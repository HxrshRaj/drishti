from app.perception.schemas import Severity, VLMFinding
from app.perception.vlm import extract_json, parse_and_validate


def test_extract_json_from_clean_output():
    text = '{"finding_type": "vehicle_presence", "location_description": "center", "severity": "minor", "confidence": 0.8}'
    data = extract_json(text)
    assert data["finding_type"] == "vehicle_presence"


def test_extract_json_with_surrounding_prose():
    text = 'Sure, here is the finding:\n{"finding_type": "personnel_presence", "location_description": "left side", "severity": "major", "confidence": 0.61}\nLet me know if you need more.'
    data = extract_json(text)
    assert data["severity"] == "major"


def test_extract_json_returns_none_for_garbage():
    assert extract_json("no json here at all") is None


def test_extract_json_returns_none_for_malformed_json():
    assert extract_json("{finding_type: vehicle_presence,}") is None


def test_parse_and_validate_success():
    text = '{"finding_type": "Vehicle Presence", "location_description": "near the gate", "severity": "critical", "confidence": 0.9, "notes": "parked truck"}'
    finding, failed = parse_and_validate(text)
    assert failed is False
    assert isinstance(finding, VLMFinding)
    assert finding.severity == Severity.critical
    # normalization: spaces -> underscores, lowercased
    assert finding.finding_type == "vehicle_presence"


def test_parse_and_validate_out_of_range_confidence_fails():
    text = '{"finding_type": "x", "location_description": "y", "severity": "minor", "confidence": 1.5}'
    finding, failed = parse_and_validate(text)
    assert failed is True
    assert finding is None


def test_parse_and_validate_missing_field_fails():
    text = '{"finding_type": "x", "severity": "minor", "confidence": 0.5}'
    finding, failed = parse_and_validate(text)
    assert failed is True


def test_parse_and_validate_invalid_severity_fails():
    text = '{"finding_type": "x", "location_description": "y", "severity": "super_bad", "confidence": 0.5}'
    finding, failed = parse_and_validate(text)
    assert failed is True


def test_parse_and_validate_no_json_fails():
    finding, failed = parse_and_validate("I cannot help with that.")
    assert failed is True
    assert finding is None
