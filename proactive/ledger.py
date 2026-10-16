"""Append-only activity ledger with deterministic status transitions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import json
import os
from pathlib import Path
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from typing import Any, Mapping

from .events import MAX_PAYLOAD_BYTES, _payload


class ActivityStatus(str, Enum):
    OBSERVED = "observed"
    PLANNED = "planned"
    RUNNING = "running"
    UNVERIFIED = "unverified"
    INTERRUPTED = "interrupted"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class Activity:
    id: str
    event_id: str | None
    kind: str
    summary: str
    details: dict[str, Any]
    status: ActivityStatus
    created_at: str
    updated_at: str


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


class ActivityLedger:
    """Local persistent log; each method opens an isolated SQLite connection."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).expanduser()
        self._lock = threading.RLock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        connection = sqlite3.connect(self.path, timeout=30)
        try:
            os.chmod(self.path, 0o600)
        except OSError:
            connection.close()
            raise
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 30000")
        return connection

    @contextmanager
    def _session(self):
        connection = self._connect()
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._lock, self._session() as connection:
            connection.execute("BEGIN IMMEDIATE")
            old = connection.execute("SELECT sql FROM sqlite_master WHERE name='proactive_activity'").fetchone()
            if old and "'unverified'" not in old['sql']:
                connection.execute("ALTER TABLE proactive_activity RENAME TO proactive_activity_legacy")
            connection.execute("""CREATE TABLE IF NOT EXISTS proactive_activity (
                id TEXT PRIMARY KEY,
                event_id TEXT,
                kind TEXT NOT NULL,
                summary TEXT NOT NULL,
                details TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('observed','planned','running','unverified','interrupted','succeeded','failed','cancelled')),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )""")
            if old and "'unverified'" not in old['sql']:
                connection.execute("INSERT INTO proactive_activity SELECT * FROM proactive_activity_legacy")
                connection.execute("DROP TABLE proactive_activity_legacy")
            connection.execute("CREATE INDEX IF NOT EXISTS proactive_activity_created ON proactive_activity(created_at, id)")
            connection.execute("CREATE INDEX IF NOT EXISTS proactive_activity_event ON proactive_activity(event_id)")
            connection.execute("""CREATE TABLE IF NOT EXISTS proactive_execution (
                activity_id TEXT PRIMARY KEY, record TEXT NOT NULL
            )""")

    def save_execution(self, activity_id: str, record: Mapping[str, Any]) -> None:
        encoded = _payload(record)
        with self._lock, self._session() as connection:
            connection.execute("INSERT OR REPLACE INTO proactive_execution VALUES (?, ?)",
                               (activity_id, encoded))

    def executions(self, *, pending_only=False) -> dict[str, dict[str, Any]]:
        with self._lock, self._session() as connection:
            query = "SELECT e.activity_id, e.record FROM proactive_execution e JOIN proactive_activity a ON a.id=e.activity_id"
            if pending_only:
                query += " WHERE a.status IN ('planned','running')"
            return {row['activity_id']: json.loads(row['record']) for row in connection.execute(query)}

    def execution(self, activity_id: str) -> dict[str, Any] | None:
        with self._lock, self._session() as connection:
            row = connection.execute('SELECT record FROM proactive_execution WHERE activity_id=?',
                                     (activity_id,)).fetchone()
            return json.loads(row['record']) if row else None

    @staticmethod
    def _row(row: sqlite3.Row) -> Activity:
        return Activity(row["id"], row["event_id"], row["kind"], row["summary"],
                        json.loads(row["details"]), ActivityStatus(row["status"]),
                        row["created_at"], row["updated_at"])

    def append(self, kind: str, summary: str, *, details: Mapping[str, Any] | None = None,
               event_id: str | None = None, status: ActivityStatus | str = ActivityStatus.OBSERVED,
               activity_id: str | None = None) -> Activity:
        if not isinstance(kind, str) or not kind.strip() or len(kind.encode("utf-8")) > 128:
            raise ValueError("kind must be non-empty and at most 128 bytes")
        if not isinstance(summary, str) or not summary.strip() or len(summary.encode("utf-8")) > 4096:
            raise ValueError("summary must be non-empty and at most 4096 bytes")
        if event_id is not None and (not isinstance(event_id, str) or not event_id or len(event_id) > 128):
            raise ValueError("event_id must be a non-empty string of at most 128 characters")
        try:
            normalized_status = ActivityStatus(status)
        except ValueError as exc:
            raise ValueError("unknown activity status") from exc
        if normalized_status not in (ActivityStatus.OBSERVED, ActivityStatus.PLANNED):
            raise ValueError("new activity status must be observed or planned")
        encoded = _payload({} if details is None else details)
        if len(encoded.encode("utf-8")) > MAX_PAYLOAD_BYTES:
            raise ValueError("activity details exceed payload limit")
        identifier = activity_id or str(uuid.uuid4())
        if not isinstance(identifier, str) or not identifier or len(identifier) > 128:
            raise ValueError("activity_id must be a non-empty string of at most 128 characters")
        timestamp = _now()
        with self._lock, self._session() as connection:
            connection.execute("INSERT INTO proactive_activity VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                               (identifier, event_id, kind, summary, encoded,
                                normalized_status.value, timestamp, timestamp))
            return self._row(connection.execute("SELECT * FROM proactive_activity WHERE id=?", (identifier,)).fetchone())

    def get(self, activity_id: str) -> Activity | None:
        with self._lock, self._session() as connection:
            row = connection.execute("SELECT * FROM proactive_activity WHERE id=?", (activity_id,)).fetchone()
            return self._row(row) if row else None

    def list(self, *, limit: int = 100, before: str | None = None,
             event_id: str | None = None) -> list[Activity]:
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 1000:
            raise ValueError("limit must be between 1 and 1000")
        query = "SELECT * FROM proactive_activity WHERE 1=1"
        args: list[Any] = []
        if before is not None:
            query += " AND created_at < ?"
            args.append(before)
        if event_id is not None:
            query += " AND event_id = ?"
            args.append(event_id)
        query += " ORDER BY created_at DESC, id DESC LIMIT ?"
        args.append(limit)
        with self._lock, self._session() as connection:
            return [self._row(row) for row in connection.execute(query, args)]

    def transition(self, activity_id: str, status: ActivityStatus | str) -> Activity:
        try:
            target = ActivityStatus(status)
        except ValueError as exc:
            raise ValueError("unknown activity status") from exc
        allowed = {
            ActivityStatus.OBSERVED: {ActivityStatus.PLANNED, ActivityStatus.CANCELLED},
            ActivityStatus.PLANNED: {ActivityStatus.RUNNING, ActivityStatus.CANCELLED, ActivityStatus.FAILED, ActivityStatus.INTERRUPTED},
            ActivityStatus.RUNNING: {ActivityStatus.SUCCEEDED, ActivityStatus.FAILED, ActivityStatus.CANCELLED,
                                     ActivityStatus.UNVERIFIED, ActivityStatus.INTERRUPTED},
            ActivityStatus.UNVERIFIED: set(),
            ActivityStatus.INTERRUPTED: set(),
            ActivityStatus.SUCCEEDED: set(),
            ActivityStatus.FAILED: {ActivityStatus.PLANNED, ActivityStatus.CANCELLED},
            ActivityStatus.CANCELLED: set(),
        }
        with self._lock, self._session() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT * FROM proactive_activity WHERE id=?", (activity_id,)).fetchone()
            if row is None:
                raise KeyError(activity_id)
            current = ActivityStatus(row["status"])
            if target != current and target not in allowed[current]:
                raise ValueError(f"invalid activity transition: {current.value} -> {target.value}")
            if target != current:
                connection.execute("UPDATE proactive_activity SET status=?, updated_at=? WHERE id=?",
                                   (target.value, _now(), activity_id))
            return self._row(connection.execute("SELECT * FROM proactive_activity WHERE id=?", (activity_id,)).fetchone())

