from app.agents.tools import compute_findings_summary


def test_empty_findings():
    assert compute_findings_summary([]) == {"total": 0, "by_severity": {}, "by_type": {}}


def test_counts_by_severity_and_type():
    findings = [
        {"severity": "critical", "finding_type": "vehicle_presence", "confidence": 0.9},
        {"severity": "major", "finding_type": "vehicle_presence", "confidence": 0.7},
        {"severity": "major", "finding_type": "personnel_presence", "confidence": 0.6},
    ]
    result = compute_findings_summary(findings)
    assert result["total"] == 3
    assert result["by_severity"] == {"major": 2, "critical": 1}
    assert result["by_type"] == {"vehicle_presence": 2, "personnel_presence": 1}
    assert abs(result["mean_confidence"] - 0.733) < 0.01
