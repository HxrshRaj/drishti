"""Sample a licensed subset of VisDrone2019-DET for the Drishti demo.

Source: Voxel51/VisDrone2019-DET on the Hugging Face Hub (a FiftyOne
re-packaging of the official VisDrone2019-DET benchmark from the AISKYEYE
team, Tianjin University). See docs/data.md for the full license discussion:
the dataset is CC BY-NC-SA 3.0 (attribution, non-commercial, share-alike).

This script downloads samples.json (the FiftyOne label export) and a
stratified sample of the referenced JPEGs, then writes:
  - data/images/<filename>.jpg
  - data/labels/labels.jsonl   (one record per image: split, width, height,
    detections[{label, bbox_xywh_px, truncation, occlusion}])
  - data/labels/class_counts.json

Usage:
    python benchmarks/fetch_dataset.py --n 350 --seed 7
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
from collections import Counter
from pathlib import Path

import requests

REPO = "Voxel51/VisDrone2019-DET"
SAMPLES_URL = f"https://huggingface.co/datasets/{REPO}/resolve/main/samples.json"
IMAGE_URL_TMPL = f"https://huggingface.co/datasets/{REPO}/resolve/main/{{filepath}}"

ROOT = Path(__file__).resolve().parent.parent
RAW_CACHE = ROOT / "data" / "raw_cache"
IMAGES_DIR = ROOT / "data" / "images"
LABELS_DIR = ROOT / "data" / "labels"

REAL_CLASSES = {
    "car", "van", "truck", "bus", "pedestrian", "people",
    "bicycle", "motor", "tricycle", "awning-tricycle",
}


def download(url: str, dest: Path, retries: int = 3) -> None:
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(url, timeout=60)
            resp.raise_for_status()
            dest.write_bytes(resp.content)
            return
        except requests.RequestException as exc:
            if attempt == retries:
                raise
            print(f"  retry {attempt}/{retries} for {url}: {exc}", file=sys.stderr)
            time.sleep(2 * attempt)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=350, help="number of images to sample")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--min-detections", type=int, default=2,
                     help="minimum non-ignored detections required to keep an image")
    args = ap.parse_args()

    RAW_CACHE.mkdir(parents=True, exist_ok=True)
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    LABELS_DIR.mkdir(parents=True, exist_ok=True)

    cache_path = RAW_CACHE / "samples.json"
    if not cache_path.exists():
        print(f"Downloading label export from {SAMPLES_URL} ...")
        download(SAMPLES_URL, cache_path)
    else:
        print(f"Using cached {cache_path}")

    data = json.loads(cache_path.read_text(encoding="utf-8"))
    samples = data["samples"]
    print(f"Loaded {len(samples)} labeled samples")

    # Keep only samples with a reasonable number of real (non ignore_regions,
    # non "others") detections, so the demo has meaningful findings.
    usable = []
    for s in samples:
        dets = s.get("ground_truth", {}).get("detections", []) or []
        real = [d for d in dets if d["label"] in REAL_CLASSES]
        if len(real) >= args.min_detections:
            usable.append((s, real))
    print(f"{len(usable)} samples have >= {args.min_detections} real-class detections")

    rng = random.Random(args.seed)
    rng.shuffle(usable)
    chosen = usable[: args.n]
    print(f"Sampling {len(chosen)} images (seed={args.seed})")

    labels_out = []
    class_counts: Counter[str] = Counter()
    split_counts: Counter[str] = Counter()

    for i, (s, real_dets) in enumerate(chosen, 1):
        filepath = s["filepath"]  # e.g. "data/0000002_..._d_0000014.jpg"
        fname = Path(filepath).name
        dest = IMAGES_DIR / fname
        if not dest.exists():
            url = IMAGE_URL_TMPL.format(filepath=filepath)
            download(url, dest)
        if i % 25 == 0 or i == len(chosen):
            print(f"  [{i}/{len(chosen)}] {fname}")

        w = s["metadata"]["width"]
        h = s["metadata"]["height"]
        split = s["tags"][0] if s.get("tags") else "train"
        split_counts[split] += 1

        dets_px = []
        for d in real_dets:
            bx, by, bw, bh = d["bounding_box"]  # normalized xywh
            dets_px.append({
                "label": d["label"],
                "bbox_xywh_px": [
                    round(bx * w, 1), round(by * h, 1),
                    round(bw * w, 1), round(bh * h, 1),
                ],
                "truncation": d.get("truncation", 0),
                "occlusion": d.get("occlusion", 0),
            })
            class_counts[d["label"]] += 1

        labels_out.append({
            "file": fname,
            "split": split,
            "width": w,
            "height": h,
            "detections": dets_px,
            "source": "VisDrone2019-DET (via Voxel51 FiftyOne export on HF Hub)",
            "license": "CC BY-NC-SA 3.0",
        })

    labels_path = LABELS_DIR / "labels.jsonl"
    with labels_path.open("w", encoding="utf-8") as f:
        for rec in labels_out:
            f.write(json.dumps(rec) + "\n")

    (LABELS_DIR / "class_counts.json").write_text(
        json.dumps({
            "n_images": len(labels_out),
            "split_counts": dict(split_counts),
            "class_counts": dict(class_counts.most_common()),
            "seed": args.seed,
            "min_detections": args.min_detections,
        }, indent=2),
        encoding="utf-8",
    )

    print(f"\nWrote {len(labels_out)} label records to {labels_path}")
    print(f"Class counts: {dict(class_counts.most_common())}")
    print(f"Split counts: {dict(split_counts)}")
    print(f"Images saved to {IMAGES_DIR}")


if __name__ == "__main__":
    main()
