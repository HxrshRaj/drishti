from app.config import settings
from app.llm.provider import resolve_llm_backend


def test_azure_backend_is_selected_when_configured(monkeypatch):
    for k in ("anthropic_api_key", "openai_api_key"):
        monkeypatch.setattr(settings, k, "")
    monkeypatch.setattr(settings, "azure_openai_endpoint", "https://r.openai.azure.com/")
    monkeypatch.setattr(settings, "azure_openai_api_key", "k")
    monkeypatch.setattr(settings, "azure_openai_deployment", "gpt4o")
    b = resolve_llm_backend()
    assert b.kind == "azure" and b.model == "gpt4o"
    assert b.base_url == "https://r.openai.azure.com/openai/deployments/gpt4o" and b.api_version == "2024-10-21"


def test_falls_back_to_local_without_any_key(monkeypatch):
    for k in ("anthropic_api_key", "openai_api_key", "azure_openai_api_key"):
        monkeypatch.setattr(settings, k, "")
    assert resolve_llm_backend().kind == "local"
