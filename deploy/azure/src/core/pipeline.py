"""Blob-upload handler and API logic, kept free of Azure Functions types so it is testable."""
from __future__ import annotations

from collections import Counter

from core.findings import narrate, perceive
from core.store import FindingStore

MIME = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png"}
MAX_BYTES = 20_000_000  # Azure OpenAI image upload limit is 20 MB


def process_blob(name: str, data: bytes, store: FindingStore, client, deployment: str) -> dict:
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if ext not in MIME:
        return store.put(name, {"severity": "skipped", "status": "unsupported_type"})
    if len(data) > MAX_BYTES:
        return store.put(name, {"severity": "skipped", "status": "image_too_large"})
    result = perceive(client, deployment, data, MIME[ext])
    if result.parse_failed:
        return store.put(name, {"severity": "unparsed", "status": "parse_failed",
                                "attempts": result.attempts, "raw_output": result.raw_output[:1000],
                                "model": deployment})
    f = result.finding
    return store.put(name, {"status": "ok", "attempts": result.attempts, "model": deployment, **f})


def list_findings(store: FindingStore, severity: str | None) -> dict:
    items = store.list(severity)
    return {"count": len(items), "items": items}


def summarise(store: FindingStore, client, deployment: str, narrative: bool) -> dict:
    items = store.list()
    counts = dict(Counter(i["severity"] for i in items))
    body = {"total": len(items), "by_severity": counts}
    if narrative and items:
        try:
            body["narrative"] = narrate(client, deployment, counts, len(items))
        except Exception:  # the counts stay correct without the narrative
            body["narrative"] = None
            body["narrative_error"] = "model unavailable"
    return body
