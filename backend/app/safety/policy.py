"""Risk policy: classifies proposed actions low/medium/high per SOP-001
through SOP-005, independent of any framework so it's trivially unit
testable. The orchestration layer (LangGraph nodes) calls these functions
and, for `high`, routes through the approval gate in app.safety.gate
before letting the action proceed — this is what SOP-004 requires.
"""
from __future__ import annotations

from enum import Enum

BATTERY_CONTINUE_THRESHOLD = 25.0  # SOP-002
LOW_CONFIDENCE_THRESHOLD = 0.55  # SOP-004 / SOP-005


class RiskLevel(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class ZoneClass(str, Enum):
    A = "A"
    B = "B"
    C = "C"


class ZoneEntryBlocked(Exception):
    """Raised for a Class A (no-fly) zone: SOP-001 says this is never
    approvable and the mission must re-plan around it, not go through the
    approval gate.
    """


def assess_zone_entry(zone_class: ZoneClass | str | None) -> RiskLevel:
    if zone_class is None:
        return RiskLevel.low
    zc = ZoneClass(zone_class) if not isinstance(zone_class, ZoneClass) else zone_class
    if zc == ZoneClass.A:
        raise ZoneEntryBlocked("Class A zones are never approvable; the mission must re-plan around them (SOP-001)")
    if zc == ZoneClass.B:
        return RiskLevel.high
    return RiskLevel.low  # Class C is caution-only, not an approval-gated risk


def assess_battery_continue(battery_pct: float) -> RiskLevel:
    return RiskLevel.high if battery_pct < BATTERY_CONTINUE_THRESHOLD else RiskLevel.low


def assess_finding_confidence(confidence: float) -> RiskLevel:
    """SOP-004 rule 3: acting on (escalating, reporting externally, or
    scheduling a follow-up mission for) a finding below 0.55 confidence is
    high-risk, even if the verifier accepted it.
    """
    return RiskLevel.high if confidence < LOW_CONFIDENCE_THRESHOLD else RiskLevel.low


def assess_dismiss_finding(severity: str) -> RiskLevel:
    """SOP-004 rule 4: dismissing/resolving a critical-severity finding is
    high-risk.
    """
    return RiskLevel.high if severity == "critical" else RiskLevel.low


def requires_approval(risk_level: RiskLevel) -> bool:
    return risk_level == RiskLevel.high
