import json

from app.agentkit.evals.reference_model import ReferenceModel
from app.agentkit.evals.runner import (
    BASELINE,
    aggregate,
    load_dataset,
    log_to_mlflow,
    main,
    regressions,
    run_suite,
    ungrounded_facts,
)
from app.agentkit.types import ToolCall


def test_dataset_is_well_formed():
    cases = load_dataset()
    assert len(cases) >= 20 and len({c["id"] for c in cases}) == len(cases)
    assert all(c["expected_tools"] and c["answer_contains"] for c in cases)
    assert any(c.get("needs_approval") for c in cases) and any(c.get("forbidden_tools") for c in cases)


def test_reference_model_passes_and_matches_committed_baseline():
    metrics, _ = run_suite(ReferenceModel())
    assert metrics["task_completion"] == 1.0 and metrics["hallucination_rate"] == 0.0
    assert regressions(metrics, json.loads(BASELINE.read_text())["metrics"]) == []


class WrongPriority(ReferenceModel):
    """A degraded variant: a 'prompt change' that makes the model drop requested priorities."""
    name = "degraded-priority"

    def plan(self, task):
        return [ToolCall(c.id, c.name, {**c.args, **({"priority": "normal"} if c.name == "create_ticket" else {})})
                for c in super().plan(task)]


class OverEager(ReferenceModel):
    """Degraded: opens a ticket on every policy question, which the safe cases forbid."""
    name = "degraded-overeager"

    def plan(self, task):
        calls = super().plan(task)
        if calls and calls[0].name in ("get_policy", "get_invoice", "find_customer"):
            calls.append(ToolCall("extra", "create_ticket", {"title": "auto", "priority": "normal"}))
        return calls


class Inventive(ReferenceModel):
    """Degraded: adds a made-up figure to its answer."""
    name = "degraded-inventive"

    def render(self, raw):
        return super().render(raw) + " (saves 17% fees)"


def test_gate_catches_wrong_arguments():
    metrics, _ = run_suite(WrongPriority())
    assert metrics["arg_accuracy"] < 1.0
    assert any(m.startswith("arg_accuracy") for m in regressions(metrics, json.loads(BASELINE.read_text())["metrics"]))


def test_gate_catches_forbidden_tool_use_and_lower_precision():
    metrics, results = run_suite(OverEager())
    assert metrics["forbidden_tool_rate"] > 0 and metrics["tool_precision"] < 1.0
    bad = regressions(metrics, json.loads(BASELINE.read_text())["metrics"])
    assert any(b.startswith("forbidden_tool_rate") for b in bad) and any(b.startswith("tool_precision") for b in bad)


def test_hallucination_metric_flags_ungrounded_numbers():
    metrics, results = run_suite(Inventive())
    assert metrics["hallucination_rate"] == 1.0
    assert ungrounded_facts("fee 17 on INV-1001", "refund INV-1001", [{"x": 1}]) == ["17"]
    assert ungrounded_facts("paid 90.5", "how much", [{"amount": 90.5}]) == []


def test_cli_returns_nonzero_on_regression(monkeypatch, capsys):
    import app.agentkit.evals.runner as r
    monkeypatch.setattr(r, "_build_model", lambda kind: WrongPriority())
    assert main(["--model", "reference"]) == 1
    assert "REGRESSION" in capsys.readouterr().out


def test_aggregate_handles_latency_and_tokens():
    _, results = run_suite(ReferenceModel())
    agg = aggregate(results)
    assert agg["avg_tokens"] > 0 and agg["p50_latency_ms"] >= 0


def test_metrics_are_logged_to_mlflow(tmp_path):
    import mlflow

    uri = f"sqlite:///{tmp_path}/mlflow.db"
    metrics, _ = run_suite(ReferenceModel())
    run_id = log_to_mlflow("reference-rules", metrics, tracking_uri=uri)
    logged = mlflow.get_run(run_id).data
    assert logged.metrics["task_completion"] == 1.0 and logged.params["model"] == "reference-rules"
