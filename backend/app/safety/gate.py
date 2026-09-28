"""The approval gate itself (SOP-004): given a risk assessment, either lets
an action proceed immediately (low/medium) or creates a pending approval
record and blocks until an operator decision is recorded. This is what the
LangGraph mission workflow calls `interrupt()` around.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.memory import repository as repo
from app.safety.policy import RiskLevel, requires_approval


@dataclass
class GateResult:
    allowed: bool
    approval_id: str | None
    risk_level: RiskLevel


def submit_for_gate(mission_id: str, action_description: str, risk_level: RiskLevel,
                     proposing_agent: str, evidence: dict) -> GateResult:
    if not requires_approval(risk_level):
        return GateResult(allowed=True, approval_id=None, risk_level=risk_level)

    approval_id = repo.create_approval_request(
        mission_id=mission_id, action_description=action_description, risk_level=risk_level.value,
        proposing_agent=proposing_agent, evidence=evidence,
    )
    repo.log_audit_event(
        "approval_requested", actor=proposing_agent, mission_id=mission_id,
        payload={"approval_id": approval_id, "action": action_description, "risk_level": risk_level.value},
    )
    return GateResult(allowed=False, approval_id=approval_id, risk_level=risk_level)


def check_gate(approval_id: str) -> bool:
    """Returns True only if an operator has recorded 'approved'. 'modified'
    is deliberately NOT treated as approved here — SOP-004 says a `modify`
    decision produces a *new* proposed action subject to its own risk
    assessment, not a green light for the original one.
    """
    approval = repo.get_approval(approval_id)
    return approval is not None and approval.status == "approved"


def decide(approval_id: str, decision: str, operator_id: str, rationale: str = ""):
    result = repo.decide_approval(approval_id, decision, operator_id, rationale)
    repo.log_audit_event(
        "approval_decided", actor=f"operator:{operator_id}", mission_id=result.mission_id,
        payload={"approval_id": approval_id, "decision": decision, "rationale": rationale},
    )
    return result
