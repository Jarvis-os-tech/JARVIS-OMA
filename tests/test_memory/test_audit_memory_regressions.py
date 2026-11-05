import json
from pathlib import Path
import tempfile
import time
import unittest

from jarvis_memory.knowledge import KnowledgeStore
from jarvis_memory.mcp_server import AuditLog, ClientPolicy, UniversalMemoryMCP
from jarvis_memory.service_facade import UniversalMemoryService


class MemoryAuditRegressionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = KnowledgeStore(self.root / "knowledge.db")
        self.service = UniversalMemoryService(self.store)
        self.mcp = UniversalMemoryMCP(
            self.service,
            ClientPolicy("reader", frozenset({"project:test"}), frozenset({"project:test"}),
                         frozenset({"commit", "correct", "forget"})),
            AuditLog(self.root / "audit.jsonl"))

    def test_secret_forbidden_is_hidden_from_search_read_and_history(self):
        secret = self.store.upsert("SECRET-CANARY private text", key="memo", scope="project:test",
                                   sensitivity="secret-forbidden", evidence={"quote": "SECRET-EVIDENCE"})
        visible = self.store.upsert("Ordinary replacement", key="memo", scope="project:test")

        self.assertEqual(self.service.search("SECRET-CANARY", scopes=["project:test"])["records"], [])
        with self.assertRaises(KeyError):
            self.service.read(secret["id"])
        history = self.service.history(visible["id"])
        self.assertFalse(any(item["sensitivity"] == "secret-forbidden" for item in history))
        self.assertFalse(any("SECRET-EVIDENCE" in json.dumps(item) for item in history))
        self.assertEqual(self.mcp.call_tool("memory_search", {"query": "SECRET-CANARY"})["records"], [])
        self.assertEqual(self.mcp.call_tool("memory_history", {"record_id": visible["id"]})["revisions"], history)

    def test_secret_forbidden_mutations_cannot_return_record_content(self):
        secret_proposal = self.store.propose("SECRET-COMMIT-CANARY", scope="project:test",
                                             sensitivity="secret-forbidden")
        secret_active = self.store.upsert("SECRET-CORRECT-CANARY", key="restricted", scope="project:test",
                                          sensitivity="secret-forbidden")
        for tool, args in (
                ("memory_commit", {"proposal_id": secret_proposal["id"]}),
                ("memory_correct", {"record_id": secret_active["id"], "replacement": "leak"}),
                ("memory_forget", {"record_id": secret_active["id"]})):
            with self.subTest(tool=tool), self.assertRaises(KeyError):
                self.mcp.call_tool(tool, args)
        self.assertIn("SECRET-COMMIT-CANARY", self.store.get(secret_proposal["id"])["text"])
        self.assertEqual(self.store.get(secret_active["id"])["text"], "SECRET-CORRECT-CANARY")

    def test_duplicate_upsert_refreshes_expiry_without_downgrading_authority(self):
        first = self.store.upsert("Same fact", key="fact", scope="project:test",
                                  expires_at=time.time() - 1, authority="user", sensitivity="private")
        refreshed = self.store.upsert("Same fact", key="fact", scope="project:test",
                                      expires_at=None, authority="user", sensitivity="public")
        self.assertEqual(first["id"], refreshed["id"])
        self.assertIsNone(refreshed["expires_at"])
        self.assertEqual(refreshed["authority"], "user")
        self.assertEqual(refreshed["sensitivity"], "private")
        self.assertEqual(self.store.history(first["id"])[-1]["action"], "evidence")

    def test_lower_authority_duplicate_preserves_user_evidence_and_expiry(self):
        expiry = time.time() + 60
        first = self.store.upsert("User fact", key="user-fact", authority="user",
                                  evidence={"quote": "User fact"}, source="explicit-user",
                                  expires_at=expiry)
        repeated = self.store.upsert("User fact", key="user-fact", authority="agent",
                                     evidence={"quote": "Agent guess"}, expires_at=None)
        self.assertEqual(repeated["expires_at"], expiry)
        self.assertEqual(repeated["evidence"], first["evidence"])
        self.assertEqual(repeated["source"], "explicit-user")

    def test_omitted_expiry_preserves_expiry_and_explicit_none_clears_it(self):
        expiry = time.time() + 60
        first = self.store.upsert("Timed fact", expires_at=expiry)
        self.assertEqual(self.store.upsert("Timed fact")["expires_at"], expiry)
        self.assertIsNone(self.store.upsert("Timed fact", expires_at=None)["expires_at"])
        self.assertEqual(self.store.get(first["id"])["expires_at"], None)

    def test_reclassification_hides_earlier_snapshots_of_the_same_record(self):
        first = self.store.upsert("RECLASSIFIED-CANARY", key="reclassified", scope="project:test")
        self.store.upsert("RECLASSIFIED-CANARY", key="reclassified", scope="project:test",
                          sensitivity="secret-forbidden")
        visible = self.store.upsert("Public replacement", key="reclassified", scope="project:test")
        history = self.mcp.call_tool("memory_history", {"record_id": visible["id"]})["revisions"]
        self.assertFalse(any(row["id"] == first["id"] for row in history))
        self.assertNotIn("RECLASSIFIED-CANARY", json.dumps(history))

    def test_duplicate_upsert_keeps_restrictive_sensitivity_and_accepts_higher_authority(self):
        first = self.store.upsert("Same secret", key="secret", scope="project:test",
                                  authority="agent", sensitivity="secret-forbidden")
        refreshed = self.store.upsert("Same secret", key="secret", scope="project:test",
                                      authority="verified", sensitivity="private")
        self.assertEqual(refreshed["authority"], "verified")
        self.assertEqual(refreshed["sensitivity"], "secret-forbidden")
        self.assertEqual(self.store.history(first["id"])[-1]["sensitivity"], "secret-forbidden")


if __name__ == "__main__":
    unittest.main()
