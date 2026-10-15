"""LangGraph mission workflow: plan -> dispatch -> capture -> perceive ->
verify -> decide -> (loop to next waypoint) -> report. State is
checkpointed (SqliteSaver) so a mission can pause at a human-approval
interrupt() and resume later from exactly where it left off (SOP-004).

Perception and verification are injectable (constructor args on
MissionGraphDeps) so tests can swap in fast fakes without touching
production node logic — the real path always uses the real VLM service
and the real AutoGen verifier exchange.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TypedDict

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from app.agentkit.tracing import traced_node
from app.config import settings
from app.memory import repository as repo
from app.orchestration.gateway_client import DroneGatewayClient, GatewayError
from app.rag.retrieve import format_context, retrieve_sops
from app.safety import gate as safety_gate
from app.safety.policy import (
    RiskLevel,
    ZoneClass,
    ZoneEntryBlocked,
    assess_battery_continue,
    assess_finding_confidence,
    assess_zone_entry,
)

MAX_WAYPOINTS_DEFAULT = 3  # kept small deliberately: each waypoint runs a
# real VLM call + a real AutoGen exchange, which is slow on CPU — see
# docs/benchmarks.md. Callers can raise this for a real full-site run.


class MissionState(TypedDict, total=False):
    mission_id: str
    site_id: str
    operator_goal: str
    drone_id: str
    waypoint_ids: list[str]
    zone_by_waypoint: dict[str, str | None]
    waypoint_index: int
    findings: list[dict]
    status: str
    last_error: str | None
    report: dict | None
    # Per-waypoint scratch state, threaded between adjacent nodes only
    # (dispatch/capture -> perceive -> verify -> decide). Must be declared
    # here — LangGraph's StateGraph only tracks channels for keys present
    # in this TypedDict; any key a node returns that isn't declared is
    # silently dropped rather than merged into state.
    _capture: dict
    _finding: dict
    _verdict: dict


PerceiveFn = Callable[[str, str], dict]  # (image_url, site_context) -> finding dict
VerifyFn = Callable[[str, dict], dict]  # (site_id, finding dict) -> verdict dict
ReportFn = Callable[[str, str, str], dict]  # (mission_id, site_id, operator_goal) -> report dict


@dataclass
class MissionGraphDeps:
    gateway: DroneGatewayClient = field(default_factory=DroneGatewayClient)
    perceive_fn: PerceiveFn | None = None
    verify_fn: VerifyFn | None = None
    report_fn: ReportFn | None = None
    max_waypoints: int = MAX_WAYPOINTS_DEFAULT

    def perceive(self, image_url: str, site_context: str) -> dict:
        if self.perceive_fn is not None:
            return self.perceive_fn(image_url, site_context)
        from app.perception.router import get_service
        service = get_service()
        import httpx
        resp = httpx.get(self.gateway.client.base_url.join(image_url), timeout=30)
        resp.raise_for_status()
        import io

        from PIL import Image
        image = Image.open(io.BytesIO(resp.content)).convert("RGB")
        result = service.analyze(image, site_context=site_context)
        if result.finding is None:
            return {"finding_type": "no_finding", "location_description": "unparseable",
                    "severity": "informational", "confidence": 0.0, "notes": "parse failed"}
        return result.finding.model_dump(mode="json")

    def verify(self, site_id: str, finding: dict) -> dict:
        if self.verify_fn is not None:
            return self.verify_fn(site_id, finding)
        from app.agents.verifier import run_verification_exchange
        from app.perception.schemas import VLMFinding
        exchange = run_verification_exchange(site_id, VLMFinding.model_validate(finding))
        return {"outcome": exchange.verdict.outcome.value, "reasoning": exchange.verdict.reasoning,
                "escalated": exchange.escalated, "messages": exchange.messages}


def _log(mission_id: str, event_type: str, actor: str, payload: dict) -> None:
    repo.log_audit_event(event_type, actor=actor, payload=payload, mission_id=mission_id)


def make_plan_node(deps: MissionGraphDeps):
    def plan(state: MissionState) -> dict:
        site = deps.gateway.get_site(state["site_id"])
        waypoint_ids = [wp["waypoint_id"] for wp in site["waypoints"]][: deps.max_waypoints]
        zone_by_waypoint = {wp["waypoint_id"]: wp.get("zone_id") for wp in site["waypoints"]}
        zone_class_by_id = {z["zone_id"]: z["zone_class"] for z in site["zones"]}
        zone_class_by_waypoint = {
            wp_id: zone_class_by_id.get(zone_id) if zone_id else None
            for wp_id, zone_id in zone_by_waypoint.items()
        }

        fleet = deps.gateway.get_fleet()
        same_site_drones = [d for d in fleet if d["site_id"] == state["site_id"]]
        if not same_site_drones:
            raise ValueError(f"no drone stationed at site {state['site_id']!r}")
        drone_id = same_site_drones[0]["drone_id"]
        sop_hits = retrieve_sops(state["operator_goal"], top_k=3)
        _log(state["mission_id"], "mission_planned", "orchestrator", {
            "site_id": state["site_id"], "waypoint_ids": waypoint_ids, "drone_id": drone_id,
            "sop_context": format_context(sop_hits),
        })
        repo.set_mission_status(state["mission_id"], "running")
        return {
            "drone_id": drone_id, "waypoint_ids": waypoint_ids,
            "zone_by_waypoint": zone_class_by_waypoint, "waypoint_index": 0,
            "findings": [], "status": "running",
        }
    return plan


def make_dispatch_node(deps: MissionGraphDeps):
    def dispatch(state: MissionState) -> dict:
        wp_id = state["waypoint_ids"][state["waypoint_index"]]
        for attempt in range(3):
            try:
                deps.gateway.goto(state["drone_id"], state["mission_id"], wp_id)
                _log(state["mission_id"], "goto", "drone-gateway-client", {"waypoint_id": wp_id, "attempt": attempt + 1})
                return {"last_error": None}
            except GatewayError as e:
                _log(state["mission_id"], "goto_failed", "drone-gateway-client",
                     {"waypoint_id": wp_id, "error": e.code, "attempt": attempt + 1})
                if e.code != "drone_offline":
                    return {"last_error": e.code}
        return {"last_error": "drone_offline"}
    return dispatch


def make_capture_node(deps: MissionGraphDeps):
    def capture(state: MissionState) -> dict:
        if state.get("last_error"):
            return {}
        wp_id = state["waypoint_ids"][state["waypoint_index"]]
        for attempt in range(2):
            try:
                result = deps.gateway.capture(state["drone_id"], state["mission_id"], wp_id)
                _log(state["mission_id"], "capture", "drone-gateway-client", {"waypoint_id": wp_id, "image_file": result["image_file"]})
                return {"last_error": None, "_capture": result}
            except GatewayError as e:
                _log(state["mission_id"], "capture_failed", "drone-gateway-client",
                     {"waypoint_id": wp_id, "error": e.code, "attempt": attempt + 1})
                if e.code == "low_battery_critical":
                    deps.gateway.rth(state["drone_id"], state["mission_id"], "low_battery_critical")
                    _log(state["mission_id"], "rth", "orchestrator", {"reason": "low_battery_critical"})
                    return {"last_error": "low_battery_critical"}
                if e.code != "capture_timeout":
                    return {"last_error": e.code}
        return {"last_error": "capture_timeout"}
    return capture


def make_perceive_node(deps: MissionGraphDeps):
    def perceive(state: MissionState) -> dict:
        if state.get("last_error"):
            return {}
        capture = state["_capture"]
        sop_hits = retrieve_sops(f"waypoint inspection {state['operator_goal']}", top_k=2)
        finding = deps.perceive(capture["image_url"], format_context(sop_hits))
        return {"_finding": finding}
    return perceive


def make_verify_node(deps: MissionGraphDeps):
    def verify(state: MissionState) -> dict:
        if state.get("last_error"):
            return {}
        verdict = deps.verify(state["site_id"], state["_finding"])
        return {"_verdict": verdict}
    return verify


def make_decide_node(deps: MissionGraphDeps):
    def decide(state: MissionState) -> dict:
        if state.get("last_error"):
            idx = state["waypoint_index"]
            return {"waypoint_index": idx + 1, "last_error": None}

        wp_id = state["waypoint_ids"][state["waypoint_index"]]
        finding = state["_finding"]
        verdict = state["_verdict"]
        zone_class = state["zone_by_waypoint"].get(wp_id)

        _RISK_RANK = {RiskLevel.low: 0, RiskLevel.medium: 1, RiskLevel.high: 2}
        risk = RiskLevel.low
        block_reason = None
        try:
            if zone_class:
                zone_risk = assess_zone_entry(ZoneClass(zone_class))
                if _RISK_RANK[zone_risk] > _RISK_RANK[risk]:
                    risk = zone_risk
        except ZoneEntryBlocked:
            block_reason = "zone_class_a_blocked"

        conf_risk = assess_finding_confidence(finding["confidence"])
        if conf_risk == RiskLevel.high:
            risk = RiskLevel.high
        if verdict["outcome"] != "agree":
            risk = RiskLevel.high

        battery_pct = state.get("_capture", {}).get("battery_pct")
        battery_risk = assess_battery_continue(battery_pct) if battery_pct is not None else RiskLevel.low
        continuing_needs_approval = battery_risk == RiskLevel.high

        findings = list(state.get("findings", []))

        if block_reason:
            _log(state["mission_id"], "action_blocked", "safety-layer", {"waypoint_id": wp_id, "reason": block_reason})
        elif continuing_needs_approval:
            # SOP-002/SOP-004: below the continue threshold, RTH is the default;
            # continuing to the next waypoint instead is the high-risk action.
            gate_result = safety_gate.submit_for_gate(
                mission_id=state["mission_id"],
                action_description=f"continue mission past battery threshold ({battery_pct}%) instead of RTH",
                risk_level=RiskLevel.high, proposing_agent="orchestrator",
                evidence={"waypoint_id": wp_id, "battery_pct": battery_pct},
            )
            decision = interrupt({"approval_id": gate_result.approval_id, "waypoint_id": wp_id, "reason": "low_battery_continue"})
            if not (decision == "approved" or safety_gate.check_gate(gate_result.approval_id)):
                deps.gateway.rth(state["drone_id"], state["mission_id"], "low_battery_continue_not_approved")
                _log(state["mission_id"], "rth", "orchestrator", {"reason": "low_battery_continue_not_approved"})
                return {"waypoint_index": state["waypoint_index"] + 1, "findings": findings, "last_error": "low_battery_critical"}
            fid = repo.record_finding(
                mission_id=state["mission_id"], site_id=state["site_id"], waypoint_id=wp_id,
                image_file=state["_capture"]["image_file"], finding_type=finding["finding_type"],
                location_description=finding["location_description"], severity=finding["severity"],
                confidence=finding["confidence"], verifier_outcome=verdict["outcome"],
            )
            findings.append({"id": fid, "waypoint_id": wp_id, **finding, "verifier_outcome": verdict["outcome"]})
        elif risk == RiskLevel.high:
            gate_result = safety_gate.submit_for_gate(
                mission_id=state["mission_id"],
                action_description=f"accept finding {finding['finding_type']} at {wp_id} (confidence={finding['confidence']}, verifier={verdict['outcome']})",
                risk_level=risk, proposing_agent="orchestrator",
                evidence={"waypoint_id": wp_id, "finding": finding, "verdict": verdict},
            )
            decision = interrupt({
                "approval_id": gate_result.approval_id, "waypoint_id": wp_id,
                "finding": finding, "verdict": verdict,
            })
            if decision == "approved" or safety_gate.check_gate(gate_result.approval_id):
                fid = repo.record_finding(
                    mission_id=state["mission_id"], site_id=state["site_id"], waypoint_id=wp_id,
                    image_file=state["_capture"]["image_file"], finding_type=finding["finding_type"],
                    location_description=finding["location_description"], severity=finding["severity"],
                    confidence=finding["confidence"], verifier_outcome=verdict["outcome"],
                )
                findings.append({"id": fid, "waypoint_id": wp_id, **finding, "verifier_outcome": verdict["outcome"]})
        else:
            fid = repo.record_finding(
                mission_id=state["mission_id"], site_id=state["site_id"], waypoint_id=wp_id,
                image_file=state["_capture"]["image_file"], finding_type=finding["finding_type"],
                location_description=finding["location_description"], severity=finding["severity"],
                confidence=finding["confidence"], verifier_outcome=verdict["outcome"],
            )
            findings.append({"id": fid, "waypoint_id": wp_id, **finding, "verifier_outcome": verdict["outcome"]})

        return {"waypoint_index": state["waypoint_index"] + 1, "findings": findings, "last_error": None}
    return decide


def route_after_decide(state: MissionState) -> str:
    if state["waypoint_index"] < len(state["waypoint_ids"]):
        return "dispatch"
    return "report"


def make_report_node(deps: MissionGraphDeps):
    def report(state: MissionState) -> dict:
        if deps.report_fn is not None:
            report_data = deps.report_fn(state["mission_id"], state["site_id"], state["operator_goal"])
        else:
            from app.agents.reporting_crew import generate_report
            report_data = generate_report(state["mission_id"], state["site_id"], state["operator_goal"])
        repo.set_mission_status(state["mission_id"], "completed", ended=True)
        repo.save_mission_report(
            state["mission_id"],
            report_text=report_data.get("report_text", ""),
            report_summary=report_data.get("computed_summary", {}),
        )
        _log(state["mission_id"], "mission_completed", "orchestrator", {"n_findings": len(state.get("findings", []))})
        return {"status": "completed", "report": report_data}
    return report


def build_mission_graph(deps: MissionGraphDeps, checkpointer):
    graph = StateGraph(MissionState)
    graph.add_node("plan", traced_node("plan", make_plan_node(deps)))
    graph.add_node("dispatch", traced_node("dispatch", make_dispatch_node(deps)))
    graph.add_node("capture", traced_node("capture", make_capture_node(deps)))
    graph.add_node("perceive", traced_node("perceive", make_perceive_node(deps)))
    graph.add_node("verify", traced_node("verify", make_verify_node(deps)))
    graph.add_node("decide", traced_node("decide", make_decide_node(deps)))
    graph.add_node("report", traced_node("report", make_report_node(deps)))

    graph.add_edge(START, "plan")
    graph.add_edge("plan", "dispatch")
    graph.add_edge("dispatch", "capture")
    graph.add_edge("capture", "perceive")
    graph.add_edge("perceive", "verify")
    graph.add_edge("verify", "decide")
    graph.add_conditional_edges("decide", route_after_decide, {"dispatch": "dispatch", "report": "report"})
    graph.add_edge("report", END)

    return graph.compile(checkpointer=checkpointer)


_checkpointer_cm = None
_checkpointer = None


def get_checkpointer():
    global _checkpointer_cm, _checkpointer
    if _checkpointer is None:
        db_path = Path(settings.memory_db_path).parent / "mission_checkpoints.sqlite"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        _checkpointer_cm = SqliteSaver.from_conn_string(str(db_path))
        _checkpointer = _checkpointer_cm.__enter__()
    return _checkpointer
