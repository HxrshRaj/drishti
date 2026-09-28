"""Serves the real benchmark/eval/parity JSON artifacts this project
produced (benchmarks/results/) to the frontend's Metrics page — never
invented numbers, only whatever the last real run actually wrote to disk.
"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/metrics", tags=["metrics"])

RESULTS_DIR = Path(__file__).resolve().parents[3] / "benchmarks" / "results"


def _read(name: str) -> dict:
    path = RESULTS_DIR / name
    if not path.exists():
        raise HTTPException(404, detail=f"{name} has not been generated yet — run the corresponding benchmark/eval script")
    return json.loads(path.read_text(encoding="utf-8"))


@router.get("/retrieval")
def retrieval_eval():
    return _read("retrieval_eval.json")


@router.get("/perception")
def perception_eval():
    return _read("perception_eval.json")


@router.get("/bench")
def latency_bench():
    return _read("bench_results.json")


@router.get("/parity")
def parity_report():
    return _read("parity_report.json")


@router.get("/manifest")
def manifest():
    """Lists which real results files currently exist, so the frontend can
    show "not run yet" instead of erroring on missing endpoints.
    """
    known = ["retrieval_eval.json", "perception_eval.json", "bench_results.json", "parity_report.json"]
    return {name: (RESULTS_DIR / name).exists() for name in known}
