from __future__ import annotations

from functools import lru_cache

from app.config import settings
from app.vectorstore.base import VectorStore


@lru_cache(maxsize=1)
def get_vector_store() -> VectorStore:
    backend = settings.vector_store_backend
    if backend in ("milvus_lite", "milvus"):
        from app.vectorstore.milvus_store import MilvusVectorStore
        return MilvusVectorStore(uri=settings.vector_store_uri)
    if backend == "pinecone":
        if not settings.pinecone_api_key:
            raise RuntimeError("VECTOR_STORE_BACKEND=pinecone but PINECONE_API_KEY is not set")
        from app.vectorstore.pinecone_store import PineconeVectorStore
        return PineconeVectorStore(
            api_key=settings.pinecone_api_key, cloud=settings.pinecone_cloud, region=settings.pinecone_region,
        )
    raise ValueError(f"unknown VECTOR_STORE_BACKEND={backend!r}")
