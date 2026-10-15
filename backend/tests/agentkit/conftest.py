import pytest

from app.agentkit.tracing import configure_tracing, get_memory_exporter


@pytest.fixture(scope="session", autouse=True)
def _tracing():
    configure_tracing(in_memory=True)


@pytest.fixture
def spans():
    exp = get_memory_exporter()
    exp.clear()
    yield exp


# The repo-wide autouse fixtures load the embedding model and a vector store. The
# agent harness needs neither, so these tests override them with no-ops and run fast.
@pytest.fixture(scope="session")
def _ingested_test_vector_store():
    return None


@pytest.fixture(autouse=True)
def isolated_memory_db():
    yield
