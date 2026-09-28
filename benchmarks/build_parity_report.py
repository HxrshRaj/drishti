"""Builds the real parity report (SOP-011 / Phase 5.4) from an existing
manual_check run's output (real VLM predictions), augmented with
brightness/resolution bins computed from the actual image files. Reuses
the expensive VLM run rather than requiring a second one.

Usage:
    python benchmarks/build_parity_report.py --in benchmarks/results/manual_check_20.jsonl
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from parity import brightness_bin, compute_parity_report, resolution_bin, scene_mix
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
IMAGES_DIR = ROOT / "data" / "images"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="in_path", type=str, default=str(ROOT / "benchmarks" / "results" / "manual_check_20.jsonl"))
    ap.add_argument("--out", type=str, default=str(ROOT / "benchmarks" / "results" / "parity_report.json"))
    args = ap.parse_args()

    lines = [json.loads(l) for l in Path(args.in_path).read_text(encoding="utf-8").splitlines() if l.strip()]

    records = []
    for rec in lines:
        if rec.get("parse_failed") or rec.get("finding") is None:
            continue
        image = Image.open(IMAGES_DIR / rec["file"]).convert("RGB")
        gt = set(rec["gt_classes"])
        records.append({
            "file": rec["file"],
            "finding_type": rec["finding"]["finding_type"],
            "gt_labels": list(gt),
            "brightness_bin": brightness_bin(image),
            "resolution_bin": resolution_bin(*image.size),
            "scene_mix": scene_mix(gt),
        })

    report = compute_parity_report(records)
    report["source_file"] = str(Path(args.in_path).name)
    report["n_parse_failed_excluded"] = len(lines) - len(records)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"n_total={report['n_total']} overall_accuracy={report['overall_accuracy']:.3f}")
    print(f"parse failures excluded: {report['n_parse_failed_excluded']}")
    print("\nGroup results:")
    for g in report["group_results"]:
        flag = " <-- LOW SAMPLE" if g["low_confidence_note"] else ""
        print(f"  {g['group_key']}={g['group_value']}: n={g['n']} accuracy={g['accuracy']:.3f}{flag}")
    if report["flags"]:
        print("\nFLAGGED (gap > threshold, sufficient samples):")
        for f in report["flags"]:
            print(f"  {f}")
    else:
        print("\nNo groups flagged (either no gap exceeded threshold, or all gapped groups had too few samples).")
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
