"""Dependency-free SQLite cache and cosine search for semantic memory."""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import sqlite3
import struct
from typing import Any, Iterable, Mapping, Sequence


_SCHEMA = """
CREATE TABLE IF NOT EXISTS vectors (
    namespace TEXT NOT NULL,
    source_id TEXT NOT NULL,
    content TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    metadata TEXT NOT NULL,
    provider_identity TEXT NOT NULL,
    dimension INTEGER NOT NULL,
    embedding BLOB NOT NULL,
    PRIMARY KEY (namespace, source_id)
)
"""


class VectorStore:
    """Persist validated embeddings while opening a fresh connection per call."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).expanduser()

    @staticmethod
    def _identity(provider: Any) -> str:
        value = getattr(provider, "identity", None)
        value = value() if callable(value) else value
        if not isinstance(value, str) or not value:
            raise ValueError("provider.identity must be a non-empty string")
        return value

    @staticmethod
    def _declared_dimension(provider: Any) -> int | None:
        value = getattr(provider, "dimension", None)
        if value is None:
            value = getattr(provider, "dim", None)
        if value is None:
            value = getattr(provider, "dimensions", None)
        value = value() if callable(value) else value
        if value is None:
            return None
        if isinstance(value, bool) or int(value) <= 0:
            raise ValueError("provider dimension must be a positive integer")
        return int(value)

    @staticmethod
    def _vector(values: Sequence[float], expected: int | None = None) -> tuple[float, ...]:
        try:
            vector = tuple(float(value) for value in values)
        except (TypeError, ValueError) as exc:
            raise ValueError("embedding must be a sequence of numbers") from exc
        if not vector or any(not math.isfinite(value) for value in vector):
            raise ValueError("embedding must contain finite numbers")
        if expected is not None and len(vector) != expected:
            raise ValueError(f"embedding dimension {len(vector)} does not match {expected}")
        if not any(value != 0.0 for value in vector):
            raise ValueError("embedding must not be a zero vector")
        return vector

    @staticmethod
    def _pack(vector: Sequence[float]) -> bytes:
        return struct.pack(f"<{len(vector)}d", *vector)

    @staticmethod
    def _unpack(blob: bytes, dimension: int) -> tuple[float, ...]:
        if dimension <= 0 or len(blob) != dimension * 8:
            raise ValueError("stored embedding has an invalid dimension")
        return struct.unpack(f"<{dimension}d", blob)

    def _write_connection(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        connection = sqlite3.connect(self.path, timeout=30)
        try:
            os.chmod(self.path, 0o600)
            connection.execute("PRAGMA busy_timeout = 30000")
            connection.execute(_SCHEMA)
            connection.commit()
        except Exception:
            connection.close()
            raise
        return connection

    def sync(self, namespace: str, records: Iterable[Mapping[str, Any]], provider: Any) -> dict[str, int]:
        """Synchronize one namespace and embed only changed or incompatible rows."""
        if not isinstance(namespace, str) or not namespace:
            raise ValueError("namespace must be a non-empty string")
        identity = self._identity(provider)
        declared_dimension = self._declared_dimension(provider)
        prepared: dict[str, tuple[str, str, str]] = {}
        for record in records:
            if not isinstance(record, Mapping):
                raise ValueError("each record must be a mapping")
            source_id, content = record.get("id"), record.get("text")
            metadata = record.get("metadata", {})
            if not isinstance(source_id, str) or not source_id:
                raise ValueError("record id must be a non-empty string")
            if not isinstance(content, str):
                raise ValueError("record text must be a string")
            if not isinstance(metadata, Mapping):
                raise ValueError("record metadata must be a mapping")
            metadata_json = json.dumps(dict(metadata), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
            prepared[source_id] = (content, metadata_json, digest)

        connection = self._write_connection()
        try:
            connection.execute("BEGIN IMMEDIATE")
            existing = {
                row[0]: row[1:]
                for row in connection.execute(
                    "SELECT source_id, content_hash, provider_identity, dimension FROM vectors WHERE namespace = ?",
                    (namespace,),
                )
            }
            stale = set(existing) - set(prepared)
            if stale:
                connection.executemany(
                    "DELETE FROM vectors WHERE namespace = ? AND source_id = ?",
                    ((namespace, source_id) for source_id in stale),
                )
            changed_ids = [
                source_id for source_id, (_, _, digest) in prepared.items()
                if source_id not in existing
                or existing[source_id][0] != digest
                or existing[source_id][1] != identity
                or (declared_dimension is not None and existing[source_id][2] != declared_dimension)
            ]
            vectors = []
            batch_size = min(int(getattr(provider, "max_batch_size", 32)), 256)
            if batch_size <= 0:
                raise ValueError("provider max_batch_size must be positive")
            for offset in range(0, len(changed_ids), batch_size):
                batch_ids = changed_ids[offset:offset + batch_size]
                embed = getattr(provider, "embed_texts", None) or getattr(provider, "embed", None)
                if not callable(embed):
                    raise ValueError("provider must implement embed_texts")
                vectors.extend(embed([prepared[source_id][0] for source_id in batch_ids]))
            if len(vectors) != len(changed_ids):
                raise ValueError("provider returned the wrong number of embeddings")
            for source_id, raw_vector in zip(changed_ids, vectors):
                vector = self._vector(raw_vector, declared_dimension)
                content, metadata_json, digest = prepared[source_id]
                connection.execute(
                    "INSERT OR REPLACE INTO vectors VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (namespace, source_id, content, digest, metadata_json, identity, len(vector), self._pack(vector)),
                )
            # Metadata is not part of the embedding cache key, but remains current.
            for source_id, (_, metadata_json, _) in prepared.items():
                if source_id not in changed_ids:
                    connection.execute(
                        "UPDATE vectors SET metadata = ? WHERE namespace = ? AND source_id = ?",
                        (metadata_json, namespace, source_id),
                    )
            connection.commit()
            return {"embedded": len(changed_ids), "removed": len(stale), "total": len(prepared)}
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def clear(self, namespaces: str | Iterable[str] | None = None) -> int:
        """Remove cached vectors without creating a database when none exists."""
        if not self.path.is_file():
            return 0
        connection = self._write_connection()
        try:
            if namespaces is None:
                cursor = connection.execute("DELETE FROM vectors")
            else:
                selected = [namespaces] if isinstance(namespaces, str) else list(namespaces)
                if not selected or any(not isinstance(item, str) or not item for item in selected):
                    raise ValueError("namespaces must contain non-empty strings")
                placeholders = ",".join("?" for _ in selected)
                cursor = connection.execute(
                    f"DELETE FROM vectors WHERE namespace IN ({placeholders})", selected)
            connection.commit()
            return cursor.rowcount
        finally:
            connection.close()

    def search(
        self,
        namespaces: str | Iterable[str],
        query_vector: Sequence[float],
        provider_identity: str,
        limit: int = 10,
        min_score: float = -1.0,
    ) -> list[dict[str, Any]]:
        """Return deterministic cosine-ranked copies from existing state only."""
        query = self._vector(query_vector)
        if not isinstance(provider_identity, str) or not provider_identity:
            raise ValueError("provider_identity must be a non-empty string")
        limit = int(limit)
        if limit <= 0:
            return []
        min_score = float(min_score)
        if not math.isfinite(min_score):
            raise ValueError("min_score must be finite")
        selected = [namespaces] if isinstance(namespaces, str) else list(namespaces)
        if not selected or any(not isinstance(item, str) or not item for item in selected):
            raise ValueError("namespaces must contain non-empty strings")
        if not self.path.is_file():
            return []

        uri = f"file:{self.path.resolve().as_posix()}?mode=ro"
        connection = sqlite3.connect(uri, uri=True, timeout=30)
        try:
            placeholders = ",".join("?" for _ in selected)
            rows = connection.execute(
                f"SELECT namespace, source_id, content, metadata, dimension, embedding FROM vectors "
                f"WHERE provider_identity = ? AND namespace IN ({placeholders})",
                (provider_identity, *selected),
            )
            query_norm = math.sqrt(sum(value * value for value in query))
            ranked = []
            for namespace, source_id, content, metadata_json, dimension, blob in rows:
                if dimension != len(query):
                    continue
                vector = self._unpack(blob, dimension)
                norm = math.sqrt(sum(value * value for value in vector))
                if not math.isfinite(norm) or norm == 0:
                    continue
                score = sum(left * right for left, right in zip(query, vector)) / (query_norm * norm)
                if math.isfinite(score) and score >= min_score:
                    result = dict(json.loads(metadata_json))
                    result.update(semantic_score=score, content=content, id=source_id)
                    ranked.append((result, namespace))
            ranked.sort(key=lambda item: (-item[0]["semantic_score"], item[0]["id"], item[1]))
            return [item[0] for item in ranked[:limit]]
        finally:
            connection.close()
