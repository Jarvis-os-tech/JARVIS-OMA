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
from hashlib import sha256


KINDS = frozenset({"fact", "preference", "decision", "goal", "constraint",
                   "observation", "event", "entity", "procedure", "task", "project"})
_SCHEMA = """
CREATE TABLE IF NOT EXISTS entries (
 id TEXT PRIMARY KEY, text TEXT NOT NULL, kind TEXT NOT NULL,
 key TEXT NOT NULL, source TEXT NOT NULL, evidence TEXT,
 confidence REAL NOT NULL, status TEXT NOT NULL,
 created_at REAL NOT NULL, updated_at REAL NOT NULL, family TEXT NOT NULL,
 scope TEXT NOT NULL DEFAULT 'user', author TEXT NOT NULL DEFAULT '',
 agent_id TEXT NOT NULL DEFAULT '', observed_at REAL,
 expires_at REAL, authority TEXT NOT NULL DEFAULT 'agent',
 sensitivity TEXT NOT NULL DEFAULT 'private', superseded_by TEXT,
 source_hash TEXT NOT NULL DEFAULT '', evidence_refs TEXT NOT NULL DEFAULT '[]'
);
CREATE UNIQUE INDEX IF NOT EXISTS active_keys ON entries(key)
 WHERE key <> '' AND status = 'active';
CREATE TABLE IF NOT EXISTS revisions (
 sequence INTEGER PRIMARY KEY AUTOINCREMENT, family TEXT NOT NULL,
 snapshot TEXT NOT NULL
);
"""

