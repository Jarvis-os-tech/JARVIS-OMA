from pathlib import Path
import tempfile
import time
import unittest

from jarvis_memory.knowledge import KnowledgeStore
from jarvis_memory.service_facade import MemoryServiceError, UniversalMemoryService


class UniversalMemoryServiceTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        store = KnowledgeStore(Path(self.directory.name) / "knowledge.db")
        self.service = UniversalMemoryService(store)

    def test_proposals_are_hidden_until_commit(self):
        proposed = self.service.propose({
            "text": "Beta launches Friday", "kind": "decision", "key": "beta-launch",
            "scope": "project:jarvis", "author": "codex", "agent_id": "codex",
            "authority": "agent", "source": "codex-session",
        }, ["session:codex:42"])
        self.assertEqual(self.service.search("beta", scopes=["project:jarvis"])["records"], [])
        self.assertEqual(self.service.search("beta", include_proposals=True)["records"][0]["id"],
                         proposed["id"])
        committed = self.service.commit(proposed["id"])
        self.assertEqual(self.service.search("beta")["records"][0]["id"], committed["id"])
        self.assertEqual(self.service.read(committed["id"])["evidence_refs"], ["session:codex:42"])

    def test_scope_type_expiry_and_cursor_filters(self):
        for index in range(3):
            proposal = self.service.propose({
                "text": f"SQLite decision {index}", "kind": "decision", "scope": "project:jarvis",
                "author": "agent", "agent_id": "agent", "authority": "verified",
            })
            self.service.commit(proposal["id"])
        expired = self.service.propose({
            "text": "SQLite stale observation", "kind": "observation", "scope": "project:jarvis",
            "expires_at": time.time() - 1,
        })
        self.service.commit(expired["id"])
        other = self.service.propose({"text": "SQLite elsewhere", "scope": "project:other"})
        self.service.commit(other["id"])
        first = self.service.search("SQLite", ["project:jarvis"], ["decision"], limit=2)
        second = self.service.search("SQLite", ["project:jarvis"], ["decision"], limit=2,
                                     cursor=first["next_cursor"])
        self.assertEqual(first["count"], 2)
        self.assertEqual(second["count"], 1)
        self.assertIsNone(second["next_cursor"])

    def test_correction_history_forget_and_status(self):
        proposal = self.service.propose({"text": "Uses tea", "key": "drink"})
        committed = self.service.commit(proposal["id"])
        corrected = self.service.correct(committed["id"], "Uses water", "User corrected it")
        self.assertEqual(corrected["authority"], "user")
        self.assertGreaterEqual(len(self.service.history(corrected["id"])), 4)
        self.assertEqual(self.service.forget(corrected["id"])["deleted"], 2)
        self.assertEqual(self.service.status()["schema_version"], 1)

    def test_request_validation(self):
        with self.assertRaises(MemoryServiceError):
            self.service.search(limit=0)
        with self.assertRaises(MemoryServiceError):
            self.service.search(cursor="bad")
        with self.assertRaises(MemoryServiceError):
            self.service.propose({"text": "x", "unknown": True})


if __name__ == "__main__":
    unittest.main()
