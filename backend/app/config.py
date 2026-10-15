from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Anchor every default path to the repo root regardless of the process's
# current working directory (uvicorn from backend/, pytest from backend/,
# a benchmark script run from the repo root, or a Docker container's
# /app — all resolve the same way). Explicit env vars (e.g. in
# docker-compose.yml) still override these.
_REPO_ROOT = Path(__file__).resolve().parents[2]
_BACKEND_ENV_FILE = _REPO_ROOT / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(_BACKEND_ENV_FILE), env_file_encoding="utf-8", extra="ignore")

    # Perception
    device: str = "cpu"
    vlm_model_id: str = "HuggingFaceTB/SmolVLM-256M-Instruct"
    local_llm_model_id: str = "Qwen/Qwen2.5-0.5B-Instruct"
    huggingface_token: str = ""

    # Vector store / RAG
    vector_store_backend: str = "milvus_lite"  # milvus_lite | milvus | pinecone
    # NOTE: intentionally not named MILVUS_URI — pymilvus itself reads that
    # exact env var name for its own global default connection at import
    # time (via an internal dotenv auto-load) and expects an http(s) URI,
    # which collides with our Milvus Lite local-file-path default and
    # crashes on import. See docs/limitations.md.
    vector_store_uri: str = str(_REPO_ROOT / "data" / "milvus_lite.db")
    pinecone_api_key: str = ""
    pinecone_index_name: str = "drishti-sops"
    pinecone_cloud: str = "aws"
    pinecone_region: str = "us-east-1"

    # Observability
    langsmith_api_key: str = ""
    langsmith_project: str = "drishti"
    langsmith_tracing: bool = False

    # Optional hosted LLM upgrade
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    azure_openai_endpoint: str = ""
    azure_openai_api_key: str = ""
    azure_openai_deployment: str = ""
    azure_openai_api_version: str = "2024-10-21"

    # Data paths
    data_sops_dir: Path = _REPO_ROOT / "data" / "sops"
    data_images_dir: Path = _REPO_ROOT / "data" / "images"
    data_labels_file: Path = _REPO_ROOT / "data" / "labels" / "labels.jsonl"
    memory_db_path: Path = _REPO_ROOT / "data" / "memory" / "drishti.db"

    # Services
    drone_gateway_url: str = "http://localhost:8100"

    # Server
    host: str = "0.0.0.0"
    port: int = 8000


settings = Settings()
