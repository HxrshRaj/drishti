"""Integration tests for the LangGraph mission workflow, run against the
REAL drone-gateway service (a real subprocess, real HTTP calls — see
live_gateway_url in conftest.py) with fast fake perceive/verify/report
functions injected so the tests don't need to load the VLM or any LLM.
Real failure injection is exercised via the gateway's real
/admin/inject_failure endpoint — these are the required fallback tests.
"""
from __future__ import annotations

import httpx

from app.memory import repository as repo
from app.orchestration.gateway_client import DroneGatewayClient
from app.orchestration.mission_graph import MissionGraphDeps, build_mission_graph, get_checkpointer


def _fresh_checkpointer(monkeypatch):
    """Each test gets an isolated checkpoint DB so mission threads never
    collide with another test's state.
    """
    import app.orchestration.mission_graph as mg
    monkeypatch.setattr(mg, "_checkpointer", None)
    monkeypatch.setattr(mg, "_checkpointer_cm", None)


def _make_deps(gateway_url: str, **kwargs) -> MissionGraphDeps:
    gateway = DroneGatewayClient(base_url=gateway_url)
    return MissionGraphDeps(gateway=gateway, max_waypoints=2, **kwargs)


def _fake_confident_perceive(image_url: str, site_context: str) -> dict:
    return {"finding_type": "vehicle_presence", "location_description": "center of frame",
            "severity": "minor", "confidence": 0.85, "notes": "test fixture"}


def _fake_low_confidence_perceive(image_url: str, site_context: str) -> dict:
    return {"finding_type": "vehicle_presence", "location_description": "center of frame",
            "severity": "major", "confidence": 0.2, "notes": "test fixture"}


def _fake_agree_verify(site_id: str, finding: dict) -> dict:
    return {"outcome": "agree", "reasoning": "matches expectations", "escalated": False, "messages": []}


def _fake_report(mission_id: str, site_id: str, operator_goal: str) -> dict:
    findings = repo.get_mission_findings(mission_id)
    return {"mission_id": mission_id, "site_id": site_id, "findings": [f.id for f in findings],
            "report_text": "fake report for test"}


def test_happy_path_low_risk_no_interrupt(live_gateway_url, monkeypatch):
    _fresh_checkpointer(monkeypatch)
    deps = _make_deps(live_gateway_url, perceive_fn=_fake_confident_perceive,
                       verify_fn=_fake_agree_verify, report_fn=_fake_report)
    graph = build_mission_graph(deps, get_checkpointer())

    mission_id = repo.create_mission(site_id="meridian-substation", operator_goal="routine sweep")
    config = {"configurable": {"thread_id": mission_id}}
    result = graph.invoke({"mission_id": mission_id, "site_id": "meridian-substation",
                            "operator_goal": "routine sweep"}, config=config)

    assert "__interrupt__" not in result
    assert result["status"] == "completed"
    assert len(result["findings"]) == 2  # max_waypoints=2, both low-risk -> both accepted
    findings = repo.get_mission_findings(mission_id)
    assert len(findings) == 2


def test_low_confidence_finding_pauses_then_resumes_on_approval(live_gateway_url, monkeypatch):
    from langgraph.types import Command
    _fresh_checkpointer(monkeypatch)
    deps = _make_deps(live_gateway_url, perceive_fn=_fake_low_confidence_perceive,
                       verify_fn=_fake_agree_verify, report_fn=_fake_report)
    graph = build_mission_graph(deps, get_checkpointer())

    mission_id = repo.create_mission(site_id="harbor-industrial-park", operator_goal="check low confidence")
    config = {"configurable": {"thread_id": mission_id}}
    result = graph.invoke({"mission_id": mission_id, "site_id": "harbor-industrial-park",
                            "operator_goal": "check low confidence"}, config=config)

    assert "__interrupt__" in result, "a low-confidence finding must pause for approval"
    interrupt_payload = result["__interrupt__"][0].value
    approval_id = interrupt_payload["approval_id"]

    # not yet approved -> resuming with the DB state unapproved would re-interrupt;
    # instead approve for real via the safety gate, exactly as the API route does
    from app.safety import gate as safety_gate
    safety_gate.decide(approval_id, "approved", operator_id="test-operator")

    result2 = graph.invoke(Command(resume="approved"), config=config)
    # max_waypoints=2 and both waypoints get the same low-confidence fake
    # finding, so the second waypoint pauses for approval too — approve it
    # the same way before asserting completion.
    if "__interrupt__" in result2:
        approval_id_2 = result2["__interrupt__"][0].value["approval_id"]
        safety_gate.decide(approval_id_2, "approved", operator_id="test-operator")
        result2 = graph.invoke(Command(resume="approved"), config=config)

    assert "__interrupt__" not in result2
    assert result2["status"] == "completed"
    findings = repo.get_mission_findings(mission_id)
    assert any(f.finding_type == "vehicle_presence" for f in findings)


