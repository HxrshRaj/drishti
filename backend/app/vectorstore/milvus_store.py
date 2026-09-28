"""Milvus-backed VectorStore. Works unmodified against Milvus Lite
(embedded, MILVUS_URI is a local file path — the default for `docker
compose`-free local dev) and Milvus standalone (MILVUS_URI is an
http:// endpoint, e.g. the docker-compose stack in this repo) because
pymilvus's MilvusClient exposes the same API for both deployment modes.
"""
from __future__ import annotations

import json
from pathlib import Path

from pymilvus import MilvusClient

from app.vectorstore.base import VectorHit, VectorStore


class MilvusVectorStore(VectorStore):
    def __init__(self, uri: str):
        if uri.endswith(".db"):
            Path(uri).parent.mkdir(parents=True, exist_ok=True)
        self.client = MilvusClient(uri=uri)

    def ensure_collection(self, collection: str, dim: int) -> None:
        if self.client.has_collection(collection):
            return
        self.client.create_collection(
            collection_name=collection,
            dimension=dim,
            primary_field_name="id",
            id_type="string",
            max_length=256,
            vector_field_name="vector",
            metric_type="COSINE",
            auto_id=False,
            enable_dynamic_field=True,
        )
        self.client.load_collection(collection)

    def upsert(self, collection: str, ids: list[str], vectors: list[list[float]],
               texts: list[str], metadatas: list[dict]) -> None:
        rows = []
        for _id, vec, text, meta in zip(ids, vectors, texts, metadatas, strict=True):
            row = {"id": _id, "vector": vec, "text": text, "metadata_json": json.dumps(meta)}
            # flatten a few commonly-filtered scalar keys as real dynamic fields
            for key in ("site_id", "doc_id", "kind"):
                if key in meta:
                    row[key] = meta[key]
            rows.append(row)
        self.client.upsert(collection_name=collection, data=rows)

    def query(self, collection: str, vector: list[float], top_k: int = 5,
              metadata_filter: dict | None = None) -> list[VectorHit]:
        if not self.client.has_collection(collection):
            # Real, expected condition on a fresh install before ingestion
            # has run — SOP-008 treats "no SOP context retrieved" as a soft
            # flag, not a crash.
            return []
        # A collection created by a different process/session (e.g. the
        # ingest script) persists to disk but isn't loaded into this
        # client's memory yet — load is idempotent and cheap once warm.
        self.client.load_collection(collection)
        expr = None
        if metadata_filter:
            clauses = [f'{k} == "{v}"' for k, v in metadata_filter.items()]
            expr = " and ".join(clauses)
        results = self.client.search(
            collection_name=collection, data=[vector], limit=top_k,
            filter=expr, output_fields=["text", "metadata_json"],
        )
        hits = []
        for hit in results[0]:
            entity = hit.get("entity", {})
            meta = json.loads(entity.get("metadata_json", "{}"))
            hits.append(VectorHit(id=str(hit["id"]), score=float(hit["distance"]),
                                   text=entity.get("text", ""), metadata=meta))
        return hits

    def delete(self, collection: str, ids: list[str]) -> None:
        self.client.delete(collection_name=collection, ids=ids)

    def count(self, collection: str) -> int:
        if not self.client.has_collection(collection):
            return 0
        stats = self.client.get_collection_stats(collection)
        return int(stats.get("row_count", 0))
