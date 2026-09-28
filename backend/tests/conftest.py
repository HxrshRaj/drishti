import socket
import subprocess
import time
from pathlib import Path

import httpx
import pytest

GATEWAY_DIR = Path(__file__).resolve().parent.parent.parent / "drone-gateway"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def live_gateway_url():
    """Launches the REAL drone-gateway service (its own venv, its own
    process) so orchestration tests exercise real HTTP calls into real
    gateway logic — not a mock. Session-scoped: one process for the whole
    test run. Skips (rather than fails) if the gateway's own venv isn't
    set up, so backend-only test runs still work.
    """
    gateway_python = GATEWAY_DIR / ".venv" / "Scripts" / "python.exe"
    if not gateway_python.exists():
        pytest.skip("drone-gateway/.venv not set up — run pip install -r drone-gateway/requirements.txt")

    port = _free_port()
    env = {
        **__import__("os").environ,
        "DATA_IMAGES_DIR": str(GATEWAY_DIR.parent / "data" / "images"),
        "DATA_LABELS_FILE": str(GATEWAY_DIR.parent / "data" / "labels" / "labels.jsonl"),
    }
    proc = subprocess.Popen(
        [str(gateway_python), "-m", "uvicorn", "app.main:app", "--port", str(port), "--host", "127.0.0.1"],
        cwd=str(GATEWAY_DIR), env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    base_url = f"http://127.0.0.1:{port}"
    try:
        for _ in range(50):
            try:
                if httpx.get(f"{base_url}/health", timeout=1).status_code == 200:
                    break
            except httpx.RequestError:
                pass
            time.sleep(0.2)
        else:
            proc.kill()
            pytest.fail("drone-gateway did not become healthy in time")
        yield base_url
    finally:
        proc.kill()
        proc.wait(timeout=10)


@pytest.fixture(scope="session")
def _ingested_test_vector_store(tmp_path_factory):
    """Milvus Lite locks its data file for exclusive access per process —
    running tests against the same file a live dev server has open
    (data/milvus_lite.db) fails with DataDirLockedError. So the whole test
    session gets its own Milvus Lite file, session-scoped so SOP ingestion
    (which loads the embedding model) only happens once.
    """
    from app.config import settings
    db_path = tmp_path_factory.mktemp("vector_store") / "test_milvus_lite.db"
    settings.vector_store_uri = str(db_path)

    from app.rag.ingest import ingest_sops
    from app.vectorstore.factory import get_vector_store
    get_vector_store.cache_clear()
    ingest_sops()
    return str(db_path)


@pytest.fixture(autouse=True)
def isolated_memory_db(monkeypatch, tmp_path, _ingested_test_vector_store):
    """Every test gets its own throwaway SQLite file so tests don't share
    state and don't touch the real data/memory/drishti.db.
    """
    db_path = tmp_path / "test_memory.db"
    monkeypatch.setenv("MEMORY_DB_PATH", str(db_path))
    from app.config import settings
    monkeypatch.setattr(settings, "memory_db_path", db_path)
    monkeypatch.setattr(settings, "vector_store_uri", _ingested_test_vector_store)

    import app.db.session as session_module
    monkeypatch.setattr(session_module, "_engine", None)
    monkeypatch.setattr(session_module, "_SessionLocal", None)
    yield
