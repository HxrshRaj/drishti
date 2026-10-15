"""Evaluation runner for agents built on the harness.

Measures, per case and in aggregate: tool selection precision and recall, argument
accuracy, task completion, hallucination rate (numbers/ids in the answer that appear
in neither the task nor any tool result), steps, tokens and latency. A baseline file
turns it into a regression gate for prompt / model / workflow changes.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..harness import AgentHarness
from ..middleware import ErrorToMessage, ToolRetry
from ..tracing import configure_tracing, get_memory_exporter, summarize_spans
from ..types import ChatModel
from .reference_model import ReferenceModel
from .toolset import build_tools

HERE = Path(__file__).parent
DATASET = HERE / "dataset.jsonl"
BASELINE = HERE / "baseline.json"
HIGHER_BETTER = ["tool_precision", "tool_recall", "arg_accuracy", "task_completion"]
LOWER_BETTER = ["hallucination_rate", "forbidden_tool_rate"]
TOLERANCE = 0.02

_FACT = re.compile(r"INV-\d+|T-\d+|[\w.]+@[\w.]+\.\w+|\d+(?:\.\d+)?")


def load_dataset(path: Path = DATASET) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def ungrounded_facts(answer: str, task: str, tool_results: list[Any]) -> list[str]:
    source = task + " " + json.dumps(tool_results, default=str)
    return [f for f in _FACT.findall(answer) if f not in source and f.rstrip("0").rstrip(".") not in source]


def _args_match(expected: dict[str, dict], trace: list[dict]) -> bool:
    for tool, want in expected.items():
        hits = [t for t in trace if t["tool"] == tool]
        if not any(all(h["args"].get(k) == v for k, v in want.items()) for h in hits):
            return False
    return True


@dataclass
class CaseResult:
    id: str
    tools_called: list[str]
    precision: float
    recall: float
    args_ok: bool
    completed: bool
    forbidden_used: bool
    ungrounded: list[str]
    steps: int
    tokens: int
    latency_ms: float
    status: str


def run_case(case: dict[str, Any], model: ChatModel) -> CaseResult:
    sink: list = []
    harness = AgentHarness(model, build_tools(sink), [ErrorToMessage(), ToolRetry(max_attempts=2)],
                           granted_permissions={"read", "write"}, max_steps=6)
    t0 = time.perf_counter()
    result = harness.run(case["task"], run_id=f"eval-{case['id']}")
    while result.status == "awaiting_approval":  # the eval plays the human reviewer: approves every request
        result = harness.resume(result.run_id, approve={result.pending_call.id: True})
    latency = (time.perf_counter() - t0) * 1000
    called = [t["tool"] for t in result.tool_trace]
    want, got = set(case["expected_tools"]), set(called)
    precision = len(want & got) / len(got) if got else 0.0
    recall = len(want & got) / len(want)
    forbidden = bool(got & set(case.get("forbidden_tools", [])))
    answer_ok = all(s.lower() in result.answer.lower() for s in case["answer_contains"])
    return CaseResult(
        case["id"], called, precision, recall, _args_match(case["expected_args"], result.tool_trace),
        result.status == "completed" and answer_ok and not forbidden, forbidden,
        ungrounded_facts(result.answer, case["task"], [t["result"] for t in result.tool_trace]),
        result.steps, result.usage.input_tokens + result.usage.output_tokens, latency, result.status)


def aggregate(results: list[CaseResult]) -> dict[str, float]:
    n = len(results)
    return {
        "cases": n,
        "tool_precision": sum(r.precision for r in results) / n,
        "tool_recall": sum(r.recall for r in results) / n,
        "arg_accuracy": sum(r.args_ok for r in results) / n,
        "task_completion": sum(r.completed for r in results) / n,
        "hallucination_rate": sum(bool(r.ungrounded) for r in results) / n,
        "forbidden_tool_rate": sum(r.forbidden_used for r in results) / n,
        "avg_steps": sum(r.steps for r in results) / n,
        "avg_tokens": sum(r.tokens for r in results) / n,
        "p50_latency_ms": sorted(r.latency_ms for r in results)[n // 2],
    }


def regressions(current: dict[str, float], baseline: dict[str, float], tol: float = TOLERANCE) -> list[str]:
    bad = []
    for m in HIGHER_BETTER:
        if current[m] < baseline[m] - tol:
            bad.append(f"{m}: {baseline[m]:.3f} -> {current[m]:.3f}")
    for m in LOWER_BETTER:
        if current[m] > baseline[m] + tol:
            bad.append(f"{m}: {baseline[m]:.3f} -> {current[m]:.3f}")
    return bad


def run_suite(model: ChatModel, dataset: Path = DATASET) -> tuple[dict[str, float], list[CaseResult]]:
    configure_tracing(in_memory=True)
    exp = get_memory_exporter()
    exp.clear()
    results = [run_case(c, model) for c in load_dataset(dataset)]
    metrics = aggregate(results)
    trace = summarize_spans(list(exp.get_finished_spans()))
    metrics["trace_tool_errors"] = trace["tool_errors"]
    return metrics, results


def log_to_mlflow(model_name: str, metrics: dict[str, float], tracking_uri: str | None = None) -> str:
    import mlflow

    if tracking_uri:
        mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_experiment("drishti-agent-evals")
    with mlflow.start_run(run_name=model_name) as run:
        mlflow.log_param("model", model_name)
        mlflow.log_param("dataset_cases", int(metrics["cases"]))
        mlflow.log_metrics({k: float(v) for k, v in metrics.items() if k != "cases"})
        return run.info.run_id


def _build_model(kind: str) -> ChatModel:
    import os

    from ..llm_openai import OpenAICompatModel

    if kind == "reference":
        return ReferenceModel()
    if kind == "openai":
        return OpenAICompatModel(os.environ.get("OPENAI_MODEL", "gpt-4o-mini"), "https://api.openai.com/v1", os.environ["OPENAI_API_KEY"])
    if kind == "azure":
        return OpenAICompatModel.azure(os.environ["AZURE_OPENAI_ENDPOINT"], os.environ["AZURE_OPENAI_DEPLOYMENT"],
                                       os.environ["AZURE_OPENAI_API_KEY"], os.environ.get("AZURE_OPENAI_API_VERSION", "2024-10-21"))
    if kind == "ollama":
        return OpenAICompatModel(os.environ.get("OLLAMA_MODEL", "qwen2.5:7b"), "http://localhost:11434/v1", "ollama")
    raise SystemExit(f"unknown model kind {kind}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", default="reference", choices=["reference", "openai", "azure", "ollama"])
    ap.add_argument("--baseline", type=Path, default=BASELINE)
    ap.add_argument("--update-baseline", action="store_true")
    ap.add_argument("--mlflow", action="store_true", help="log metrics to MLflow (MLFLOW_TRACKING_URI or ./mlruns)")
    args = ap.parse_args(argv)
    model = _build_model(args.model)
    metrics, results = run_suite(model)
    for r in results:
        flag = "ok " if r.completed else "FAIL"
        print(f"{flag} {r.id:8s} tools={r.tools_called} args_ok={r.args_ok} steps={r.steps}")
    print(json.dumps({k: round(v, 3) for k, v in metrics.items()}, indent=2))
    if args.mlflow:
        print("mlflow run:", log_to_mlflow(model.name, metrics))
    if args.update_baseline:
        args.baseline.write_text(json.dumps({"model": model.name, "metrics": metrics}, indent=2) + "\n")
        print("baseline written")
        return 0
    if args.baseline.exists():
        base = json.loads(args.baseline.read_text())["metrics"]
        bad = regressions(metrics, base)
        if bad:
            print("REGRESSION vs baseline:\n  " + "\n  ".join(bad))
            return 1
        print("no regression vs baseline")
    return 0


if __name__ == "__main__":
    sys.exit(main())
