import json

from app.observability.langsmith import configure_langsmith
from app.observability.logging_config import log_json


def test_log_json_emits_valid_json(caplog):
    with caplog.at_level("INFO", logger="drishti"):
        log_json("test_event", foo="bar", n=3)
    line = caplog.records[-1].message
    data = json.loads(line)
    assert data["event_type"] == "test_event"
    assert data["foo"] == "bar"
    assert data["n"] == 3


def test_configure_langsmith_disabled_without_key(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "langsmith_api_key", "")
    assert configure_langsmith() is False


def test_configure_langsmith_enabled_with_key(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "langsmith_api_key", "fake-key-for-test")
    monkeypatch.setattr(settings, "langsmith_project", "drishti-test")
    assert configure_langsmith() is True
    import os
    assert os.environ["LANGSMITH_TRACING"] == "true"
    assert os.environ["LANGSMITH_API_KEY"] == "fake-key-for-test"


def test_audit_event_also_emits_structured_log(caplog):
    from app.memory import repository as repo
    with caplog.at_level("INFO", logger="drishti"):
        mid = repo.create_mission(site_id="meridian-substation", operator_goal="log test")
        repo.log_audit_event("goto", actor="orchestrator", payload={"waypoint_id": "WP-01"}, mission_id=mid)
    assert any(json.loads(r.message).get("event_type") == "goto" for r in caplog.records)
