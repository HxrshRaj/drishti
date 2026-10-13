import sys
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

AZURITE = "UseDevelopmentStorage=true"  # local Azure Storage emulator (Azurite)


@pytest.fixture
def table():
    """A real Table Storage table on Azurite, unique per test."""
    from azure.data.tables import TableServiceClient
    svc = TableServiceClient.from_connection_string(AZURITE)
    name = "t" + uuid.uuid4().hex[:12]
    client = svc.create_table(name)
    yield client
    svc.delete_table(name)


class FakeOpenAI:
    """Returns canned chat completions in order and records requests."""
    def __init__(self, *texts):
        self.texts = list(texts)
        self.calls = []
        outer = self

        class _Completions:
            def create(self, **kw):
                outer.calls.append(kw)
                text = outer.texts.pop(0) if len(outer.texts) > 1 else outer.texts[0]

                class Msg: content = text
                class Choice: message = Msg()
                class Resp: choices = [Choice()]
                return Resp()
        class _Chat:
            completions = _Completions()
        self.chat = _Chat()
