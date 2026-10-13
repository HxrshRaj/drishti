"""The Azure Functions wrappers: HTTP request/response handling, with dependencies injected."""
import json

import azure.functions as func
from conftest import FakeOpenAI

import function_app as fa
from core.store import FindingStore


def _req(route, **params):
    return func.HttpRequest(method="GET", url=f"/api/{route}", params=params, body=b"")


def test_http_routes_return_json(table, monkeypatch):
    store = FindingStore(table)
    store.put("a.jpg", {"severity": "major", "status": "ok"})
    monkeypatch.setattr(fa, "_store", store)
    monkeypatch.setattr(fa, "_client", FakeOpenAI("Summary."))
    monkeypatch.setenv("OPENAI_DEPLOYMENT", "dep")

    r = fa.findings._function.get_user_function()(_req("findings", severity="major"))
    assert r.status_code == 200 and r.mimetype == "application/json"
    assert json.loads(r.get_body())["count"] == 1

    r = fa.summary._function.get_user_function()(_req("summary", narrative="true"))
    assert json.loads(r.get_body())["narrative"] == "Summary."


def test_app_registers_expected_triggers():
    registered = fa.app.get_functions()  # build once: it validates unique names
    funcs = {f.get_function_name(): f.get_trigger().type for f in registered}
    assert funcs == {"inspect_image": "blobTrigger", "findings": "httpTrigger",
                     "summary": "httpTrigger"}
    blob = next(f for f in registered if f.get_function_name() == "inspect_image")
    assert blob.get_trigger().path == "images/{name}"
