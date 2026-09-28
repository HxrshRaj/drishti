"""Analyst + Report Writer crew (SOP-009), built on CrewAI. Turns a
mission's accepted findings into a structured inspection report, using a
real pandas tool for the quantitative summary and real persistent-memory
data for the comparison-to-prior-visit section.
"""
from __future__ import annotations

import json

from crewai import LLM, Agent, Crew, Process, Task

from app.agents.tools import compute_findings_summary, findings_summary_tool
from app.llm.provider import resolve_llm_backend
from app.memory import repository as repo


def _make_llm() -> LLM:
    backend = resolve_llm_backend()
    if backend.kind == "local":
        return LLM(model=f"openai/{backend.model}", base_url=backend.base_url, api_key=backend.api_key)
    if backend.kind == "openai":
        return LLM(model=f"openai/{backend.model}", api_key=backend.api_key)
    return LLM(model=f"anthropic/{backend.model}", api_key=backend.api_key)


def _comparison_to_prior_visit(site_id: str, mission_id: str) -> str:
    priors = repo.get_prior_missions(site_id, exclude_mission_id=mission_id, limit=1)
    if not priors:
        return "No prior mission on record for this site — this is the first visit."
    prior = priors[0]
    prior_findings = repo.get_mission_findings(prior.id)
    unresolved = [f for f in prior_findings if f.status == "unresolved"]
    return (
        f"Prior mission {prior.id} on {prior.started_at.date()} recorded {len(prior_findings)} "
        f"finding(s), of which {len(unresolved)} remain unresolved."
    )


def generate_report(mission_id: str, site_id: str, operator_goal: str) -> dict:
    findings = repo.get_mission_findings(mission_id)
    findings_dicts = [{
        "id": f.id, "waypoint_id": f.waypoint_id, "finding_type": f.finding_type,
        "severity": f.severity, "confidence": f.confidence, "verifier_outcome": f.verifier_outcome,
        "image_file": f.image_file,
    } for f in findings]

    pending_approvals = repo.get_pending_approvals(mission_id=mission_id)
    comparison = _comparison_to_prior_visit(site_id, mission_id)
    llm = _make_llm()

    analyst = Agent(
        role="Findings Analyst",
        goal="Compute an accurate quantitative summary of this mission's findings using the summary tool.",
        backstory="A meticulous data analyst for a drone inspection program who never estimates numbers by hand.",
        llm=llm, tools=[findings_summary_tool], verbose=False,
    )
    writer = Agent(
        role="Report Writer",
        goal="Write a clear, strictly evidence-based inspection report following the required SOP-009 format.",
        backstory="A technical writer who never states anything not backed by the findings table or approval log.",
        llm=llm, verbose=False,
    )

    analyst_task = Task(
        description=(
            f"Here is the JSON list of findings for mission {mission_id}:\n{json.dumps(findings_dicts)}\n"
            "Use the Findings Summary Tool to compute counts by severity and by finding_type. "
            "Report the tool's output exactly."
        ),
        expected_output="The JSON summary produced by the Findings Summary Tool.",
        agent=analyst,
    )
    writer_task = Task(
        description=(
            f"Site: {site_id}. Operator goal: {operator_goal!r}. Mission id: {mission_id}.\n"
            f"Findings table (JSON): {json.dumps(findings_dicts)}\n"
            f"Pending approvals: {len(pending_approvals)}\n"
            f"Comparison to prior visit: {comparison}\n\n"
            "Write the inspection report with these sections: Mission Summary, Findings Table, "
            "Quantitative Summary (use the Analyst's numbers exactly), Approval Log Excerpt, "
            "Comparison to Prior Visit. Do not invent findings not present in the data above."
        ),
        expected_output="A complete inspection report in the required SOP-009 sections.",
        agent=writer, context=[analyst_task],
    )

    crew = Crew(agents=[analyst, writer], tasks=[analyst_task, writer_task], process=Process.sequential, verbose=False)
    crew_output = crew.kickoff()

    return {
        "mission_id": mission_id,
        "site_id": site_id,
        "findings": findings_dicts,
        "computed_summary": compute_findings_summary(findings_dicts),  # ground truth, independent of the LLM's tool call
        "comparison_to_prior_visit": comparison,
        "pending_approvals": len(pending_approvals),
        "report_text": str(crew_output),
    }
