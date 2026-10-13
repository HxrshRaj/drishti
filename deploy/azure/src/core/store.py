"""Findings stored in Azure Table Storage. RowKey = URL-safe base64 of the blob name, because
table keys cannot contain '/', '\\', '#' or '?'. Upserting the same name overwrites (idempotent)."""
from __future__ import annotations

import base64
import time

from azure.data.tables import TableClient, UpdateMode

PARTITION = "finding"


def encode_key(name: str) -> str:
    return base64.urlsafe_b64encode(name.encode()).decode().rstrip("=")


def decode_key(key: str) -> str:
    return base64.urlsafe_b64decode(key + "=" * (-len(key) % 4)).decode()


class FindingStore:
    def __init__(self, table: TableClient):
        self.table = table

    def put(self, image_name: str, record: dict) -> dict:
        entity = {"PartitionKey": PARTITION, "RowKey": encode_key(image_name),
                  "image_name": image_name, "created_at": int(time.time()), **record}
        self.table.upsert_entity(entity, mode=UpdateMode.REPLACE)
        return entity

    def list(self, severity: str | None = None, limit: int = 100) -> list[dict]:
        flt = "PartitionKey eq 'finding'"
        params = {}
        if severity:
            flt += " and severity eq @sev"
            params["sev"] = severity
        rows = self.table.query_entities(flt, parameters=params or None, results_per_page=limit)
        out = []
        for i, row in enumerate(rows):
            if i >= limit:
                break
            out.append({k: v for k, v in dict(row).items() if k not in ("PartitionKey", "RowKey")})
        return out
