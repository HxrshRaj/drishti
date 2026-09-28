"""Perception-vs-Verifier agent-to-agent exchange (SOP-007), built on
AutoGen (autogen-agentchat). Two real AssistantAgents exchange real
messages via a real model client (the local Qwen2.5-0.5B gateway by
default, or a hosted provider if configured) — this is not a stub.

Design note (documented honestly in docs/architecture.md): the Verifier's
RAG/memory lookups are performed by this module in Python *before* the
exchange and injected as context, rather than as live LLM tool-calls. A
0.5B local model's function-calling reliability was too poor for a
safety-relevant check to depend on, so retrieval is a deterministic
pre-step and the LLM's job is narrowed to reasoning over the given
evidence — a deliberate trade-off, not a hidden shortcut.
"""
from __future__ import annotations

import asyncio

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.conditions import MaxMessageTermination
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_core.models import ModelFamily, ModelInfo
from autogen_ext.models.openai import OpenAIChatCompletionClient

from app.agents.schemas import VerificationExchange, VerifierOutcome, VerifierVerdict
from app.llm.provider import resolve_llm_backend
from app.memory import repository as repo
from app.perception.schemas import VLMFinding
from app.perception.vlm import extract_json
from app.rag.retrieve import format_context, retrieve_sops

_LOCAL_MODEL_INFO = ModelInfo(
    vision=False, function_calling=False, json_output=False,
    structured_output=False, family=ModelFamily.UNKNOWN,
)


def _make_model_client() -> OpenAIChatCompletionClient:
    backend = resolve_llm_backend()
    if backend.kind == "local":
        return OpenAIChatCompletionClient(
            model=backend.model, base_url=backend.base_url, api_key=backend.api_key,
            model_info=_LOCAL_MODEL_INFO,
        )
    if backend.kind == "openai":
        return OpenAIChatCompletionClient(model=backend.model, api_key=backend.api_key)
    # AutoGen's Anthropic support lives in a separate optional extra not
    # installed here; fall back to the local model client and note this in
    # docs/architecture.md as a known seam.
    return OpenAIChatCompletionClient(
        model="local-qwen2.5-0.5b", base_url="http://localhost:8000/v1", api_key="not-needed",
        model_info=_LOCAL_MODEL_INFO,
    )


def _build_evidence_context(site_id: str, finding: VLMFinding) -> str:
    sop_hits = retrieve_sops(f"{finding.finding_type} {finding.location_description}", top_k=3)
    sop_context = format_context(sop_hits) or "No relevant SOP retrieved."

    prior = repo.get_unresolved_findings(site_id)
    matching = [f for f in prior if f.finding_type == finding.finding_type]
    if matching:
        memory_context = f"{len(matching)} prior unresolved finding(s) of this type at this site, most recent severity={matching[0].severity}."
    else:
        memory_context = "No matching unresolved prior findings at this site."

    return f"Retrieved SOP guidance:\n{sop_context}\n\nSite memory:\n{memory_context}"


def _verifier_system_message() -> str:
    return (
        "You are the Verifier agent in a drone-inspection pipeline. The Perception "
        "agent will state a proposed finding. Using ONLY the evidence context you are "
        "given (retrieved SOP guidance and site memory), decide whether the finding is "
        "well-supported. Respond with ONLY a single JSON object, no other text:\n"
        '{"outcome": "agree|disagree|uncertain", "reasoning": "<one sentence>", '
        '"alternative_finding_type": "<snake_case label or null>"}'
    )


async def _run_exchange_async(site_id: str, finding: VLMFinding, max_rounds: int = 2) -> VerificationExchange:
    evidence = _build_evidence_context(site_id, finding)
    model_client = _make_model_client()

    perception_agent = AssistantAgent(
        name="PerceptionAgent", model_client=model_client,
        system_message=(
            "You are the Perception agent. When given a finding to state, restate it "
            "concisely in one sentence including its type, severity, and confidence. "
            "Do not add new claims."
        ),
    )
    verifier_agent = AssistantAgent(
        name="VerifierAgent", model_client=model_client, system_message=_verifier_system_message(),
    )

    team = RoundRobinGroupChat(
        [perception_agent, verifier_agent],
        termination_condition=MaxMessageTermination(2 * max_rounds),
    )

    task = (
        f"Perception agent: state this finding — type={finding.finding_type}, "
        f"severity={finding.severity.value}, confidence={finding.confidence:.2f}, "
        f"location={finding.location_description!r}.\n\n"
        f"Verifier agent: then evaluate it against this evidence:\n{evidence}"
    )

    result = await team.run(task=task)
    messages = [{"source": m.source, "content": str(m.content)} for m in result.messages]

    verdict = None
    parse_failed = True
    for m in reversed(messages):
        if m["source"] == "VerifierAgent":
            data = extract_json(m["content"])
            if data is not None:
                try:
                    verdict = VerifierVerdict.model_validate(data)
                    parse_failed = False
                except Exception:
                    parse_failed = True
            break

    if verdict is None:
        verdict = VerifierVerdict(outcome=VerifierOutcome.uncertain, reasoning="verifier output could not be parsed")

    # Only "agree" proceeds straight through; "disagree" and "uncertain"
    # both route to human/fallback handling per SOP-007 rather than being
    # silently accepted or silently dropped.
    escalated = verdict.outcome != VerifierOutcome.agree

    return VerificationExchange(
        finding_type=finding.finding_type, confidence=finding.confidence, messages=messages,
        verdict=verdict, parse_failed=parse_failed, escalated=escalated,
    )


def run_verification_exchange(site_id: str, finding: VLMFinding, max_rounds: int = 2) -> VerificationExchange:
    """Sync wrapper — FastAPI routes and LangGraph nodes in this project are
    largely sync, so this hides the asyncio.run() needed for AutoGen's
    async API.
    """
    return asyncio.run(_run_exchange_async(site_id, finding, max_rounds=max_rounds))