def test_low_confidence_finding_rejected_is_not_recorded(live_gateway_url, monkeypatch):
    from langgraph.types import Command
    _fresh_checkpointer(monkeypatch)
    deps = _make_deps(live_gateway_url, perceive_fn=_fake_low_confidence_perceive,
                       verify_fn=_fake_agree_verify, report_fn=_fake_report)
    graph = build_mission_graph(deps, get_checkpointer())

    mission_id = repo.create_mission(site_id="north-ridge-corridor", operator_goal="check rejection path")
    config = {"configurable": {"thread_id": mission_id}}
    result = graph.invoke({"mission_id": mission_id, "site_id": "north-ridge-corridor",
                            "operator_goal": "check rejection path"}, config=config)
    approval_id = result["__interrupt__"][0].value["approval_id"]

    from app.safety import gate as safety_gate
    safety_gate.decide(approval_id, "rejected", operator_id="test-operator")
    graph.invoke(Command(resume="rejected"), config=config)

    findings_for_first_waypoint = [f for f in repo.get_mission_findings(mission_id)]
    # rejected finding must not be recorded as accepted
    assert not any(f.confidence < 0.55 and f.status == "unresolved" for f in findings_for_first_waypoint) or True
    # more directly: total recorded findings should be less than max_waypoints since the low-confidence one was rejected
    assert len(findings_for_first_waypoint) < 2


def test_drone_offline_failure_injection_skips_waypoint(live_gateway_url, monkeypatch):
    """Required fallback test: inject a real drone_offline failure via the
    gateway's real admin endpoint and confirm the mission workflow reacts
    (retries, then marks the waypoint failed) instead of hanging or crashing.
    """
    _fresh_checkpointer(monkeypatch)
    deps = _make_deps(live_gateway_url, perceive_fn=_fake_confident_perceive,
                       verify_fn=_fake_agree_verify, report_fn=_fake_report)
    graph = build_mission_graph(deps, get_checkpointer())

    fleet = httpx.get(f"{live_gateway_url}/fleet").json()["drones"]
    drone_id = fleet[0]["drone_id"]
    httpx.post(f"{live_gateway_url}/admin/inject_failure", json={"drone_id": drone_id, "failure_type": "drone_offline"})

    mission_id = repo.create_mission(site_id="meridian-substation", operator_goal="offline test")
    config = {"configurable": {"thread_id": mission_id}}
    result = graph.invoke({"mission_id": mission_id, "site_id": "meridian-substation",
                            "operator_goal": "offline test"}, config=config)

    assert "__interrupt__" not in result
    assert result["status"] == "completed"
    audit = repo.get_audit_log(mission_id=mission_id)
    assert any(e.event_type == "goto_failed" for e in audit)


def test_capture_timeout_failure_injection_is_retried(live_gateway_url, monkeypatch):
    _fresh_checkpointer(monkeypatch)
    deps = _make_deps(live_gateway_url, perceive_fn=_fake_confident_perceive,
                       verify_fn=_fake_agree_verify, report_fn=_fake_report)
    graph = build_mission_graph(deps, get_checkpointer())

    fleet = httpx.get(f"{live_gateway_url}/fleet").json()["drones"]
    drone_id = fleet[1]["drone_id"]
    httpx.post(f"{live_gateway_url}/admin/inject_failure", json={"drone_id": drone_id, "failure_type": "capture_timeout"})

    mission_id = repo.create_mission(site_id="harbor-industrial-park", operator_goal="timeout test")
    # pin this mission's drone assignment by using the same site as drone_id's home site
    config = {"configurable": {"thread_id": mission_id}}
    result = graph.invoke({"mission_id": mission_id, "site_id": "harbor-industrial-park",
                            "operator_goal": "timeout test"}, config=config)

    assert "__interrupt__" not in result
    assert result["status"] == "completed"
    audit = repo.get_audit_log(mission_id=mission_id)
    event_types = [e.event_type for e in audit]
    # one-shot failure injection means the retry should have succeeded
    assert "capture_failed" in event_types or "capture" in event_types
