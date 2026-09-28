"""Persistent memory of past missions/findings, plus the approval and audit
logs (SOP-010, SOP-004, SOP-014). Backed by SQLite via SQLAlchemy — this is
the layer LangGraph's mission-planning node queries with "what's still open
at this site from last time" (SOP-010), and what the operator dashboard's
approval queue and audit timeline read from.
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import select

from app.db.models import Approval, AuditEvent, Finding, Mission
from app.db.session import get_session
from app.observability.logging_config import log_json


# ---- missions -------------------------------------------------------------
def create_mission(site_id: str, operator_goal: str) -> str:
    with get_session() as s:
        m = Mission(site_id=site_id, operator_goal=operator_goal, status="planned")
        s.add(m)
        s.flush()
        return m.id


def set_mission_status(mission_id: str, status: str, ended: bool = False) -> None:
    with get_session() as s:
        m = s.get(Mission, mission_id)
        if m is None:
            raise ValueError(f"no such mission {mission_id}")
        m.status = status
        if ended:
            m.ended_at = dt.datetime.now(dt.UTC)


def save_mission_report(mission_id: str, report_text: str, report_summary: dict) -> None:
    with get_session() as s:
        m = s.get(Mission, mission_id)
        if m is None:
            raise ValueError(f"no such mission {mission_id}")
        m.report_text = report_text
        m.report_summary = report_summary


def list_missions(limit: int = 50) -> list[Mission]:
    with get_session() as s:
        stmt = select(Mission).order_by(Mission.started_at.desc()).limit(limit)
        return list(s.execute(stmt).scalars())


def get_mission(mission_id: str) -> Mission | None:
    with get_session() as s:
        return s.get(Mission, mission_id)


def get_prior_missions(site_id: str, exclude_mission_id: str | None = None, limit: int = 5) -> list[Mission]:
    with get_session() as s:
        stmt = select(Mission).where(Mission.site_id == site_id).order_by(Mission.started_at.desc()).limit(limit)
        rows = list(s.execute(stmt).scalars())
        if exclude_mission_id:
            rows = [r for r in rows if r.id != exclude_mission_id]
        return rows


# ---- findings ---------------------------------------------------------------
def record_finding(mission_id: str, site_id: str, waypoint_id: str, image_file: str,
                    finding_type: str, location_description: str, severity: str,
                    confidence: float, verifier_outcome: str = "unverified") -> str:
    with get_session() as s:
        f = Finding(
            mission_id=mission_id, site_id=site_id, waypoint_id=waypoint_id, image_file=image_file,
            finding_type=finding_type, location_description=location_description,
            severity=severity, confidence=confidence, verifier_outcome=verifier_outcome,
        )
        s.add(f)
        s.flush()
        return f.id


def get_unresolved_findings(site_id: str, exclude_mission_id: str | None = None) -> list[Finding]:
    with get_session() as s:
        stmt = select(Finding).where(Finding.site_id == site_id, Finding.status == "unresolved")
        rows = list(s.execute(stmt).scalars())
        if exclude_mission_id:
            rows = [r for r in rows if r.mission_id != exclude_mission_id]
        return rows


def resolve_finding(finding_id: str) -> None:
    with get_session() as s:
        f = s.get(Finding, finding_id)
        if f is not None:
            f.status = "resolved"


def get_mission_findings(mission_id: str) -> list[Finding]:
    with get_session() as s:
        stmt = select(Finding).where(Finding.mission_id == mission_id)
        return list(s.execute(stmt).scalars())


def list_all_findings(limit: int = 100) -> list[Finding]:
    with get_session() as s:
        stmt = select(Finding).order_by(Finding.created_at.desc()).limit(limit)
        return list(s.execute(stmt).scalars())


# ---- approvals (SOP-004) -----------------------------------------------------
def create_approval_request(mission_id: str, action_description: str, risk_level: str,
                             proposing_agent: str, evidence: dict) -> str:
    with get_session() as s:
        a = Approval(mission_id=mission_id, action_description=action_description, risk_level=risk_level,
                      proposing_agent=proposing_agent, evidence=evidence, status="pending")
        s.add(a)
        s.flush()
        return a.id


def decide_approval(approval_id: str, status: str, operator_id: str, rationale: str = "") -> Approval:
    if status not in ("approved", "rejected", "modified"):
        raise ValueError(f"invalid approval status {status!r}")
    with get_session() as s:
        a = s.get(Approval, approval_id)
        if a is None:
            raise ValueError(f"no such approval {approval_id}")
        a.status = status
        a.operator_id = operator_id
        a.rationale = rationale
        a.decided_at = dt.datetime.now(dt.UTC)
        s.flush()
        s.refresh(a)
        return a


def get_approval(approval_id: str) -> Approval | None:
    with get_session() as s:
        return s.get(Approval, approval_id)


def get_pending_approvals(mission_id: str | None = None) -> list[Approval]:
    with get_session() as s:
        stmt = select(Approval).where(Approval.status == "pending")
        if mission_id:
            stmt = stmt.where(Approval.mission_id == mission_id)
        return list(s.execute(stmt).scalars())


# ---- audit log (SOP-014) -----------------------------------------------------
def log_audit_event(event_type: str, actor: str, payload: dict, mission_id: str | None = None) -> None:
    with get_session() as s:
        s.add(AuditEvent(mission_id=mission_id, event_type=event_type, actor=actor, payload=payload))
    log_json(event_type, actor=actor, mission_id=mission_id, payload=payload)


def get_audit_log(mission_id: str | None = None, limit: int = 200) -> list[AuditEvent]:
    with get_session() as s:
        stmt = select(AuditEvent).order_by(AuditEvent.timestamp.desc()).limit(limit)
        if mission_id:
            stmt = stmt.where(AuditEvent.mission_id == mission_id)
        return list(s.execute(stmt).scalars())
