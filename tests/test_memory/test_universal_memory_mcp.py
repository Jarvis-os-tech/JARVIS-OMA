import io
import json
from pathlib import Path
import tempfile
import unittest

from jarvis_memory.knowledge import KnowledgeStore
from jarvis_memory.mcp_server import AuditLog, ClientPolicy, MCPMemoryError, UniversalMemoryMCP
from jarvis_memory.service_facade import UniversalMemoryService


class UniversalMemoryMCPTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        root = Path(self.directory.name)
        self.store = KnowledgeStore(root / "knowledge.db")
        self.service = UniversalMemoryService(self.store)
        self.audit_path = root / "audit.jsonl"
        self.server = UniversalMemoryMCP(self.service,
            ClientPolicy("codex", frozenset({"project:jarvis"}), frozenset({"project:jarvis"}),
                         frozenset({"propose", "commit"})), AuditLog(self.audit_path))

    def call(self, name, arguments, request_id=1):
        response = self.server.handle({"jsonrpc": "2.0", "id": request_id, "method": "tools/call",
                                       "params": {"name": name, "arguments": arguments}})
        self.assertNotIn("error", response)
        return json.loads(response["result"]["content"][0]["text"])

    def test_proposal_identity_scope_commit_and_audit(self):
        proposed = self.call("memory_propose", {"record": {
            "text": "Beta launches Friday", "kind": "decision", "scope": "project:jarvis",
            "author": "spoof", "agent_id": "spoof", "authority": "verified"}})
        self.assertEqual(proposed["author"], "codex")
        self.assertEqual(proposed["authority"], "agent")
        self.assertEqual(self.call("memory_search", {"query": "Beta"})["records"], [])
        committed = self.call("memory_commit", {"proposal_id": proposed["id"]}, 2)
        self.assertEqual(committed["status"], "active")
        lines = [json.loads(line) for line in self.audit_path.read_text().splitlines()]
        self.assertEqual([line["operation"] for line in lines], ["propose", "commit"])
        self.assertFalse(any("Beta" in json.dumps(line) for line in lines))

    def test_scope_and_permission_boundaries(self):
        denied = self.server.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {
            "name": "memory_propose", "arguments": {"record": {"text": "x", "scope": "project:other"}}}})
        self.assertIn("write scopes", denied["error"]["message"])
        denied = self.server.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {
            "name": "memory_forget", "arguments": {"record_id": "missing"}}})
        self.assertIn("unauthorized", denied["error"]["message"])
        with self.assertRaises(MCPMemoryError):
            ClientPolicy("bad id", frozenset({"x"}), frozenset())

    def test_tools_list_only_exposes_authorized_operations(self):
        response = self.server.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}})
        names = {tool["name"] for tool in response["result"]["tools"]}
        self.assertIn("memory_search", names)
        self.assertIn("memory_propose", names)
        self.assertNotIn("memory_forget", names)

    def test_stdio_protocol_and_size_limit(self):
        source = io.StringIO('\n'.join([
            json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}),
            json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}),
            "not-json", "x" * 300,
        ]) + "\n")
        output = io.StringIO()
        self.server.max_request_bytes = 200
        self.server.serve(source, output)
        responses = [json.loads(line) for line in output.getvalue().splitlines()]
        self.assertEqual(responses[0]["result"]["serverInfo"]["name"], "jarvis-universal-memory")
        self.assertEqual(responses[1]["error"]["code"], -32700)
        self.assertEqual(responses[2]["error"]["code"], -32600)

    def test_read_cannot_cross_scope(self):
        proposed = self.service.propose({"text": "Other secret", "scope": "project:other"})
        committed = self.service.commit(proposed["id"])
        response = self.server.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {
            "name": "memory_read", "arguments": {"record_id": committed["id"]}}})
        self.assertIn("read scopes", response["error"]["message"])

    def test_agent_correction_keeps_agent_authority(self):
        server = UniversalMemoryMCP(
            self.service,
            ClientPolicy("claude", frozenset({"project:jarvis"}),
                         frozenset({"project:jarvis"}),
                         frozenset({"propose", "commit", "correct"})),
            AuditLog(self.audit_path))
        proposed = server.call_tool("memory_propose", {"record": {
            "text": "Launch Friday", "kind": "decision", "scope": "project:jarvis"}})
        committed = server.call_tool("memory_commit", {"proposal_id": proposed["id"]})

        corrected = server.call_tool("memory_correct", {
            "record_id": committed["id"], "replacement": "Launch Monday",
            "reason": "Agent observed a newer plan"})

        self.assertEqual(corrected["author"], "claude")
        self.assertEqual(corrected["agent_id"], "claude")
        self.assertEqual(corrected["authority"], "agent")


if __name__ == "__main__":
    unittest.main()
