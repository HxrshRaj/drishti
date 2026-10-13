"""Azure Functions (Python v2 model): blob-triggered inspection + read-only HTTP API.

  image uploaded to the `images` container -> process_blob -> Azure OpenAI (vision) -> Table Storage
  GET /api/findings[?severity=]   GET /api/summary[?narrative=true]
"""
import json
import logging
import os

import azure.functions as func
from azure.data.tables import TableServiceClient
from azure.identity import DefaultAzureCredential
from openai import AzureOpenAI

from core.pipeline import list_findings, process_blob, summarise
from core.store import FindingStore

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)
_store = None
_client = None


def _deps():
    """Built lazily so importing this module needs no cloud settings (tests, tooling)."""
    global _store, _client
    if _store is None:
        cred = DefaultAzureCredential()  # the Function App's managed identity in Azure
        svc = TableServiceClient(endpoint=os.environ["TABLE_ENDPOINT"], credential=cred)
        _store = FindingStore(svc.get_table_client(os.environ.get("TABLE_NAME", "findings")))
        token = cred.get_token("https://cognitiveservices.azure.com/.default").token
        _client = AzureOpenAI(azure_endpoint=os.environ["OPENAI_ENDPOINT"],
                              api_version="2024-06-01", azure_ad_token=token)
    return _store, _client


@app.blob_trigger(arg_name="blob", path="images/{name}", connection="IMAGES")
def inspect_image(blob: func.InputStream):
    store, client = _deps()
    name = blob.name.split("/", 1)[-1]
    record = process_blob(name, blob.read(), store, client, os.environ["OPENAI_DEPLOYMENT"])
    logging.info("processed %s status=%s severity=%s", name, record["status"], record["severity"])


def _json(body, status=200) -> func.HttpResponse:
    return func.HttpResponse(json.dumps(body, default=str), status_code=status,
                             mimetype="application/json")


@app.route(route="findings", methods=["GET"])
def findings(req: func.HttpRequest) -> func.HttpResponse:
    store, _ = _deps()
    return _json(list_findings(store, req.params.get("severity")))


@app.route(route="summary", methods=["GET"])
def summary(req: func.HttpRequest) -> func.HttpResponse:
    store, client = _deps()
    return _json(summarise(store, client, os.environ["OPENAI_DEPLOYMENT"],
                           req.params.get("narrative") == "true"))