_MIGRATION_COLUMNS = {
    "scope": "TEXT NOT NULL DEFAULT 'user'",
    "author": "TEXT NOT NULL DEFAULT ''",
    "agent_id": "TEXT NOT NULL DEFAULT ''",
    "observed_at": "REAL",
    "expires_at": "REAL",
    "authority": "TEXT NOT NULL DEFAULT 'agent'",
    "sensitivity": "TEXT NOT NULL DEFAULT 'private'",
    "superseded_by": "TEXT",
    "source_hash": "TEXT NOT NULL DEFAULT ''",
    "evidence_refs": "TEXT NOT NULL DEFAULT '[]'",
}
AUTHORITIES = frozenset({"user", "verified", "tool", "agent", "summary"})
SENSITIVITIES = frozenset({"public", "internal", "private", "secret-forbidden"})


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
                existing = {row[1] for row in connection.execute("PRAGMA table_info(entries)")}
                for name, declaration in _MIGRATION_COLUMNS.items():
                    if name not in existing:
                        connection.execute(f"ALTER TABLE entries ADD COLUMN {name} {declaration}")
                for identifier, text in connection.execute(
                        "SELECT id,text FROM entries WHERE source_hash='' OR source_hash IS NULL"):
                    connection.execute("UPDATE entries SET source_hash=? WHERE id=?",
                                       (sha256(text.encode("utf-8")).hexdigest(), identifier))
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
        entry["evidence_refs"] = json.loads(entry["evidence_refs"] or "[]")
        return entry

    @staticmethod
    def _validate(text, kind, key, source, evidence, confidence, *, scope="user", author="",
                  agent_id="", observed_at=None, expires_at=None, authority="agent",
                  sensitivity="private", source_hash="", evidence_refs=()):
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
        for name, value in (("scope", scope), ("author", author), ("agent_id", agent_id),
                            ("authority", authority), ("sensitivity", sensitivity),
                            ("source_hash", source_hash)):
            if not isinstance(value, str):
                raise TypeError(f"{name} must be a string")
        if not scope.strip():
            raise ValueError("scope must not be blank")
        if authority not in AUTHORITIES:
            raise ValueError(f"unsupported authority: {authority}")
        if sensitivity not in SENSITIVITIES:
            raise ValueError(f"unsupported sensitivity: {sensitivity}")
        for name, value in (("observed_at", observed_at), ("expires_at", expires_at)):
            if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float))):
                raise TypeError(f"{name} must be a number or None")
            if value is not None and not math.isfinite(value):
                raise ValueError(f"{name} must be finite")
        if not isinstance(evidence_refs, (list, tuple)) or not all(isinstance(item, str) and item for item in evidence_refs):
            raise TypeError("evidence_refs must be a list or tuple of nonempty strings")
        encoded_evidence = json.dumps(evidence, allow_nan=False) if evidence is not None else None
        encoded_refs = json.dumps(list(evidence_refs), allow_nan=False)
        return encoded_evidence, encoded_refs

    def _record(self, connection, row, action, reason=""):
        snapshot = self._entry(row)
        snapshot.update(action=action, reason=reason)
        connection.execute("INSERT INTO revisions(family, snapshot) VALUES (?, ?)",
                           (row["family"], json.dumps(snapshot, allow_nan=False)))

    def _insert(self, connection, text, kind, key, source, evidence, confidence,
                family=None, action="created", reason="", *, memory_id=None, status="active",
                scope="user", author="", agent_id="", observed_at=None, expires_at=None,
                authority="agent", sensitivity="private", source_hash="", evidence_refs="[]"):
        memory_id = memory_id or uuid4().hex
        now = time.time()
        connection.execute(
            "INSERT INTO entries (id,text,kind,key,source,evidence,confidence,status,created_at,updated_at,"
            "family,scope,author,agent_id,observed_at,expires_at,authority,sensitivity,superseded_by,"
            "source_hash,evidence_refs) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (memory_id, text, kind, key, source, evidence, confidence, status, now, now,
             family or memory_id, scope, author, agent_id, observed_at, expires_at, authority,
             sensitivity, None, source_hash or sha256(text.encode("utf-8")).hexdigest(), evidence_refs))
        row = connection.execute("SELECT * FROM entries WHERE id=?", (memory_id,)).fetchone()
        self._record(connection, row, action, reason)
        return self._entry(row)

    def upsert(self, text, kind="fact", key="", source="", evidence=None, confidence=1.0, *,
               scope="user", author="", agent_id="", observed_at=None, expires_at=None,
               authority="agent", sensitivity="private", source_hash="", evidence_refs=()):
        encoded, encoded_refs = self._validate(
            text, kind, key, source, evidence, confidence, scope=scope, author=author,
            agent_id=agent_id, observed_at=observed_at, expires_at=expires_at,
            authority=authority, sensitivity=sensitivity, source_hash=source_hash,
            evidence_refs=evidence_refs)
        with self._connection(write=True) as connection:
            duplicate = connection.execute(
                "SELECT * FROM entries WHERE text=? AND kind=? AND key=? AND status='active'",
                (text, kind, key)).fetchone()
            if duplicate:
                # Identical observations are idempotent. New evidence is kept
                # as a revision, while the initial source remains in history.
                if (duplicate["source"], duplicate["evidence"], duplicate["confidence"],
                    duplicate["evidence_refs"]) != (source, encoded, confidence, encoded_refs):
                    connection.execute("UPDATE entries SET source=?, evidence=?, confidence=?, evidence_refs=?, updated_at=? WHERE id=?",
                                       (source, encoded, confidence, encoded_refs, time.time(), duplicate["id"]))
                    duplicate = connection.execute("SELECT * FROM entries WHERE id=?", (duplicate["id"],)).fetchone()
                    self._record(connection, duplicate, "evidence")
                return self._entry(duplicate)
            previous = connection.execute("SELECT * FROM entries WHERE key=? AND status='active'", (key,)).fetchone() if key else None
            memory_id = uuid4().hex
            if previous:
                self._supersede(connection, previous, "explicit key replacement", memory_id)
            return self._insert(connection, text, kind, key, source, encoded, confidence,
                                family=previous["family"] if previous else None, memory_id=memory_id,
                                scope=scope, author=author, agent_id=agent_id,
                                observed_at=observed_at, expires_at=expires_at, authority=authority,
                                sensitivity=sensitivity, source_hash=source_hash, evidence_refs=encoded_refs)

    def _supersede(self, connection, row, reason, superseded_by=None):
        connection.execute("UPDATE entries SET status='superseded', superseded_by=?, updated_at=? WHERE id=?",
                           (superseded_by, time.time(), row["id"]))
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

    def get(self, memory_id):
        self._id(memory_id)
        with self._connection() as connection:
            if connection is None:
                return None
            row = connection.execute("SELECT * FROM entries WHERE id=?", (memory_id,)).fetchone()
            return self._entry(row) if row is not None else None

    def propose(self, text, kind="fact", key="", source="", evidence=None, confidence=0.5, *,
                scope="user", author="", agent_id="", observed_at=None, expires_at=None,
                authority="agent", sensitivity="private", source_hash="", evidence_refs=()):
        encoded, encoded_refs = self._validate(
            text, kind, key, source, evidence, confidence, scope=scope, author=author,
            agent_id=agent_id, observed_at=observed_at, expires_at=expires_at,
            authority=authority, sensitivity=sensitivity, source_hash=source_hash,
            evidence_refs=evidence_refs)
        with self._connection(write=True) as connection:
            return self._insert(connection, text, kind, key, source, encoded, confidence,
                                status="proposed", action="proposed", evidence_refs=encoded_refs,
                                scope=scope, author=author, agent_id=agent_id,
                                observed_at=observed_at, expires_at=expires_at,
                                authority=authority, sensitivity=sensitivity,
                                source_hash=source_hash)

    def commit(self, memory_id):
        self._id(memory_id)
        with self._connection(write=True) as connection:
            row = connection.execute("SELECT * FROM entries WHERE id=?", (memory_id,)).fetchone()
            if row is None:
                raise KeyError(memory_id)
            if row["status"] != "proposed":
                raise ValueError("only proposed entries can be committed")
            previous = connection.execute(
                "SELECT * FROM entries WHERE key=? AND status='active'", (row["key"],)).fetchone() if row["key"] else None
            if previous:
                self._supersede(connection, previous, "committed proposal", memory_id)
                connection.execute("UPDATE entries SET family=? WHERE id=?", (previous["family"], memory_id))
            connection.execute("UPDATE entries SET status='active', updated_at=? WHERE id=?", (time.time(), memory_id))
            committed = connection.execute("SELECT * FROM entries WHERE id=?", (memory_id,)).fetchone()
            self._record(connection, committed, "committed")
            return self._entry(committed)

    def correct(self, memory_id, text, reason="", *, author="user", agent_id="",
                authority="user"):
        self._id(memory_id)
        if not isinstance(reason, str):
            raise TypeError("reason must be a string")
        if not isinstance(author, str) or not isinstance(agent_id, str):
            raise TypeError("author and agent_id must be strings")
        if authority not in AUTHORITIES:
            raise ValueError(f"unsupported authority: {authority}")
        self._validate(text, "fact", "", "", None, 1.0)
        if not self.path.exists():
            raise KeyError(memory_id)
        with self._connection(write=True) as connection:
            row = connection.execute("SELECT * FROM entries WHERE id=?", (memory_id,)).fetchone()
            if row is None:
                raise KeyError(memory_id)
            if row["status"] != "active":
                raise ValueError("only active entries can be corrected")
            replacement_id = uuid4().hex
            self._supersede(connection, row, reason, replacement_id)
            actor = agent_id or author or authority
            evidence_data = {"role": authority, "quote": text, "reason": reason}
            if authority != "user":
                evidence_data["actor"] = actor
            evidence = json.dumps(evidence_data)
            source = "explicit-user-correction" if authority == "user" else f"{actor}-correction"
            return self._insert(connection, text, row["kind"], row["key"], source,
                                evidence, 1.0, row["family"], "corrected", reason,
                                memory_id=replacement_id, scope=row["scope"], author=author,
                                agent_id=agent_id, observed_at=time.time(), authority=authority,
                                sensitivity=row["sensitivity"],
                                source_hash=sha256(text.encode("utf-8")).hexdigest(),
                                evidence_refs=row["evidence_refs"])

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
            counts = {"active": 0, "proposed": 0, "superseded": 0, "total": 0, "revisions": 0}
            if connection is not None:
                for status, count in connection.execute("SELECT status, COUNT(*) FROM entries GROUP BY status"):
                    counts[status] = count
                    counts["total"] += count
                counts["revisions"] = connection.execute("SELECT COUNT(*) FROM revisions").fetchone()[0]
            return counts
