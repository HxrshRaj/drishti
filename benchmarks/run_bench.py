"""Phase 2 latency/throughput/accuracy benchmark.

This environment has no GPU (`nvidia-smi` is not present), so this script
measures real CPU numbers only: an fp32 CPU baseline (the only dtype this
model runs correctly in on CPU — bfloat16/float16 are not meaningfully
faster and are not well-supported for this architecture on CPU) and a
real image-resolution/max-pixels sweep, since that IS a meaningful CPU
lever. The fp16 baseline / 4-bit / 8-bit quantized / batch-size / vLLM
comparisons this phase would otherwise include are GPU-only in practice
(bitsandbytes quantization is CUDA-accelerated; vLLM targets GPU serving)
and are shipped instead as benchmarks/colab_bench.ipynb, to be run on a
free Colab/Kaggle GPU — see docs/benchmarks.md for exactly what is
measured here vs. pending a GPU run.

Usage:
    python benchmarks/run_bench.py --n 3
"""
from __future__ import annotations

import argparse
import gc
import json
import random
import sys
import time
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
from PIL import Image  # noqa: E402

from app.perception.vlm import VLMPerceptionService  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
LABELS_FILE = ROOT / "data" / "labels" / "labels.jsonl"
IMAGES_DIR = ROOT / "data" / "images"


def run_config(images: list[Image.Image], resize_to: tuple[int, int] | None, label: str) -> dict:
    gc.collect()
    service = VLMPerceptionService()  # fresh instance per config: honest peak-memory isolation

    prepped = [im.resize(resize_to, Image.BILINEAR) if resize_to else im for im in images]

    # warmup (discarded, per correct-timing instructions)
    _ = service.analyze(prepped[0])

    latencies = []
    peak_mem_bytes = 0
    for im in prepped:
        if service.device == "cuda":
            torch.cuda.reset_peak_memory_stats()
            torch.cuda.synchronize()
        t0 = time.perf_counter()
        service.analyze(im)
        if service.device == "cuda":
            torch.cuda.synchronize()
            peak_mem_bytes = max(peak_mem_bytes, torch.cuda.max_memory_allocated())
        latencies.append((time.perf_counter() - t0) * 1000)

    latencies.sort()
    return {
        "config": label,
        "device": service.device,
        "resize_to": list(resize_to) if resize_to else "native",
        "n_images": len(prepped),
        "latency_ms_p50": latencies[len(latencies) // 2],
        "latency_ms_p95": latencies[int(len(latencies) * 0.95)] if len(latencies) > 1 else latencies[0],
        "latency_ms_mean": sum(latencies) / len(latencies),
        "throughput_img_per_s": 1000.0 / (sum(latencies) / len(latencies)),
        "peak_gpu_memory_mb": (peak_mem_bytes / 1e6) if service.device == "cuda" else None,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=3)
    ap.add_argument("--seed", type=int, default=5)
    ap.add_argument("--out", type=str, default=str(ROOT / "benchmarks" / "results" / "bench_results.json"))
    args = ap.parse_args()

    records = [json.loads(l) for l in LABELS_FILE.read_text(encoding="utf-8").splitlines() if l.strip()]
    rng = random.Random(args.seed)
    sample_recs = rng.sample(records, args.n)
    images = [Image.open(IMAGES_DIR / r["file"]).convert("RGB") for r in sample_recs]
    native_size = images[0].size

    print(f"Benchmarking on {len(images)} images. Native size (first image): {native_size}")
    print("Hardware: CPU only (no GPU detected in this environment — torch.cuda.is_available() == False)\n")

    configs = [
        {"label": "fp32_native_resolution", "resize_to": None},
        {"label": "fp32_half_resolution", "resize_to": (native_size[0] // 2, native_size[1] // 2)},
    ]

    results = []
    for cfg in configs:
        print(f"Running config: {cfg['label']} ...")
        r = run_config(images, cfg["resize_to"], cfg["label"])
        results.append(r)
        print(f"  p50={r['latency_ms_p50']:.0f}ms p95={r['latency_ms_p95']:.0f}ms throughput={r['throughput_img_per_s']:.3f} img/s")

    output = {
        "hardware": "CPU only (no GPU available in this environment)",
        "n_images": len(images), "seed": args.seed, "native_resolution": list(native_size),
        "configs": results,
        "note": (
            "fp16/4-bit/8-bit/batch-size/vLLM comparisons are GPU-only in "
            "practice here and are shipped as benchmarks/colab_bench.ipynb, "
            "pending a user GPU run — see docs/benchmarks.md."
        ),
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(f"\nWrote {args.out}")


if __name__ == "__main__":
    main()
