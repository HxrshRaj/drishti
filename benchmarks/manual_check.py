"""Phase 1 verification helper: run the VLM perception service on N real
sampled images and print its JSON finding next to the VisDrone ground-truth
detections for that image, so the outputs can be checked by hand.

Usage:
    python benchmarks/manual_check.py --n 20 --seed 3
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from PIL import Image  # noqa: E402

from app.perception.vlm import VLMPerceptionService  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
LABELS_FILE = ROOT / "data" / "labels" / "labels.jsonl"
IMAGES_DIR = ROOT / "data" / "images"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--seed", type=int, default=3)
    ap.add_argument("--out", type=str, default=None, help="optional JSONL output path")
    args = ap.parse_args()

    records = [json.loads(line) for line in LABELS_FILE.read_text(encoding="utf-8").splitlines() if line.strip()]
    rng = random.Random(args.seed)
    sample = rng.sample(records, min(args.n, len(records)))

    print("Loading VLM service...")
    service = VLMPerceptionService()
    print(f"Model: {service.model_id} on {service.device}\n")

    out_f = open(args.out, "w", encoding="utf-8") if args.out else None
    for i, rec in enumerate(sample, 1):
        img_path = IMAGES_DIR / rec["file"]
        image = Image.open(img_path).convert("RGB")
        result = service.analyze(image)

        gt_classes = sorted({d["label"] for d in rec["detections"]})
        print(f"[{i}/{len(sample)}] {rec['file']}")
        print(f"  ground truth classes: {gt_classes} ({len(rec['detections'])} boxes)")
        if result.parse_failed:
            print(f"  VLM: PARSE FAILED after {result.attempts} attempt(s). raw={result.raw_output[:200]!r}")
        else:
            f = result.finding
            print(f"  VLM: type={f.finding_type!r} severity={f.severity.value} confidence={f.confidence:.2f}")
            print(f"       location={f.location_description!r}")
        print(f"  latency={result.latency_ms:.0f}ms\n")

        if out_f:
            out_f.write(json.dumps({
                "file": rec["file"], "gt_classes": gt_classes, "gt_count": len(rec["detections"]),
                "parse_failed": result.parse_failed,
                "finding": result.finding.model_dump() if result.finding else None,
                "latency_ms": result.latency_ms,
            }) + "\n")

    if out_f:
        out_f.close()
    print("Metrics:", service.metrics())


if __name__ == "__main__":
    main()
