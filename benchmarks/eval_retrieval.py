"""Phase 3 verification: recall@k for SOP retrieval against the hand-labeled
query set in data/eval/retrieval_queries.jsonl.

Usage:
    python benchmarks/eval_retrieval.py --k 1 3 5
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.rag.ingest import ingest_sops  # noqa: E402
from app.rag.retrieve import retrieve_sops  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
QUERIES_FILE = ROOT / "data" / "eval" / "retrieval_queries.jsonl"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, nargs="+", default=[1, 3, 5])
    ap.add_argument("--out", type=str, default=str(ROOT / "benchmarks" / "results" / "retrieval_eval.json"))
    args = ap.parse_args()

    n_chunks = ingest_sops()
    print(f"Ingested {n_chunks} SOP chunks.\n")

    queries = [json.loads(line) for line in QUERIES_FILE.read_text(encoding="utf-8").splitlines() if line.strip()]
    max_k = max(args.k)

    per_query = []
    for q in queries:
        hits = retrieve_sops(q["query"], top_k=max_k)
        retrieved_doc_ids = [h.metadata.get("doc_id") for h in hits]
        ranks = {k: q["expected_doc_id"] in retrieved_doc_ids[:k] for k in args.k}
        per_query.append({
            "query": q["query"], "expected": q["expected_doc_id"],
            "retrieved_top1": retrieved_doc_ids[0] if retrieved_doc_ids else None,
            "hit": ranks,
        })

    recall_at_k = {}
    for k in args.k:
        hits = sum(1 for pq in per_query if pq["hit"][k])
        recall_at_k[k] = hits / len(per_query) if per_query else 0.0

    print("Recall@k:")
    for k in args.k:
        print(f"  k={k}: {recall_at_k[k]:.3f}  ({sum(1 for pq in per_query if pq['hit'][k])}/{len(per_query)})")

    misses = [pq for pq in per_query if not pq["hit"][max_k]]
    if misses:
        print(f"\nMissed at k={max_k} (top-1 shown):")
        for m in misses:
            print(f"  '{m['query']}' -> expected {m['expected']}, got {m['retrieved_top1']}")

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps({
        "n_queries": len(per_query), "n_sop_chunks": n_chunks,
        "recall_at_k": {str(k): v for k, v in recall_at_k.items()},
        "per_query": per_query,
    }, indent=2), encoding="utf-8")
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
