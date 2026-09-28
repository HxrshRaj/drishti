"""Builds perception_eval.json (the accuracy + latency summary the
frontend Metrics page and docs/benchmarks.md read) from an existing
manual_check run's raw output, so a slow re-run isn't required just to
get a summary of data already collected for real.

Usage:
    python benchmarks/summarize_manual_check.py --in benchmarks/results/manual_check_20.jsonl
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from parity import is_correct  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="in_path", type=str, default=str(ROOT / "benchmarks" / "results" / "manual_check_20.jsonl"))
    ap.add_argument("--out", type=str, default=str(ROOT / "benchmarks" / "results" / "perception_eval.json"))
    ap.add_argument("--model-id", type=str, default="HuggingFaceTB/SmolVLM-256M-Instruct")
    ap.add_argument("--device", type=str, default="cpu")
    args = ap.parse_args()

    lines = [json.loads(l) for l in Path(args.in_path).read_text(encoding="utf-8").splitlines() if l.strip()]
    n = len(lines)
    n_parse_failed = sum(1 for r in lines if r.get("parse_failed"))
    scored = [r for r in lines if not r.get("parse_failed") and r.get("finding")]
    n_correct = sum(1 for r in scored if is_correct(r["finding"]["finding_type"], set(r["gt_classes"])))
    overall_accuracy = n_correct / len(scored) if scored else 0.0

    latencies = sorted(r["latency_ms"] for r in lines)
    p50 = latencies[len(latencies) // 2]
    p95 = latencies[int(len(latencies) * 0.95)] if len(latencies) > 1 else latencies[0]

    summary = {
        "source": Path(args.in_path).name,
        "n_images": n,
        "model_id": args.model_id,
        "device": args.device,
        "parse_failures": n_parse_failed,
        "parse_failure_rate": n_parse_failed / n if n else 0.0,
        "overall_accuracy": overall_accuracy,
        "accuracy_note": (
            "Coarse presence-detection accuracy (does the finding_type's coarse "
            "category — vehicle/personnel/none — match ground truth), not a "
            "closed-set classification accuracy. See docs/limitations.md: in "
            "this sample the model defaults to vehicle_presence for nearly "
            "every image, and nearly every VisDrone image contains a vehicle, "
            "so this number is inflated by class imbalance, not a sign of "
            "strong discrimination — reported honestly, not celebrated."
        ),
        "latency_ms_p50": p50,
        "latency_ms_p95": p95,
        "latency_ms_mean": sum(latencies) / len(latencies),
        "latency_ms_min": latencies[0],
        "latency_ms_max": latencies[-1],
    }

    Path(args.out).write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"\nWrote {args.out}")


if __name__ == "__main__":
    main()
