from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class VerifierOutcome(str, Enum):
    agree = "agree"
    disagree = "disagree"
    uncertain = "uncertain"


class VerifierVerdict(BaseModel):
    outcome: VerifierOutcome
    reasoning: str = Field(default="", max_length=600)
    alternative_finding_type: str | None = None


class VerificationExchange(BaseModel):
    """Full transcript + resolution of one Perception-vs-Verifier exchange
    (SOP-007), suitable for logging verbatim to the audit trail.
    """
    finding_type: str
    confidence: float
    messages: list[dict]  # [{"source": "PerceptionAgent"|"VerifierAgent", "content": str}, ...]
    verdict: VerifierVerdict
    parse_failed: bool
    escalated: bool
