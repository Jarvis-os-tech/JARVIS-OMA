"""Evidence ledger tests use isolated temporary state and no cloud services."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import stat
import tempfile
import unittest

from jarvis_memory.knowledge import KnowledgeStore


class KnowledgeStoreTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "state" / "knowledge.sqlite"
        self.store = KnowledgeStore(self.path)

    def test_reads_do_not_create_state(self):
        self.assertEqual(self.store.list(), [])
        self.assertEqual(self.store.history("missing"), [])
        self.assertEqual(self.store.stats()["total"], 0)
        self.assertEqual(self.store.forget("missing"), {"deleted": 0})
        self.assertEqual(self.store.clear(), {"deleted": 0})
        with self.assertRaises(KeyError):
            self.store.correct("missing", "new")
        self.assertFalse(self.path.parent.exists())

    def test_restart_permissions_and_exact_dedup(self):
        evidence = {"role": "user", "quote": "Synthetic test statement"}
        first = self.store.upsert("Prefers tea", evidence=evidence)
        self.assertIsInstance(first["id"], str)
        self.assertEqual(set(first), {"id", "text", "kind", "key", "source", "evidence",
                                      "confidence", "status", "created_at", "updated_at"})
        restarted = KnowledgeStore(self.path)
        self.assertEqual(restarted.upsert("Prefers tea", evidence=evidence), first)
        self.assertEqual(restarted.stats()["revisions"], 1)
        self.assertEqual(restarted.list()[0]["evidence"], evidence)
        restarted.upsert("prefers tea")
        restarted.upsert("Prefers coffee")
        self.assertEqual(len(restarted.list()), 3)
        self.assertEqual(stat.S_IMODE(self.path.stat().st_mode), 0o600)

    def test_key_supersession_and_corrections_preserve_evidence(self):
        old = self.store.upsert("Tea", key="drink", source="test", evidence={"quote": "Tea"})
        new = self.store.upsert("Coffee", key="drink", evidence={"quote": "Coffee"})
        self.assertEqual([entry["id"] for entry in self.store.list()], [new["id"]])
        self.assertEqual(self.store.list(False)[0]["status"], "superseded")
        corrected = self.store.correct(new["id"], "Water", "Explicit correction")
        self.assertEqual(corrected["key"], "drink")
        self.assertEqual(corrected["evidence"],
                         {"role": "user", "quote": "Water", "reason": "Explicit correction"})
        self.assertEqual(corrected["source"], "explicit-user-correction")
        self.assertEqual(corrected["confidence"], 1.0)
        history = self.store.history(old["id"])
        self.assertEqual(history, self.store.history(corrected["id"]))
        self.assertEqual(history[0]["source"], "test")
        self.assertEqual(history[0]["evidence"], {"quote": "Tea"})
        self.assertTrue(any(item["evidence"] == {"quote": "Coffee"} for item in history))
        self.assertEqual(history[-1]["reason"], "Explicit correction")
        with self.assertRaises(ValueError):
            self.store.correct(old["id"], "Must not resurrect")

    def test_reobservations_preserve_both_sources(self):
        first = self.store.upsert("Tea", source="one", evidence={"quote": "one"})
        second = self.store.upsert("Tea", source="two", evidence={"quote": "two"}, confidence=.5)
        self.assertEqual(first["id"], second["id"])
        self.assertEqual([item["source"] for item in self.store.history(first["id"])], ["one", "two"])

    def test_task_project_and_corrected_active_evidence(self):
        for kind in ("task", "project"):
            with self.subTest(kind=kind):
                old = self.store.upsert("Uses Hermes", kind=kind, key=kind,
                                        source="automatic", confidence=.4,
                                        evidence={"role": "user", "quote": "Uses Hermes"})
                new = self.store.correct(old["id"], "Uses OMP")
                self.assertEqual(new["kind"], kind)
                self.assertEqual(new["evidence"],
                                 {"role": "user", "quote": "Uses OMP", "reason": ""})
                self.assertEqual(new["source"], "explicit-user-correction")
                self.assertEqual(new["confidence"], 1.0)
                self.assertEqual(self.store.history(new["id"])[0]["evidence"], old["evidence"])
        self.assertTrue(all("Hermes" not in str(item["evidence"]) for item in self.store.list()))

    def test_unkeyed_correction_and_deletion_of_entire_family(self):
        first = self.store.upsert("Old synthetic fact")
        corrected = self.store.correct(first["id"], "Correct synthetic fact")
        self.assertEqual(corrected["key"], "")
        self.assertEqual(self.store.forget(first["id"]), {"deleted": 2})
        restarted = KnowledgeStore(self.path)
        self.assertEqual(restarted.list(False), [])
        self.assertEqual(restarted.history(corrected["id"]), [])
        self.assertEqual(restarted.stats()["revisions"], 0)
        self.store.upsert("Another synthetic fact")
        self.assertEqual(self.store.clear(), {"deleted": 1})
        self.assertEqual(restarted.stats()["total"], 0)
        self.assertEqual(restarted.stats()["revisions"], 0)

    def test_cross_instance_concurrent_writes(self):
        def write(index):
            store = KnowledgeStore(self.path)
            store.upsert("Shared synthetic fact")
            return store.upsert(f"Value {index}", key="shared-key")
        with ThreadPoolExecutor(max_workers=8) as executor:
            results = list(executor.map(write, range(32)))
        restarted = KnowledgeStore(self.path)
        self.assertEqual(restarted.stats()["active"], 2)
        self.assertEqual(restarted.stats()["superseded"], 31)
        self.assertEqual(len({item["id"] for item in results}), 32)
        self.assertEqual(len(restarted.list(False)), 33)

    def test_invalid_inputs_do_not_create_state(self):
        invalid = [({"text": None}, TypeError), ({"text": " "}, ValueError),
                   ({"kind": "unsupported"}, ValueError), ({"kind": []}, TypeError),
                   ({"key": 1}, TypeError), ({"key": " "}, ValueError),
                   ({"source": {}}, TypeError), ({"evidence": object()}, TypeError),
                   ({"evidence": {"bad": float("nan")}}, ValueError)]
        for confidence in (-1, 2, float("nan"), float("inf")):
            invalid.append(({"confidence": confidence}, ValueError))
        for confidence in (True, "1", None):
            invalid.append(({"confidence": confidence}, TypeError))
        for values, error in invalid:
            with self.subTest(values=values), self.assertRaises(error):
                self.store.upsert(**({"text": "Synthetic fact"} | values))
        with self.assertRaises(TypeError):
            self.store.list("yes")
        with self.assertRaises(TypeError):
            self.store.history(1)
        self.assertFalse(self.path.exists())


if __name__ == "__main__":
    unittest.main()
