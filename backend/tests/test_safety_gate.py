import pytest

from app.memory import repository as repo
from app.safety import gate
from app.safety.policy import (
    RiskLevel,
    ZoneClass,
    ZoneEntryBlocked,
    assess_battery_continue,
    assess_dismiss_finding,
    assess_finding_confidence,
    assess_zone_entry,
)


def test_class_a_zone_entry_is_blocked_not_gated():
    with pytest.raises(ZoneEntryBlocked):
        assess_zone_entry(ZoneClass.A)


def test_class_b_zone_entry_is_high_risk():
    assert assess_zone_entry(ZoneClass.B) == RiskLevel.high


def test_class_c_zone_entry_is_low_risk():
    assert assess_zone_entry(ZoneClass.C) == RiskLevel.low


def test_battery_continue_thresholds():
    assert assess_battery_continue(10.0) == RiskLevel.high
    assert assess_battery_continue(24.9) == RiskLevel.high
    assert assess_battery_continue(25.0) == RiskLevel.low
    assert assess_battery_continue(80.0) == RiskLevel.low


def test_low_confidence_finding_is_high_risk():
    assert assess_finding_confidence(0.3) == RiskLevel.high
    assert assess_finding_confidence(0.54) == RiskLevel.high
    assert assess_finding_confidence(0.55) == RiskLevel.low
    assert assess_finding_confidence(0.9) == RiskLevel.low


def test_dismissing_critical_finding_is_high_risk():
    assert assess_dismiss_finding("critical") == RiskLevel.high
    assert assess_dismiss_finding("major") == RiskLevel.low


def test_high_risk_action_blocked_then_proceeds_after_approval():
    """The required safety test: a high-risk action (entering a Class B
    restricted zone) must be BLOCKED with no approval recorded, and must
    proceed only after an operator approval decision is recorded.
    """
    mission_id = repo.create_mission(site_id="meridian-substation", operator_goal="inspect zone B")
    risk = assess_zone_entry(ZoneClass.B)
    assert risk == RiskLevel.high

    # --- FAILS first: no approval recorded yet ---
    result = gate.submit_for_gate(
        mission_id=mission_id, action_description="enter restricted zone B at WP-05",
        risk_level=risk, proposing_agent="orchestrator", evidence={"waypoint_id": "WP-05"},
    )
    assert result.allowed is False
    assert result.approval_id is not None
    assert gate.check_gate(result.approval_id) is False  # <-- blocked

    # --- PASSES after an operator approval is recorded ---
    gate.decide(result.approval_id, "approved", operator_id="operator-7", rationale="site visit confirmed safe")
    assert gate.check_gate(result.approval_id) is True  # <-- now proceeds

    audit = repo.get_audit_log(mission_id=mission_id)
    event_types = [e.event_type for e in audit]
    assert "approval_requested" in event_types
    assert "approval_decided" in event_types


def test_high_risk_action_rejected_stays_blocked():
    mission_id = repo.create_mission(site_id="meridian-substation", operator_goal="inspect zone B")
    result = gate.submit_for_gate(
        mission_id=mission_id, action_description="continue past battery threshold",
        risk_level=RiskLevel.high, proposing_agent="orchestrator", evidence={},
    )
    gate.decide(result.approval_id, "rejected", operator_id="operator-7", rationale="return to home instead")
    assert gate.check_gate(result.approval_id) is False


def test_low_risk_action_is_never_gated():
    mission_id = repo.create_mission(site_id="meridian-substation", operator_goal="routine sweep")
    result = gate.submit_for_gate(
        mission_id=mission_id, action_description="enter caution zone C",
        risk_level=RiskLevel.low, proposing_agent="orchestrator", evidence={},
    )
    assert result.allowed is True
    assert result.approval_id is None
