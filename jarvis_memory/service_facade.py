"""Stable, transport-neutral API for sharing JARVIS memory between agents.

The facade intentionally contains no MCP or HTTP code.  Local tools and future
gateways can expose the same operations without gaining direct database access.
Agent writes begin as proposals; only an explicit commit makes them recallable.
"""
from __future__ import annotations

import re
import time

from .knowledge import KnowledgeStore


class MemoryServiceError(ValueError):
    """Invalid universal-memory request."""


class UniversalMemoryService:
    def __init__(self, store: KnowledgeStore):
        self.store = store

    @staticmethod
    def _limit(limit):
        if type(limit) is not int or not 1 <= limit <= 50:
            raise MemoryServiceError("limit must be an integer from 1 to 50")
        return limit

    @staticmethod
    def _cursor(cursor):
        if cursor in (None, ""):
            return 0
        if not isinstance(cursor, str) or not cursor.isascii() or not cursor.isdigit():
            raise MemoryServiceError("cursor must be a decimal offset")
        return int(cursor)

    @staticmethod
    def _values(name, values):
        if values is None:
            return None
        if not isinstance(values, (list, tuple)) or not all(isinstance(item, str) and item for item in values):
            raise MemoryServiceError(f"{name} must be a list of nonempty strings")
        return set(values)

    def search(self, query="", scopes=None, types=None, limit=20, cursor=None, *, include_proposals=False):
        if not isinstance(query, str) or len(query) > 500:
            raise MemoryServiceError("query must be a string of at most 500 characters")
        limit = self._limit(limit)
        offset = self._cursor(cursor)
        scopes = self._values("scopes", scopes)
        types = self._values("types", types)
        now = time.time()
        records = self.store.list(active_only=False)
        allowed_statuses = {"active", "proposed"} if include_proposals else {"active"}
        records = [record for record in records
                   if record["status"] in allowed_statuses
                   and (scopes is None or record["scope"] in scopes)
                   and (types is None or record["kind"] in types)
                   and (record["expires_at"] is None or record["expires_at"] > now)]
        terms = set(re.findall(r"\w+", query.casefold(), flags=re.UNICODE))
        authority_weight = {"user": 5, "verified": 4, "tool": 3, "agent": 2, "summary": 1}

        def score(record):
            words = set(re.findall(r"\w+", record["text"].casefold(), flags=re.UNICODE))
            lexical = len(terms & words) / max(1, len(terms)) if terms else 0
            return lexical, authority_weight.get(record["authority"], 0), record["updated_at"]

        if terms:
            records = [record for record in records if score(record)[0] > 0]
        records.sort(key=score, reverse=True)
        page = records[offset:offset + limit]
        next_offset = offset + len(page)
        return {"records": page, "count": len(page),
                "next_cursor": str(next_offset) if next_offset < len(records) else None}

    def read(self, record_id):
        record = self.store.get(record_id)
        if record is None:
            raise KeyError(record_id)
        return record

    def propose(self, record, evidence_refs=()):
        if not isinstance(record, dict):
            raise MemoryServiceError("record must be an object")
        allowed = {"text", "kind", "key", "source", "evidence", "confidence", "scope",
                   "author", "agent_id", "observed_at", "expires_at", "authority",
                   "sensitivity", "source_hash"}
        unknown = set(record) - allowed
        if unknown:
            raise MemoryServiceError("unsupported record fields: " + ", ".join(sorted(unknown)))
        if "text" not in record:
            raise MemoryServiceError("record.text is required")
        values = dict(record)
        values["evidence_refs"] = evidence_refs
        return self.store.propose(**values)

    def commit(self, proposal_id):
        return self.store.commit(proposal_id)

    def correct(self, record_id, replacement, reason="", *, author="user", agent_id="",
                authority="user"):
        return self.store.correct(record_id, replacement, reason, author=author,
                                  agent_id=agent_id, authority=authority)

    def history(self, record_id):
        return self.store.history(record_id)

    def forget(self, record_id):
        return self.store.forget(record_id)

    def status(self):
        return {"service": "universal-memory", "schema_version": 1,
                "storage": "sqlite", "operations": ["search", "read", "propose", "commit",
                                                            "correct", "history", "forget", "status"],
                "records": self.store.stats()}


__all__ = ["MemoryServiceError", "UniversalMemoryService"]
