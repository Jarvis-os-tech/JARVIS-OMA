"""SQLite evidence ledger; connections belong to individual operations only.

Only explicit nonempty keys establish replacement relationships. Text matching
is exact (case and whitespace included), never semantic. Read operations do not
create a database. Forget removes an entire revision family, including evidence.
"""
from __future__ import annotations

from contextlib import contextmanager
import json
import math
import os
from pathlib import Path
import sqlite3
import time
from uuid import uuid4


KINDS = frozenset({"fact", "preference", "decision", "goal", "constraint",
                   "observation", "event", "entity", "procedure", "task", "project"})
_SCHEMA = """
CREATE TABLE IF NOT EXISTS entries (
 id TEXT PRIMARY KEY, text TEXT NOT NULL, kind TEXT NOT NULL,
 key TEXT NOT NULL, source TEXT NOT NULL, evidence TEXT,
 confidence REAL NOT NULL, status TEXT NOT NULL,
 created_at REAL NOT NULL, updated_at REAL NOT NULL, family TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS active_keys ON entries(key)
 WHERE key <> '' AND status = 'active';
CREATE TABLE IF NOT EXISTS revisions (
 sequence INTEGER PRIMARY KEY AUTOINCREMENT, family TEXT NOT NULL,
 snapshot TEXT NOT NULL
);
"""


