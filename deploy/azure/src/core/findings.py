"""Perception logic: prompt Azure OpenAI with one image, validate the JSON reply against the
same rules as backend/app/perception/schemas.py (VLMFinding), retry once, never guess."""
from __future__ import annotations

import base64
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
REPAIR_PROMPT = ("Your last reply was not valid. Reply again with ONLY the JSON object described "
                 "above, no extra text.")


class FindingError(ValueError):
    pass


@dataclass
class Perception:
    finding: dict | None
    parse_failed: bool
    raw_output: str
    attempts: int


def validate_finding(obj: object) -> dict:
    if not isinstance(obj, dict):
        raise FindingError("not a JSON object")
    ftype, loc = obj.get("finding_type"), obj.get("location_description")
    sev, conf, notes = obj.get("severity"), obj.get("confidence"), obj.get("notes", "")
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
    return {"finding_type": ftype.strip().lower().replace(" ", "_")[:64],
            "location_description": loc.strip()[:300], "severity": sev,
            "confidence": float(conf), "notes": notes[:500]}


def extract_json(text: str) -> dict:
    match = re.search(r"\{.*\}", text or "", re.DOTALL)
    if not match:
        raise FindingError("no JSON object in reply")
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise FindingError(f"invalid JSON: {exc}") from exc


def _chat(client, deployment: str, messages: list[dict]) -> str:
    resp = client.chat.completions.create(model=deployment, messages=messages,
                                          temperature=0, max_tokens=400)
    return resp.choices[0].message.content or ""


def perceive(client, deployment: str, image_bytes: bytes, mime: str,
             max_attempts: int = 2) -> Perception:
    data_uri = f"data:{mime};base64,{base64.b64encode(image_bytes).decode()}"
    first = {"role": "user", "content": [
        {"type": "text", "text": PROMPT},
        {"type": "image_url", "image_url": {"url": data_uri}}]}
    messages = [first]
    raw = ""
    for attempt in range(1, max_attempts + 1):
        raw = _chat(client, deployment, messages)
        try:
            return Perception(validate_finding(extract_json(raw)), False, raw, attempt)
        except FindingError:
            messages = [first, {"role": "assistant", "content": raw or "(empty)"},
                        {"role": "user", "content": REPAIR_PROMPT}]
    return Perception(None, True, raw, max_attempts)


def narrate(client, deployment: str, counts: dict[str, int], total: int) -> str:
    prompt = ("Write a 2-3 sentence plain-English summary of these aerial-inspection results "
              "for a site manager. Use only the numbers given; do not invent anything.\n"
              f"Total images analysed: {total}\nFindings by severity: {json.dumps(counts)}")
    return _chat(client, deployment, [{"role": "user", "content": prompt}]).strip()
