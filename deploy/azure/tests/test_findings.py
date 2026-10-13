import json

import pytest
from conftest import FakeOpenAI

from core.findings import FindingError, extract_json, narrate, perceive, validate_finding

GOOD = {"finding_type": "Vehicle Presence", "location_description": "north lot",
        "severity": "minor", "confidence": 0.8, "notes": "two trucks"}


def test_validate_normalizes_type():
    assert validate_finding(GOOD)["finding_type"] == "vehicle_presence"


@pytest.mark.parametrize("bad", [
    {**GOOD, "severity": "catastrophic"}, {**GOOD, "confidence": 1.5}, {**GOOD, "confidence": True},
    {**GOOD, "finding_type": " "}, {k: v for k, v in GOOD.items() if k != "location_description"},
    ["a", "list"]])
def test_validate_rejects_bad(bad):
    with pytest.raises(FindingError):
        validate_finding(bad)


def test_extract_json_handles_fences_and_prose():
    assert extract_json("Sure\n```json\n" + json.dumps(GOOD) + "\n```")["severity"] == "minor"
    with pytest.raises(FindingError):
        extract_json("nothing here")


def test_perceive_sends_image_as_data_uri():
    c = FakeOpenAI(json.dumps(GOOD))
    r = perceive(c, "gpt-4o-mini", b"\xff\xd8abc", "image/jpeg")
    assert r.attempts == 1 and not r.parse_failed
    part = c.calls[0]["messages"][0]["content"][1]
    assert part["image_url"]["url"].startswith("data:image/jpeg;base64,")
    assert c.calls[0]["temperature"] == 0 and c.calls[0]["model"] == "gpt-4o-mini"


def test_perceive_retries_once_with_repair_prompt():
    c = FakeOpenAI("looks like trucks", json.dumps(GOOD))
    r = perceive(c, "m", b"x", "image/png")
    assert r.attempts == 2 and not r.parse_failed
    assert c.calls[1]["messages"][-1]["content"].startswith("Your last reply")


def test_perceive_reports_parse_failure_instead_of_guessing():
    r = perceive(FakeOpenAI("nope", "still nope"), "m", b"x", "image/png")
    assert r.parse_failed and r.finding is None and r.attempts == 2


def test_narrate_gets_only_the_counts():
    c = FakeOpenAI("  Two minor findings.  ")
    assert narrate(c, "m", {"minor": 2}, 2) == "Two minor findings."
    assert '"minor": 2' in c.calls[0]["messages"][0]["content"]
