"""Structured JSON logging that works with zero credentials. Every audit
event (app.memory.repository.log_audit_event) also gets emitted here as a
JSON line to stdout — this is the "structured logs and per-step metrics
that work without any key" half of Phase 6; LangSmith tracing (which needs
a key) is configured separately in app.observability.langsmith.
"""
from __future__ import annotations

import json
import logging
import sys
import time

logger = logging.getLogger("drishti")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    logger.propagate = False


def log_json(event_type: str, **fields) -> None:
    record = {"ts": time.time(), "event_type": event_type, **fields}
    logger.info(json.dumps(record, default=str))
