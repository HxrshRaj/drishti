"""Canonical VLM accuracy + parity eval (Tests & CI requirement: "an eval
script for VLM accuracy... that prints real metrics"). Runs the real
two-stage perception pipeline over a sample of the licensed dataset,
scores coarse presence-detection accuracy against VisDrone ground truth,
and writes both a plain accuracy summary and the full parity breakdown in
one pass (so the expensive model run happens once).

Usage:
    python benchmarks/eval_perception.py --n 40 --seed 11
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from parity import brightness_bin, compute_parity_report, resolution_bin, scene_mix  # noqa: E402
from PIL import Image  # noqa: E402

from app.perception.vlm import VLMPerceptionService  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
LABELS_FILE = ROOT / "data" / "labels" / "labels.jsonl"
IMAGES_DIR = ROOT / "data" / "images"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=40)
    ap.add_argument("--seed", type=int, default=11)
    ap.add_argument("--out-eval", type=str, default=str(ROOT / "benchmarks" / "results" / "perception_eval.json"))
    ap.add_argument("--out-parity", type=str, default=str(ROOT / "benchmarks" / "results" / "parity_report.json"))
    ap.add_argument("--out-raw", type=str, default=str(ROOT / "benchmarks" / "results" / "perception_eval_raw.jsonl"))
    args = ap.parse_args()

    records = [json.loads(l) for l in LABELS_FILE.read_text(encoding="utf-8").splitlines() if l.strip()]
    rng = random.Random(args.seed)
    sample = rng.sample(records, min(args.n, len(records)))

    print(f"Loading VLM service for {len(sample)} images...")
    service = VLMPerceptionService()
    print(f"Model: {service.model_id} on {service.device}\n")

    parity_records = []
    latencies = []
    raw_f = open(args.out_raw, "w", encoding="utf-8")

    t_start = time.time()
    for i, rec in enumerate(sample, 1):
        image = Image.open(IMAGES_DIR / rec["file"]).convert("RGB")
        gt = {d["label"] for d in rec["detections"]}
        result = service.analyze(image)
        latencies.append(result.latency_ms)

        finding_type = result.finding.finding_type if result.finding else "PARSE_FAILED"
        parity_records.append({
            "file": rec["file"], "finding_type": finding_type, "gt_labels": list(gt),
            "brightness_bin": brightness_bin(image), "resolution_bin": resolution_bin(*image.size),
            "scene_mix": scene_mix(gt),
        })
        raw_f.write(json.dumps({
            "file": rec["file"], "gt_labels": list(gt), "parse_failed": result.parse_failed,
            "finding": result.finding.model_dump(mode="json") if result.finding else None,
            "latency_ms": result.latency_ms,
        }) + "\n")
        raw_f.flush()
        if i % 5 == 0 or i == len(sample):
            elapsed = time.time() - t_start
            print(f"  [{i}/{len(sample)}] elapsed={elapsed:.0f}s last_latency={result.latency_ms:.0f}ms")

    raw_f.close()

    # exclude parse failures from the accuracy/parity computation itself,
    # but report the parse-failure rate honestly alongside it
    n_parse_failed = sum(1 for r in parity_records if r["finding_type"] == "PARSE_FAILED")
    scored_records = [r for r in parity_records if r["finding_type"] != "PARSE_FAILED"]

    parity_report = compute_parity_report(scored_records)
    parity_report["source"] = "eval_perception.py"
    parity_report["n_parse_failed_excluded"] = n_parse_failed

    lat_sorted = sorted(latencies)
    p50 = lat_sorted[len(lat_sorted) // 2]
    p95 = lat_sorted[int(len(lat_sorted) * 0.95)] if len(lat_sorted) > 1 else lat_sorted[0]

    eval_summary = {
        "n_images": len(sample), "seed": args.seed, "device": service.device, "model_id": service.model_id,
        "parse_failures": n_parse_failed, "parse_failure_rate": n_parse_failed / len(sample),
        "overall_accuracy": parity_report["overall_accuracy"],
        "latency_ms_p50": p50, "latency_ms_p95": p95,
        "latency_ms_mean": sum(latencies) / len(latencies),
        "total_wall_time_s": time.time() - t_start,
    }

    Path(args.out_eval).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out_eval).write_text(json.dumps(eval_summary, indent=2), encoding="utf-8")
    Path(args.out_parity).write_text(json.dumps(parity_report, indent=2), encoding="utf-8")

    print("\n=== Eval summary ===")
    print(json.dumps(eval_summary, indent=2))
    print(f"\nWrote {args.out_eval}\nWrote {args.out_parity}\nWrote {args.out_raw}")


if __name__ == "__main__":
    main()
