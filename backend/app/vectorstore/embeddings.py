from __future__ import annotations

import threading

from sentence_transformers import SentenceTransformer

_MODEL_ID = "sentence-transformers/all-MiniLM-L6-v2"  # Apache-2.0, 384-dim, CPU-fast
EMBEDDING_DIM = 384

_instance: SentenceTransformer | None = None
_lock = threading.Lock()


def get_embedder() -> SentenceTransformer:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = SentenceTransformer(_MODEL_ID)
    return _instance


def embed_texts(texts: list[str]) -> list[list[float]]:
    model = get_embedder()
    vectors = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    return [v.tolist() for v in vectors]


def embed_query(text: str) -> list[float]:
    return embed_texts([text])[0]
