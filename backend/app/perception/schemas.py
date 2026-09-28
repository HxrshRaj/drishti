from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, field_validator


class Severity(str, Enum):
    critical = "critical"
    major = "major"
    minor = "minor"
    informational = "informational"


# Suggested to the model in the prompt, but not enforced as a closed set —
# an open VLM will not reliably stay inside an enum, and forcing one would
# just relabel low-confidence guesses as false precision.
SUGGESTED_FINDING_TYPES = [
    "vehicle_presence", "personnel_presence", "congestion_or_obstruction",
    "equipment_or_structure_anomaly", "no_finding",
]


class VLMFinding(BaseModel):
    """Schema-validated output of one perception call on one image."""

    finding_type: str = Field(..., min_length=1, max_length=64)
    location_description: str = Field(..., min_length=1, max_length=300)
    severity: Severity
    confidence: float = Field(..., ge=0.0, le=1.0)
    notes: str = Field(default="", max_length=500)

    @field_validator("finding_type")
    @classmethod
    def _normalize_type(cls, v: str) -> str:
        return v.strip().lower().replace(" ", "_")[:64]


class PerceptionRequest(BaseModel):
    image_url: str | None = None  # e.g. "/images/xxx.jpg" served by drone-gateway
    image_path: str | None = None  # local filesystem path, used by eval scripts
    site_context: str = ""  # short retrieved-SOP context injected into the prompt


class PerceptionResult(BaseModel):
    finding: VLMFinding | None
    parse_failed: bool
    raw_output: str
    attempts: int
    latency_ms: float
