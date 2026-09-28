"""Pinecone-backed VectorStore, exercised live only when PINECONE_API_KEY
is set (see docs/limitations.md — otherwise this class is implemented but
its live-run verification is listed as pending, per the project's honesty
rules around credentials this environment does not have).
"""
from __future__ import annotations

from pinecone import Pinecone, ServerlessSpec

from app.vectorstore.base import VectorHit, VectorStore


class PineconeVectorStore(VectorStore):
    def __init__(self, api_key: str, cloud: str = "aws", region: str = "us-east-1"):
        self.pc = Pinecone(api_key=api_key)
        self.cloud = cloud
        self.region = region
        self._indexes: dict[str, object] = {}

    def _index(self, collection: str):
        if collection not in self._indexes:
            self._indexes[collection] = self.pc.Index(collection)
        return self._indexes[collection]

    def ensure_collection(self, collection: str, dim: int) -> None:
        existing = {idx["name"] for idx in self.pc.list_indexes()}
        if collection not in existing:
            self.pc.create_index(
                name=collection, dimension=dim, metric="cosine",
                spec=ServerlessSpec(cloud=self.cloud, region=self.region),
            )

    def upsert(self, collection: str, ids: list[str], vectors: list[list[float]],
               texts: list[str], metadatas: list[dict]) -> None:
        index = self._index(collection)
        payload = []
        for _id, vec, text, meta in zip(ids, vectors, texts, metadatas, strict=True):
            full_meta = {**meta, "text": text}
            payload.append({"id": _id, "values": vec, "metadata": full_meta})
        index.upsert(vectors=payload)

    def query(self, collection: str, vector: list[float], top_k: int = 5,
              metadata_filter: dict | None = None) -> list[VectorHit]:
        index = self._index(collection)
        pc_filter = {k: {"$eq": v} for k, v in (metadata_filter or {}).items()} or None
        result = index.query(vector=vector, top_k=top_k, include_metadata=True, filter=pc_filter)
        hits = []
        for match in result.get("matches", []):
            meta = dict(match.get("metadata", {}))
            text = meta.pop("text", "")
            hits.append(VectorHit(id=match["id"], score=float(match["score"]), text=text, metadata=meta))
        return hits

    def delete(self, collection: str, ids: list[str]) -> None:
        self._index(collection).delete(ids=ids)

    def count(self, collection: str) -> int:
        stats = self._index(collection).describe_index_stats()
        return int(stats.get("total_vector_count", 0))
