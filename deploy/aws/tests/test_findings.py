import json

import pytest

from common.findings import FindingError, extract_json, narrate, perceive, validate_finding

GOOD = {"finding_type": "Vehicle Presence", "location_description": "north lot",
        "severity": "minor", "confidence": 0.8, "notes": "two trucks"}


class FakeBedrock:
    """Returns canned Converse responses in order and records the requests."""
    def __init__(self, *texts):
        self.texts = list(texts)
        self.calls = []

    def converse(self, **kwargs):
        self.calls.append(kwargs)
        return {"output": {"message": {"role": "assistant",
                                       "content": [{"text": self.texts.pop(0)}]}}}


def test_validate_normalizes_type():
    assert validate_finding(GOOD)["finding_type"] == "vehicle_presence"


@pytest.mark.parametrize("bad", [
    {**GOOD, "severity": "catastrophic"}, {**GOOD, "confidence": 1.5},
    {**GOOD, "confidence": True}, {**GOOD, "finding_type": " "},
    {k: v for k, v in GOOD.items() if k != "location_description"}, ["not", "a", "dict"],
])
def test_validate_rejects_bad(bad):
    with pytest.raises(FindingError):
        validate_finding(bad)


def test_extract_json_from_fenced_reply():
    assert extract_json("Sure!\n```json\n" + json.dumps(GOOD) + "\n```")["severity"] == "minor"
    with pytest.raises(FindingError):
        extract_json("no braces here")


def test_perceive_first_try_sends_image_and_prompt():
    client = FakeBedrock(json.dumps(GOOD))
    r = perceive(client, "m", b"\xff\xd8img", "jpeg")
    assert not r.parse_failed and r.attempts == 1 and r.finding["severity"] == "minor"
    content = client.calls[0]["messages"][0]["content"]
    assert content[0]["image"]["format"] == "jpeg" and content[0]["image"]["source"]["bytes"]
    assert client.calls[0]["inferenceConfig"]["temperature"] == 0


def test_perceive_retries_once_then_succeeds():
    client = FakeBedrock("I see trucks", json.dumps(GOOD))
    r = perceive(client, "m", b"x", "png")
    assert not r.parse_failed and r.attempts == 2
    assert client.calls[1]["messages"][-1]["content"][0]["text"].startswith("Your last reply")


def test_perceive_reports_parse_failure_instead_of_guessing():
    client = FakeBedrock("nope", "still nope")
    r = perceive(client, "m", b"x", "jpeg")
    assert r.parse_failed and r.finding is None and r.attempts == 2


def test_narrate_passes_only_given_numbers():
    client = FakeBedrock("  Two minor findings.  ")
    assert narrate(client, "m", {"minor": 2}, 2) == "Two minor findings."
    assert '"minor": 2' in client.calls[0]["messages"][0]["content"][0]["text"]
