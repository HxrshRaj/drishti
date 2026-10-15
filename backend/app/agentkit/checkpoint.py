"""Checkpoint stores so an agent run can pause (e.g. for approval) and resume,
including from a different process."""
from __future__ import annotations

import json
import sqlite3
from typing import Any, Protocol


class CheckpointStore(Protocol):
    def save(self, run_id: str, state: dict[str, Any]) -> None: ...
    def load(self, run_id: str) -> dict[str, Any] | None: ...


class SqliteCheckpointStore:
    def __init__(self, path: str = ":memory:") -> None:
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._db.execute("CREATE TABLE IF NOT EXISTS checkpoints (run_id TEXT PRIMARY KEY, state TEXT NOT NULL)")

    def save(self, run_id: str, state: dict[str, Any]) -> None:
        self._db.execute("INSERT OR REPLACE INTO checkpoints VALUES (?, ?)", (run_id, json.dumps(state)))
        self._db.commit()

    def load(self, run_id: str) -> dict[str, Any] | None:
        row = self._db.execute("SELECT state FROM checkpoints WHERE run_id = ?", (run_id,)).fetchone()
        return json.loads(row[0]) if row else None


class MongoCheckpointStore:
    """Same contract on MongoDB. `collection` is any pymongo-compatible collection."""

    def __init__(self, collection) -> None:
        self._c = collection

    @classmethod
    def from_uri(cls, uri: str, db: str = "agentkit", collection: str = "checkpoints") -> MongoCheckpointStore:
        from pymongo import MongoClient

        return cls(MongoClient(uri)[db][collection])

    def save(self, run_id: str, state: dict[str, Any]) -> None:
        self._c.replace_one({"_id": run_id}, {"_id": run_id, "state": state}, upsert=True)

    def load(self, run_id: str) -> dict[str, Any] | None:
        doc = self._c.find_one({"_id": run_id})
        return doc["state"] if doc else None
