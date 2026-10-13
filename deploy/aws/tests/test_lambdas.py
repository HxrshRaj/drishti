"""Lambda handlers against emulated S3 + DynamoDB (moto). Bedrock is a fake client:
moto does not model foundation models, so model output here is canned."""
import json

import boto3
import pytest
from moto import mock_aws

import api_fn.handler as api_mod
import inspect_fn.handler as inspect_mod

GOOD = {"finding_type": "vehicle_presence", "location_description": "gate",
        "severity": "major", "confidence": 0.9, "notes": "queue at gate"}


class FakeBedrock:
    def __init__(self, *texts):
        self.texts = list(texts)

    def converse(self, **kw):
        t = self.texts.pop(0) if len(self.texts) > 1 else self.texts[0]
        return {"output": {"message": {"role": "assistant", "content": [{"text": t}]}}}


@pytest.fixture
def aws(monkeypatch):
    with mock_aws():
        s3 = boto3.client("s3")
        s3.create_bucket(Bucket="imgs")
        ddb = boto3.resource("dynamodb")
        ddb.create_table(
            TableName="findings", BillingMode="PAY_PER_REQUEST",
            KeySchema=[{"AttributeName": "image_key", "KeyType": "HASH"}],
            AttributeDefinitions=[
                {"AttributeName": "image_key", "AttributeType": "S"},
                {"AttributeName": "severity", "AttributeType": "S"},
                {"AttributeName": "created_at", "AttributeType": "N"}],
            GlobalSecondaryIndexes=[{
                "IndexName": "by_severity",
                "KeySchema": [{"AttributeName": "severity", "KeyType": "HASH"},
                              {"AttributeName": "created_at", "KeyType": "RANGE"}],
                "Projection": {"ProjectionType": "ALL"}}])
        monkeypatch.setenv("TABLE_NAME", "findings")
        monkeypatch.setenv("MODEL_ID", "test-model")
        yield s3, ddb.Table("findings")


def _event(*keys):
    return {"Records": [{"s3": {"bucket": {"name": "imgs"}, "object": {"key": k}}} for k in keys]}


def _use_bedrock(monkeypatch, *texts):
    fake = FakeBedrock(*texts)
    for mod in (inspect_mod, api_mod):
        monkeypatch.setattr(mod, "_bedrock", fake)
    return fake


def _prime(monkeypatch, s3, table):
    monkeypatch.setattr(inspect_mod, "_s3", s3)
    monkeypatch.setattr(inspect_mod, "_ddb", boto3.resource("dynamodb"))
    monkeypatch.setattr(api_mod, "_ddb", boto3.resource("dynamodb"))


def test_upload_creates_finding(aws, monkeypatch):
    s3, table = aws
    _prime(monkeypatch, s3, table)
    _use_bedrock(monkeypatch, json.dumps(GOOD))
    s3.put_object(Bucket="imgs", Key="site/a b.jpg", Body=b"jpegbytes")
    out = inspect_mod.handler(_event("site/a+b.jpg"), None)  # S3 URL-encodes keys
    assert out == {"stored": 1}
    item = table.get_item(Key={"image_key": "site/a b.jpg"})["Item"]
    assert item["status"] == "ok" and item["severity"] == "major" and item["model_id"] == "test-model"


def test_unsupported_and_oversized_and_parse_failures_are_recorded_not_dropped(aws, monkeypatch):
    s3, table = aws
    _prime(monkeypatch, s3, table)
    _use_bedrock(monkeypatch, "garbage")
    s3.put_object(Bucket="imgs", Key="notes.txt", Body=b"hi")
    s3.put_object(Bucket="imgs", Key="huge.png", Body=b"x" * 3_800_000)
    s3.put_object(Bucket="imgs", Key="bad.jpg", Body=b"img")
    inspect_mod.handler(_event("notes.txt", "huge.png", "bad.jpg"), None)
    status = {i["image_key"]: i["status"] for i in table.scan()["Items"]}
    assert status == {"notes.txt": "unsupported_type", "huge.png": "image_too_large",
                      "bad.jpg": "parse_failed"}


def test_reupload_overwrites_same_key(aws, monkeypatch):
    s3, table = aws
    _prime(monkeypatch, s3, table)
    _use_bedrock(monkeypatch, json.dumps(GOOD))
    s3.put_object(Bucket="imgs", Key="a.png", Body=b"1")
    inspect_mod.handler(_event("a.png"), None)
    inspect_mod.handler(_event("a.png"), None)
    assert len(table.scan()["Items"]) == 1


def _api(path, **params):
    return {"rawPath": path, "queryStringParameters": params or None,
            "requestContext": {"http": {"method": "GET"}}}


def test_api_lists_filters_and_summarises(aws, monkeypatch):
    s3, table = aws
    _prime(monkeypatch, s3, table)
    fake = _use_bedrock(monkeypatch, json.dumps(GOOD),
                        json.dumps({**GOOD, "severity": "minor"}), "One major, one minor.")
    for k in ("a.jpg", "b.jpg"):
        s3.put_object(Bucket="imgs", Key=k, Body=b"i")
    inspect_mod.handler(_event("a.jpg", "b.jpg"), None)

    all_ = json.loads(api_mod.handler(_api("/findings"), None)["body"])
    assert all_["count"] == 2
    major = json.loads(api_mod.handler(_api("/findings", severity="major"), None)["body"])
    assert [i["image_key"] for i in major["items"]] == ["a.jpg"]
    assert isinstance(major["items"][0]["confidence"], float)

    plain = json.loads(api_mod.handler(_api("/summary"), None)["body"])
    assert plain == {"total": 2, "by_severity": {"major": 1, "minor": 1}}
    with_text = json.loads(api_mod.handler(_api("/summary", narrative="true"), None)["body"])
    assert with_text["narrative"] == "One major, one minor." and fake.texts


def test_summary_survives_model_failure(aws, monkeypatch):
    s3, table = aws
    _prime(monkeypatch, s3, table)
    table.put_item(Item={"image_key": "x.jpg", "severity": "minor", "created_at": 1})

    class Boom:
        def converse(self, **kw):
            raise RuntimeError("AccessDenied")
    monkeypatch.setattr(api_mod, "_bedrock", Boom())
    body = json.loads(api_mod.handler(_api("/summary", narrative="true"), None)["body"])
    assert body["by_severity"] == {"minor": 1} and body["narrative"] is None


def test_api_rejects_other_methods_and_paths(aws, monkeypatch):
    s3, table = aws
    _prime(monkeypatch, s3, table)
    post = {"rawPath": "/findings", "requestContext": {"http": {"method": "POST"}}}
    assert api_mod.handler(post, None)["statusCode"] == 405
    assert api_mod.handler(_api("/nope"), None)["statusCode"] == 404
