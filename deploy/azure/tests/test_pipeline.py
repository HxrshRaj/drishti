"""Pipeline logic against a REAL Table Storage API (Azurite) and a fake Azure OpenAI client.
The model's replies are canned; storage behaviour (keys, upserts, queries) is genuinely exercised."""
import json

from azure.storage.blob import BlobServiceClient
from conftest import AZURITE, FakeOpenAI

from core.pipeline import list_findings, process_blob, summarise
from core.store import FindingStore, decode_key, encode_key

GOOD = {"finding_type": "vehicle_presence", "location_description": "gate",
        "severity": "major", "confidence": 0.9, "notes": "queue at gate"}


def test_key_encoding_round_trips_names_table_keys_cannot_hold():
    for name in ["a.jpg", "site/north lot/a#1?.png", "ünï.jpg"]:
        assert decode_key(encode_key(name)) == name
        assert not set(encode_key(name)) & set("/\\#?")


def test_blob_to_finding_end_to_end(table):
    # Upload to Azurite Blob Storage, read it back as the trigger would, then process it.
    blobs = BlobServiceClient.from_connection_string(AZURITE)
    cont = blobs.get_container_client("images-test")
    if not cont.exists():
        cont.create_container()
    cont.upload_blob("site/a b.jpg", b"jpegbytes", overwrite=True)
    data = cont.download_blob("site/a b.jpg").readall()

    store = FindingStore(table)
    rec = process_blob("site/a b.jpg", data, store, FakeOpenAI(json.dumps(GOOD)), "dep")
    assert rec["status"] == "ok" and rec["severity"] == "major" and rec["model"] == "dep"
    assert store.list()[0]["image_name"] == "site/a b.jpg"


def test_unsupported_oversized_and_unparseable_are_recorded_not_dropped(table, monkeypatch):
    import core.pipeline as p
    monkeypatch.setattr(p, "MAX_BYTES", 10)
    store = FindingStore(table)
    client = FakeOpenAI("garbage")
    process_blob("notes.txt", b"hi", store, client, "d")
    process_blob("huge.png", b"x" * 11, store, client, "d")
    process_blob("bad.jpg", b"img", store, client, "d")
    status = {r["image_name"]: r["status"] for r in store.list()}
    assert status == {"notes.txt": "unsupported_type", "huge.png": "image_too_large",
                      "bad.jpg": "parse_failed"}


def test_reupload_overwrites_same_row(table):
    store = FindingStore(table)
    c = FakeOpenAI(json.dumps(GOOD), json.dumps({**GOOD, "severity": "minor"}))
    process_blob("a.png", b"1", store, c, "d")
    process_blob("a.png", b"2", store, c, "d")
    rows = store.list()
    assert len(rows) == 1 and rows[0]["severity"] == "minor"


def test_list_filter_and_summary(table):
    store = FindingStore(table)
    c = FakeOpenAI(json.dumps(GOOD), json.dumps({**GOOD, "severity": "minor"}), "One major, one minor.")
    process_blob("a.jpg", b"1", store, c, "d")
    process_blob("b.jpg", b"2", store, c, "d")
    assert [i["image_name"] for i in list_findings(store, "major")["items"]] == ["a.jpg"]
    assert list_findings(store, None)["count"] == 2
    assert summarise(store, c, "d", False) == {"total": 2, "by_severity": {"major": 1, "minor": 1}}
    assert summarise(store, c, "d", True)["narrative"] == "One major, one minor."


def test_summary_counts_survive_model_failure(table):
    store = FindingStore(table)
    store.put("x.jpg", {"severity": "minor", "status": "ok"})

    class Boom:
        class chat:
            class completions:
                @staticmethod
                def create(**kw):
                    raise RuntimeError("quota")
    body = summarise(store, Boom(), "d", True)
    assert body["by_severity"] == {"minor": 1} and body["narrative"] is None
