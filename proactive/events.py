"""Thread-safe, persistent SQLite event queue with bounded JSON payloads."""

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
from typing import Any, Callable, Mapping


MAX_EVENT_TYPE_BYTES = 128
MAX_PAYLOAD_BYTES = 64 * 1024
class EventStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True)
class Event:
    id: str
    type: str
    payload: dict[str, Any]
    status: EventStatus
    created_at: str
    updated_at: str
    attempts: int
    error: str | None = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _payload(value: Mapping[str, Any]) -> str:
    if not isinstance(value, Mapping):
        raise ValueError("payload must be a mapping")
    try:
        encoded = json.dumps(dict(value), ensure_ascii=False, sort_keys=True,
                             separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError, RecursionError) as exc:
        raise ValueError("payload must contain finite JSON values") from exc
    if len(encoded.encode("utf-8")) > MAX_PAYLOAD_BYTES:
        raise ValueError(f"payload exceeds {MAX_PAYLOAD_BYTES} bytes")
    return encoded


class EventBus:
    """A durable queue. Each operation uses its own SQLite connection."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).expanduser()
        self._lock = threading.RLock()
        self._listeners: dict[str, list[Callable[[Event], None]]] = {}
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
            connection.execute("""CREATE TABLE IF NOT EXISTS proactive_events (
                id TEXT PRIMARY KEY,
                event_type TEXT NOT NULL,
                payload TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('pending','processing','completed','failed')),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                attempts INTEGER NOT NULL DEFAULT 0,
                error TEXT
            )""")
            connection.execute("CREATE INDEX IF NOT EXISTS proactive_events_queue ON proactive_events(status, created_at, id)")

    @staticmethod
    def _row(row: sqlite3.Row) -> Event:
        return Event(row["id"], row["event_type"], json.loads(row["payload"]),
                     EventStatus(row["status"]), row["created_at"], row["updated_at"],
                     int(row["attempts"]), row["error"])

    def subscribe(self, event_type: str, callback: Callable[[Event], None]) -> Callable[[], None]:
        """Subscribe to newly published events in this process; returns unsubscribe."""
        self._validate_type(event_type)
        if not callable(callback):
            raise ValueError("callback must be callable")
        with self._lock:
            self._listeners.setdefault(event_type, []).append(callback)

        def unsubscribe() -> None:
            with self._lock:
                callbacks = self._listeners.get(event_type, [])
                if callback in callbacks:
                    callbacks.remove(callback)

        return unsubscribe

    @staticmethod
    def _validate_type(event_type: str) -> None:
        if (not isinstance(event_type, str) or not event_type.strip()
                or len(event_type.encode("utf-8")) > MAX_EVENT_TYPE_BYTES):
            raise ValueError("event type must be non-empty and at most 128 bytes")

    def publish(self, event_type: str, payload: Mapping[str, Any] | None = None,
                *, event_id: str | None = None) -> Event:
        self._validate_type(event_type)
        encoded = _payload({} if payload is None else payload)
        identifier = event_id or str(uuid.uuid4())
        if not isinstance(identifier, str) or not identifier or len(identifier) > 128:
            raise ValueError("event_id must be a non-empty string of at most 128 characters")
        timestamp = _now()
        with self._lock, self._session() as connection:
            connection.execute("INSERT INTO proactive_events VALUES (?, ?, ?, 'pending', ?, ?, 0, NULL)",
                               (identifier, event_type, encoded, timestamp, timestamp))
            row = connection.execute("SELECT * FROM proactive_events WHERE id = ?", (identifier,)).fetchone()
            event = self._row(row)
            listeners = tuple(self._listeners.get(event_type, ()))
        # Callbacks run after commit and outside the lock; listener failures do not undo durability.
        for callback in listeners:
            try:
                callback(event)
            except Exception:
                continue
        return event

    def get(self, event_id: str) -> Event | None:
        with self._lock, self._session() as connection:
            row = connection.execute("SELECT * FROM proactive_events WHERE id = ?", (event_id,)).fetchone()
            return self._row(row) if row else None

    def pending(self, *, limit: int = 100, event_type: str | None = None) -> list[Event]:
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 1000:
            raise ValueError("limit must be between 1 and 1000")
        query = "SELECT * FROM proactive_events WHERE status = 'pending'"
        args: tuple[Any, ...] = ()
        if event_type is not None:
            self._validate_type(event_type)
            query += " AND event_type = ?"
            args = (event_type,)
        query += " ORDER BY created_at, id LIMIT ?"
        args += (limit,)
        with self._lock, self._session() as connection:
            return [self._row(row) for row in connection.execute(query, args)]

    def claim(self, *, limit: int = 1, event_type: str | None = None) -> list[Event]:
        """Atomically move oldest pending events to processing and increment attempts."""
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 1000:
            raise ValueError("limit must be between 1 and 1000")
        if event_type is not None:
            self._validate_type(event_type)
        with self._lock, self._session() as connection:
            connection.execute("BEGIN IMMEDIATE")
            query = "SELECT id FROM proactive_events WHERE status = 'pending'"
            args: tuple[Any, ...] = ()
            if event_type is not None:
                query += " AND event_type = ?"
                args = (event_type,)
            ids = [row[0] for row in connection.execute(query + " ORDER BY created_at, id LIMIT ?", args + (limit,))]
            timestamp = _now()
            connection.executemany("UPDATE proactive_events SET status='processing', updated_at=?, attempts=attempts+1 WHERE id=? AND status='pending'",
                                   ((timestamp, identifier) for identifier in ids))
            if not ids:
                return []
            placeholders = ",".join("?" for _ in ids)
            rows = connection.execute(f"SELECT * FROM proactive_events WHERE id IN ({placeholders}) ORDER BY created_at, id", ids)
            return [self._row(row) for row in rows]

    def transition(self, event_id: str, status: EventStatus | str, *, error: str | None = None) -> Event:
        """Apply only valid lifecycle transitions; repeating the current state is idempotent."""
        try:
            target = EventStatus(status)
        except ValueError as exc:
            raise ValueError("unknown event status") from exc
        if error is not None:
            if not isinstance(error, str):
                raise ValueError("error must be a string or None")
            error = error[:1024]
        allowed = {
            EventStatus.PENDING: {EventStatus.PROCESSING},
            EventStatus.PROCESSING: {EventStatus.COMPLETED, EventStatus.FAILED, EventStatus.PENDING},
            EventStatus.FAILED: {EventStatus.PENDING},
            EventStatus.COMPLETED: set(),
        }
        with self._lock, self._session() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT * FROM proactive_events WHERE id=?", (event_id,)).fetchone()
            if row is None:
                raise KeyError(event_id)
            current = EventStatus(row["status"])
            if target != current and target not in allowed[current]:
                raise ValueError(f"invalid event transition: {current.value} -> {target.value}")
            if target != current:
                connection.execute("UPDATE proactive_events SET status=?, updated_at=?, error=? WHERE id=?",
                                   (target.value, _now(), error, event_id))
            elif error is not None:
                connection.execute("UPDATE proactive_events SET error=? WHERE id=?", (error, event_id))
            result = connection.execute("SELECT * FROM proactive_events WHERE id=?", (event_id,)).fetchone()
            return self._row(result)

