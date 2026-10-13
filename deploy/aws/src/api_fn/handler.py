"""Lambda behind an API Gateway HTTP API.
  GET /findings[?severity=major]  list stored findings
  GET /summary[?narrative=true]   counts by severity (+ optional Bedrock plain-English summary)"""
from __future__ import annotations

import json
import os
from collections import Counter
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Key

from common.findings import narrate

_ddb = None
_bedrock = None
LIMIT = 100


def _clients():
    global _ddb, _bedrock
    if _ddb is None:
        _ddb = boto3.resource("dynamodb")
        _bedrock = boto3.client("bedrock-runtime")
    return _ddb, _bedrock


def _json(status: int, body) -> dict:
    def default(o):
        if isinstance(o, Decimal):
            return float(o)
        raise TypeError
    return {"statusCode": status, "headers": {"content-type": "application/json"},
            "body": json.dumps(body, default=default)}


def _list(table, severity: str | None) -> list[dict]:
    if severity:
        resp = table.query(IndexName="by_severity", Limit=LIMIT, ScanIndexForward=False,
                           KeyConditionExpression=Key("severity").eq(severity))
    else:
        resp = table.scan(Limit=LIMIT)
    return resp.get("Items", [])


def handler(event, context):
    ddb, bedrock = _clients()
    table = ddb.Table(os.environ["TABLE_NAME"])
    path = event.get("rawPath", "")
    params = event.get("queryStringParameters") or {}
    if event.get("requestContext", {}).get("http", {}).get("method") != "GET":
        return _json(405, {"error": "method not allowed"})

    if path.endswith("/findings"):
        items = _list(table, params.get("severity"))
        return _json(200, {"count": len(items), "items": items})

    if path.endswith("/summary"):
        items = _list(table, None)
        counts = dict(Counter(i["severity"] for i in items))
        body = {"total": len(items), "by_severity": counts}
        if params.get("narrative") == "true" and items:
            try:
                body["narrative"] = narrate(bedrock, os.environ["MODEL_ID"], counts, len(items))
            except Exception:  # the counts are still correct without the narrative
                body["narrative"] = None
                body["narrative_error"] = "model unavailable"
        return _json(200, body)

    return _json(404, {"error": "not found"})
