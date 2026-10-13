import math
import os
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest

from jarvis_memory.vector_store import VectorStore


class FakeProvider:
    def __init__(self, identity="fake-v1", dimension=2):
        self.identity = identity
        self.dimension = dimension
        self.calls = []

    def embed(self, texts):
        self.calls.append(list(texts))
        vectors = {
            "east": [1.0, 0.0],
            "north": [0.0, 1.0],
            "west": [-1.0, 0.0],
            "tie-a": [1.0, 1.0],
            "tie-b": [2.0, 2.0],
        }
        return [vectors[text][: self.dimension] for text in texts]


class VectorStoreTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / "nested" / "vectors.sqlite3"

    def test_read_does_not_create_state(self):
        store = VectorStore(self.path)
        self.assertEqual(store.search("facts", [1.0, 0.0], "fake-v1"), [])
        self.assertFalse(self.path.parent.exists())

    def test_restart_cache_updates_and_stale_removal(self):
        provider = FakeProvider()
        store = VectorStore(self.path)
        records = [
            {"id": "a", "text": "east", "metadata": {"kind": "one"}},
            {"id": "b", "text": "north", "metadata": {"kind": "two"}},
        ]
        self.assertEqual(store.sync("facts", records, provider), {"embedded": 2, "removed": 0, "total": 2})
        restarted = VectorStore(self.path)
        self.assertEqual(restarted.sync("facts", records, provider)["embedded"], 0)
        records = [{"id": "a", "text": "west", "metadata": {"kind": "changed"}}]
        self.assertEqual(restarted.sync("facts", records, provider), {"embedded": 1, "removed": 1, "total": 1})
        result = restarted.search("facts", [-1, 0], provider.identity)
        self.assertEqual(result, [{"kind": "changed", "semantic_score": 1.0, "content": "west", "id": "a"}])

    def test_namespaces_filters_threshold_and_copied_metadata(self):
        provider = FakeProvider()
        store = VectorStore(self.path)
        store.sync("facts", [{"id": "same", "text": "east", "metadata": {"scope": "fact"}}], provider)
        store.sync("docs", [{"id": "same", "text": "north", "metadata": {"scope": "doc"}}], provider)
        results = store.search(["facts", "docs"], [1, 0], provider.identity, limit=5, min_score=0.1)
        self.assertEqual([item["scope"] for item in results], ["fact"])
        results[0]["scope"] = "mutated"
        self.assertEqual(store.search("facts", [1, 0], provider.identity)[0]["scope"], "fact")

    def test_model_and_dimension_mismatch_do_not_search(self):
        provider = FakeProvider("model-a", 2)
        store = VectorStore(self.path)
        store.sync("facts", [{"id": "a", "text": "east", "metadata": {}}], provider)
        self.assertEqual(store.search("facts", [1, 0], "model-b"), [])
        self.assertEqual(store.search("facts", [1, 0, 0], "model-a"), [])

        changed = FakeProvider("model-a", 1)
        store.sync("facts", [{"id": "a", "text": "east", "metadata": {}}], changed)
        self.assertEqual(changed.calls, [["east"]])
        self.assertEqual(store.search("facts", [1], "model-a")[0]["id"], "a")

    def test_ties_are_deterministic(self):
        provider = FakeProvider()
        store = VectorStore(self.path)
        store.sync("facts", [
            {"id": "z", "text": "tie-a", "metadata": {}},
            {"id": "a", "text": "tie-b", "metadata": {}},
        ], provider)
        self.assertEqual([item["id"] for item in store.search("facts", [1, 1], provider.identity)], ["a", "z"])
        store.sync("other", [{"id": "a", "text": "tie-a", "metadata": {"origin": "other"}}], provider)
        first = store.search(["other", "facts"], [1, 1], provider.identity)
        second = store.search(["facts", "other"], [1, 1], provider.identity)
        self.assertEqual(first, second)

    def test_rejects_invalid_vectors_and_records(self):
        store = VectorStore(self.path)
        provider = FakeProvider()
        for vector in ([0, 0], [math.nan, 0], [math.inf, 0], []):
            with self.subTest(vector=vector):
                with self.assertRaises(ValueError):
                    store.search("facts", vector, provider.identity)
        provider.embed = lambda texts: [[0.0, 0.0] for _ in texts]
        with self.assertRaises(ValueError):
            store.sync("facts", [{"id": "a", "text": "east", "metadata": {}}], provider)
        with self.assertRaises(ValueError):
            store.sync("facts", [{"id": "a", "text": "east", "metadata": []}], FakeProvider())

    @unittest.skipIf(os.name == "nt", "POSIX mode bits are not available on Windows")
    def test_database_permissions_are_private(self):
        VectorStore(self.path).sync("facts", [], FakeProvider())
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)

    def test_concurrent_syncs_leave_valid_database(self):
        store = VectorStore(self.path)
        barrier = threading.Barrier(5)
        errors = []

        def sync(index):
            try:
                barrier.wait()
                store.sync(f"ns-{index}", [{"id": str(index), "text": "east", "metadata": {"n": index}}], FakeProvider())
            except Exception as exc:  # pragma: no cover - asserted below
                errors.append(exc)

        threads = [threading.Thread(target=sync, args=(index,)) for index in range(5)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(errors, [])
        with sqlite3.connect(self.path) as connection:
            self.assertEqual(connection.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            self.assertEqual(connection.execute("SELECT count(*) FROM vectors").fetchone()[0], 5)


if __name__ == "__main__":
    unittest.main()
