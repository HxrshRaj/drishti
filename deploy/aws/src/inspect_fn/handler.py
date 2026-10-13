"""Lambda: triggered by an S3 upload. Reads the image, asks Amazon Bedrock for a
schema-validated finding, and stores the result in DynamoDB."""
from __future__ import annotations

import logging
import os
import time
from decimal import Decimal
from urllib.parse import unquote_plus

import boto3

from common.findings import perceive

log = logging.getLogger()
log.setLevel(logging.INFO)

FORMATS = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png"}
MAX_BYTES = 3_750_000  # Bedrock Converse image size limit (3.75 MB)

_s3 = None
_ddb = None
_bedrock = None


def _clients():
    global _s3, _ddb, _bedrock
    if _s3 is None:
        _s3 = boto3.client("s3")
        _ddb = boto3.resource("dynamodb")
        _bedrock = boto3.client("bedrock-runtime")
    return _s3, _ddb, _bedrock


def process_object(bucket: str, key: str, s3, table, bedrock, model_id: str) -> dict:
    ext = key.rsplit(".", 1)[-1].lower() if "." in key else ""
    base = {"image_key": key, "created_at": int(time.time()), "model_id": model_id}
    if ext not in FORMATS:
        return {**base, "severity": "skipped", "status": "unsupported_type"}
    body = s3.get_object(Bucket=bucket, Key=key)["Body"].read()
    if len(body) > MAX_BYTES:
        return {**base, "severity": "skipped", "status": "image_too_large"}
    result = perceive(bedrock, model_id, body, FORMATS[ext])
    if result.parse_failed:
        return {**base, "severity": "unparsed", "status": "parse_failed",
                "attempts": result.attempts, "raw_output": result.raw_output[:1000]}
    f = result.finding
    return {**base, "status": "ok", "attempts": result.attempts, "severity": f["severity"],
            "finding_type": f["finding_type"], "location_description": f["location_description"],
            "confidence": Decimal(str(f["confidence"])), "notes": f["notes"]}


def handler(event, context):
    s3, ddb, bedrock = _clients()
    table = ddb.Table(os.environ["TABLE_NAME"])
    model_id = os.environ["MODEL_ID"]
    stored = 0
    for record in event.get("Records", []):
        bucket = record["s3"]["bucket"]["name"]
        key = unquote_plus(record["s3"]["object"]["key"])
        item = process_object(bucket, key, s3, table, bedrock, model_id)
        table.put_item(Item=item)  # same key overwritten on re-upload: idempotent
        log.info("processed key=%s status=%s severity=%s", key, item["status"], item["severity"])
        stored += 1
    return {"stored": stored}
