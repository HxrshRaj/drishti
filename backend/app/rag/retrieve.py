from __future__ import annotations

from app.rag.ingest import SOPS_COLLECTION
from app.vectorstore.base import VectorHit
from app.vectorstore.embeddings import embed_query
from app.vectorstore.factory import get_vector_store


def retrieve_sops(query: str, top_k: int = 4) -> list[VectorHit]:
    store = get_vector_store()
    vector = embed_query(query)
    return store.query(SOPS_COLLECTION, vector, top_k=top_k)


def format_context(hits: list[VectorHit]) -> str:
    if not hits:
        return ""
    lines = []
    for h in hits:
        title = h.metadata.get("title", h.metadata.get("doc_id", "SOP"))
        lines.append(f"[{title}] {h.text}")
    return "\n".join(lines)
