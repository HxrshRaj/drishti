"""Real Python tools the CrewAI reporting crew calls — no stubs. The
pandas summary is unit-tested directly (test_reporting_tools.py) so its
correctness doesn't depend on any LLM successfully driving a tool call.
"""
from __future__ import annotations

import json

import pandas as pd
from crewai.tools import tool


def compute_findings_summary(findings: list[dict]) -> dict:
    """Real pandas computation — counts by severity and by finding_type,
    plus the total. This is what SOP-009 requires: the quantitative
    summary must be computed by a tool, not estimated from prose.
    """
    if not findings:
        return {"total": 0, "by_severity": {}, "by_type": {}}
    df = pd.DataFrame(findings)
    return {
        "total": int(len(df)),
        "by_severity": df["severity"].value_counts().to_dict(),
        "by_type": df["finding_type"].value_counts().to_dict(),
        "mean_confidence": round(float(df["confidence"].mean()), 3) if "confidence" in df else None,
    }


@tool("Findings Summary Tool")
def findings_summary_tool(findings_json: str) -> str:
    """Given a JSON array of findings (each with severity, finding_type,
    confidence), returns a JSON object with counts by severity, counts by
    finding_type, total count, and mean confidence — computed with pandas.
    """
    findings = json.loads(findings_json)
    return json.dumps(compute_findings_summary(findings))
