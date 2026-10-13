"""Perception logic shared by the Lambdas: build the prompt, call Amazon Bedrock,
and validate the model's JSON against the same rules as backend/app/perception/schemas.py
(VLMFinding). Kept free of third-party dependencies so the Lambda needs only boto3,
which is already in the Lambda runtime."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass

SEVERITIES = {"critical", "major", "minor", "informational"}

PROMPT = (
    "You are inspecting one aerial image of an industrial site. Reply with ONE JSON object "
    "and nothing else, with exactly these keys: "
    '"finding_type" (short snake_case label, e.g. vehicle_presence, personnel_presence, '
    "congestion_or_obstruction, equipment_or_structure_anomaly, no_finding), "
    '"location_description" (where in the image, one sentence), '
    '"severity" (one of critical, major, minor, informational), '
    '"confidence" (number from 0 to 1), "notes" (one short sentence). '
    "Describe only what is visible; if unsure, lower the confidence."
)
REPAIR_PROMPT = (
    "Your last reply was not valid. Reply again with ONLY the JSON object described above, "
    "no extra text."
)


class FindingError(ValueError):
    pass


@dataclass
class Perception:
    finding: dict | None
    parse_failed: bool
    raw_output: str
    attempts: int


def validate_finding(obj: object) -> dict:
    """Same constraints as the VLMFinding pydantic model."""
    if not isinstance(obj, dict):
        raise FindingError("not a JSON object")
    ftype = obj.get("finding_type")
    loc = obj.get("location_description")
    sev = obj.get("severity")
    conf = obj.get("confidence")
    notes = obj.get("notes", "")
    if not isinstance(ftype, str) or not ftype.strip():
        raise FindingError("finding_type missing")
    if not isinstance(loc, str) or not loc.strip():
        raise FindingError("location_description missing")
    if sev not in SEVERITIES:
        raise FindingError("severity invalid")
    if isinstance(conf, bool) or not isinstance(conf, (int, float)) or not 0 <= conf <= 1:
        raise FindingError("confidence must be a number between 0 and 1")
    if not isinstance(notes, str):
        raise FindingError("notes must be a string")
    return {
        "finding_type": ftype.strip().lower().replace(" ", "_")[:64],
        "location_description": loc.strip()[:300],
        "severity": sev,
        "confidence": float(conf),
        "notes": notes[:500],
    }


def extract_json(text: str) -> dict:
    """Models sometimes wrap JSON in prose or code fences; take the first {...} block."""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise FindingError("no JSON object in reply")
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise FindingError(f"invalid JSON: {exc}") from exc


def _converse_text(client, model_id: str, messages: list[dict]) -> str:
    resp = client.converse(
        modelId=model_id,
        messages=messages,
        inferenceConfig={"maxTokens": 400, "temperature": 0},
    )
    parts = resp["output"]["message"]["content"]
    return "".join(p.get("text", "") for p in parts)


def perceive(client, model_id: str, image_bytes: bytes, image_format: str,
             max_attempts: int = 2) -> Perception:
    """Ask the model about one image; retry once with a repair prompt if the reply is not
    valid, and report a parse failure instead of guessing (mirrors the local pipeline)."""
    first = {
        "role": "user",
        "content": [
            {"image": {"format": image_format, "source": {"bytes": image_bytes}}},
            {"text": PROMPT},
        ],
    }
    messages = [first]
    raw = ""
    for attempt in range(1, max_attempts + 1):
        raw = _converse_text(client, model_id, messages)
        try:
            return Perception(validate_finding(extract_json(raw)), False, raw, attempt)
        except FindingError:
            messages = [
                first,
                {"role": "assistant", "content": [{"text": raw or "(empty)"}]},
                {"role": "user", "content": [{"text": REPAIR_PROMPT}]},
            ]
    return Perception(None, True, raw, max_attempts)


def narrate(client, model_id: str, counts: dict[str, int], total: int) -> str:
    """Plain-language summary of ALREADY-COMPUTED counts. The model is told to use only
    these numbers; the counts themselves are always returned alongside it."""
    prompt = (
        "Write a 2-3 sentence plain-English summary of these aerial-inspection results for a "
        "site manager. Use only the numbers given; do not invent anything.\n"
        f"Total images analysed: {total}\nFindings by severity: {json.dumps(counts)}"
    )
    msgs = [{"role": "user", "content": [{"text": prompt}]}]
    return _converse_text(client, model_id, msgs).strip()
