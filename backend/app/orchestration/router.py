from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.memory import repository as repo
from app.orchestration import mission_service
from app.orchestration.gateway_client import DroneGatewayClient, GatewayError
from app.safety import gate as safety_gate

router = APIRouter(tags=["missions"])


class StartMissionRequest(BaseModel):
    site_id: str
    operator_goal: str
    max_waypoints: int = 3


class DecisionRequest(BaseModel):
    decision: str  # approved | rejected
    operator_id: str
    rationale: str = ""


def _mission_dict(m) -> dict:
    return {"id": m.id, "site_id": m.site_id, "operator_goal": m.operator_goal, "status": m.status,
            "started_at": m.started_at.isoformat(), "ended_at": m.ended_at.isoformat() if m.ended_at else None,
            "has_report": bool(m.report_text)}


@router.get("/sites")
def list_sites():
    try:
        return DroneGatewayClient().list_sites()
    except GatewayError as e:
        raise HTTPException(502, detail=f"drone-gateway error: {e.detail}") from e


@router.get("/fleet")
def fleet_status():
    try:
        return DroneGatewayClient().get_fleet()
    except GatewayError as e:
        raise HTTPException(502, detail=f"drone-gateway error: {e.detail}") from e


@router.get("/missions")
def list_missions():
    return [_mission_dict(m) for m in repo.list_missions()]


@router.get("/findings")
def list_all_findings():
    rows = repo.list_all_findings()
    return [{"id": f.id, "mission_id": f.mission_id, "waypoint_id": f.waypoint_id, "finding_type": f.finding_type,
              "location_description": f.location_description, "severity": f.severity, "confidence": f.confidence,
              "verifier_outcome": f.verifier_outcome, "status": f.status, "image_file": f.image_file,
              "created_at": f.created_at.isoformat()} for f in rows]


@router.get("/missions/approvals/pending")
def pending_approvals():
    rows = repo.get_pending_approvals()
    return [{"id": a.id, "mission_id": a.mission_id, "action_description": a.action_description,
              "risk_level": a.risk_level, "proposing_agent": a.proposing_agent, "evidence": a.evidence,
              "created_at": a.created_at.isoformat()} for a in rows]


@router.post("/missions/start")
def start_mission(req: StartMissionRequest):
    return mission_service.start_mission(req.site_id, req.operator_goal, max_waypoints=req.max_waypoints)


@router.get("/missions/{mission_id}")
def get_mission(mission_id: str):
    m = repo.get_mission(mission_id)
    if m is None:
        raise HTTPException(404, detail=f"no such mission {mission_id}")
    return _mission_dict(m)


@router.post("/missions/{mission_id}/decide")
def decide(mission_id: str, req: DecisionRequest):
    pending = repo.get_pending_approvals(mission_id=mission_id)
    if pending:
        safety_gate.decide(pending[0].id, req.decision, req.operator_id, req.rationale)
    return mission_service.resume_mission(mission_id, req.decision)


@router.get("/missions/{mission_id}/audit")
def audit(mission_id: str):
    events = repo.get_audit_log(mission_id=mission_id)
    return [{"timestamp": e.timestamp.isoformat(), "event_type": e.event_type, "actor": e.actor, "payload": e.payload} for e in events]


@router.get("/missions/{mission_id}/report")
def report(mission_id: str):
    m = repo.get_mission(mission_id)
    if m is None:
        raise HTTPException(404, detail=f"no such mission {mission_id}")
    if not m.report_text:
        raise HTTPException(404, detail="no report generated for this mission yet")
    return {"mission_id": mission_id, "report_text": m.report_text, "report_summary": m.report_summary}


@router.get("/missions/{mission_id}/findings")
def findings(mission_id: str):
    rows = repo.get_mission_findings(mission_id)
    return [{"id": f.id, "waypoint_id": f.waypoint_id, "finding_type": f.finding_type,
              "severity": f.severity, "confidence": f.confidence, "verifier_outcome": f.verifier_outcome,
              "status": f.status, "image_file": f.image_file} for f in rows]
