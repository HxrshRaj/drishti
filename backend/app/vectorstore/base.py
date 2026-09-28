from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class VectorHit:
    id: str
    score: float
    text: str
    metadata: dict


class VectorStore(ABC):
    """Common interface implemented by every vector-store backend this
    project supports (Milvus Lite, Milvus standalone, Pinecone), so the
    RAG and memory layers are written once against this interface and the
    backend is a config switch (VECTOR_STORE_BACKEND).
    """

    @abstractmethod
    def ensure_collection(self, collection: str, dim: int) -> None: ...

    @abstractmethod
    def upsert(self, collection: str, ids: list[str], vectors: list[list[float]],
               texts: list[str], metadatas: list[dict]) -> None: ...

    @abstractmethod
    def query(self, collection: str, vector: list[float], top_k: int = 5,
              metadata_filter: dict | None = None) -> list[VectorHit]: ...

    @abstractmethod
    def delete(self, collection: str, ids: list[str]) -> None: ...

    @abstractmethod
    def count(self, collection: str) -> int: ...