class KnowledgeStore:
    def __init__(self, path):
        self.path = Path(path)

    @contextmanager
    def _connection(self, write=False):
        if not write and not self.path.exists():
            yield None
            return
        if write:
            self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            # O_EXCL avoids truncation and ensures restrictive permissions at
            # creation, before SQLite ever writes sensitive evidence.
            try:
                fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            except FileExistsError:
                pass
            else:
                os.close(fd)
            os.chmod(self.path, 0o600)
        uri = self.path.resolve().as_uri() + ("?mode=rw" if write else "?mode=ro")
        connection = sqlite3.connect(uri, uri=True, timeout=30)
        connection.row_factory = sqlite3.Row
        try:
            if write:
                connection.execute("PRAGMA secure_delete=ON")
                connection.execute("BEGIN IMMEDIATE")
                # executescript implicitly commits; use individual statements
                # so initialization and the mutation share one transaction.
                for statement in _SCHEMA.split(";"):
                    if statement.strip():
                        connection.execute(statement)
            yield connection
            if write:
                connection.commit()
        except BaseException:
            if write:
                connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def _entry(row):
        entry = dict(row)
        entry.pop("family", None)
        entry["evidence"] = json.loads(entry["evidence"]) if entry["evidence"] is not None else None
        return entry

    @staticmethod
    def _validate(text, kind, key, source, evidence, confidence):
        for name, value in (("text", text), ("kind", kind), ("key", key), ("source", source)):
            if not isinstance(value, str):
                raise TypeError(f"{name} must be a string")
        if not text.strip():
            raise ValueError("text must not be blank")
        if key and not key.strip():
            raise ValueError("key must be empty or nonblank")
        if kind not in KINDS:
            raise ValueError(f"unsupported kind: {kind}")
        if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
            raise TypeError("confidence must be a number")
        if not math.isfinite(confidence) or not 0 <= confidence <= 1:
            raise ValueError("confidence must be finite and between zero and one")
        if evidence is not None and not isinstance(evidence, (dict, list, str)):
            raise TypeError("evidence must be a JSON object, array, string, or None")
        return json.dumps(evidence, allow_nan=False) if evidence is not None else None

    def _record(self, connection, row, action, reason=""):
        snapshot = self._entry(row)
        snapshot.update(action=action, reason=reason)
        connection.execute("INSERT INTO revisions(family, snapshot) VALUES (?, ?)",
                           (row["family"], json.dumps(snapshot, allow_nan=False)))

    def _insert(self, connection, text, kind, key, source, evidence, confidence,
                family=None, action="created", reason=""):
        memory_id = uuid4().hex
        now = time.time()
        connection.execute("INSERT INTO entries VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                           (memory_id, text, kind, key, source, evidence, confidence,
                            "active", now, now, family or memory_id))
        row = connection.execute("SELECT * FROM entries WHERE id=?", (memory_id,)).fetchone()
        self._record(connection, row, action, reason)
        return self._entry(row)

    def upsert(self, text, kind="fact", key="", source="", evidence=None, confidence=1.0):
        encoded = self._validate(text, kind, key, source, evidence, confidence)
        with self._connection(write=True) as connection:
            duplicate = connection.execute(
                "SELECT * FROM entries WHERE text=? AND kind=? AND key=? AND status='active'",
                (text, kind, key)).fetchone()
            if duplicate:
                # Identical observations are idempotent. New evidence is kept
                # as a revision, while the initial source remains in history.
                if (duplicate["source"], duplicate["evidence"], duplicate["confidence"]) != (source, encoded, confidence):
                    connection.execute("UPDATE entries SET source=?, evidence=?, confidence=?, updated_at=? WHERE id=?",
                                       (source, encoded, confidence, time.time(), duplicate["id"]))
                    duplicate = connection.execute("SELECT * FROM entries WHERE id=?", (duplicate["id"],)).fetchone()
                    self._record(connection, duplicate, "evidence")
                return self._entry(duplicate)
            previous = connection.execute("SELECT * FROM entries WHERE key=? AND status='active'", (key,)).fetchone() if key else None
            if previous:
                self._supersede(connection, previous, "explicit key replacement")
            return self._insert(connection, text, kind, key, source, encoded, confidence,
                                family=previous["family"] if previous else None)

    def _supersede(self, connection, row, reason):
        connection.execute("UPDATE entries SET status='superseded', updated_at=? WHERE id=?",
                           (time.time(), row["id"]))
        retired = connection.execute("SELECT * FROM entries WHERE id=?", (row["id"],)).fetchone()
        self._record(connection, retired, "superseded", reason)

    def list(self, active_only=True):
        if not isinstance(active_only, bool):
            raise TypeError("active_only must be a boolean")
        with self._connection() as connection:
            if connection is None:
                return []
            query = "SELECT * FROM entries" + (" WHERE status='active'" if active_only else "")
            return [self._entry(row) for row in connection.execute(query + " ORDER BY created_at, id")]

    def correct(self, memory_id, text, reason=""):
        self._id(memory_id)
        if not isinstance(reason, str):
            raise TypeError("reason must be a string")
        self._validate(text, "fact", "", "", None, 1.0)
        if not self.path.exists():
            raise KeyError(memory_id)
        with self._connection(write=True) as connection:
            row = connection.execute("SELECT * FROM entries WHERE id=?", (memory_id,)).fetchone()
            if row is None:
                raise KeyError(memory_id)
            if row["status"] != "active":
                raise ValueError("only active entries can be corrected")
            self._supersede(connection, row, reason)
            evidence = json.dumps({"role": "user", "quote": text, "reason": reason})
            return self._insert(connection, text, row["kind"], row["key"], "explicit-user-correction",
                                evidence, 1.0, row["family"], "corrected", reason)

    @staticmethod
    def _id(memory_id):
        if not isinstance(memory_id, str):
            raise TypeError("memory_id must be a string")
        if not memory_id:
            raise ValueError("memory_id must not be empty")

    def history(self, memory_id):
        self._id(memory_id)
        with self._connection() as connection:
            if connection is None:
                return []
            row = connection.execute("SELECT family FROM entries WHERE id=?", (memory_id,)).fetchone()
            if row is None:
                return []
            return [json.loads(item[0]) for item in connection.execute(
                "SELECT snapshot FROM revisions WHERE family=? ORDER BY sequence", (row[0],))]

    def forget(self, memory_id):
        self._id(memory_id)
        if not self.path.exists():
            return {"deleted": 0}
        with self._connection(write=True) as connection:
            row = connection.execute("SELECT family FROM entries WHERE id=?", (memory_id,)).fetchone()
            if row is None:
                return {"deleted": 0}
            connection.execute("DELETE FROM revisions WHERE family=?", (row[0],))
            deleted = connection.execute("DELETE FROM entries WHERE family=?", (row[0],)).rowcount
            return {"deleted": deleted}

    def clear(self):
        if not self.path.exists():
            return {"deleted": 0}
        with self._connection(write=True) as connection:
            connection.execute("DELETE FROM revisions")
            deleted = connection.execute("DELETE FROM entries").rowcount
            return {"deleted": deleted}

    def stats(self):
        with self._connection() as connection:
            counts = {"active": 0, "superseded": 0, "total": 0, "revisions": 0}
            if connection is not None:
                for status, count in connection.execute("SELECT status, COUNT(*) FROM entries GROUP BY status"):
                    counts[status] = count
                    counts["total"] += count
                counts["revisions"] = connection.execute("SELECT COUNT(*) FROM revisions").fetchone()[0]
            return counts
