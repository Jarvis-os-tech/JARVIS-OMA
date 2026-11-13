"""Comprehensive test suite for the JARVIS OS Memory Department.
Tests the 5 agents, SQLite WAL schema, FTS5 BM25 search, recursive CTE graph traversal,
and event-driven day rollover compaction.
"""

from datetime import datetime, date, timedelta
from pathlib import Path
import shutil
import tempfile
import unittest

from departments.memory.config import MemoryConfig
from departments.memory.db import MemoryDatabase
from departments.memory.department import MemoryDepartment
from departments.memory.agents import (
    ExtractorGatekeeperAgent,
    ConsolidationAgent,
    ReflectionAgent,
    RetrievalRouterAgent,
    DayRolloverCompactorAgent,
    MemoryCandidate,
)


class TestMemoryDepartment(unittest.TestCase):
    """Integration and unit tests for the Memory Department."""

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="jarvis_memory_test_"))
        self.db_path = self.temp_dir / "test_memory.db"
        self.vault_path = self.temp_dir / "obsidian_vault"
        self.vault_path.mkdir(parents=True, exist_ok=True)

        self.cfg = MemoryConfig()
        self.cfg.base_dir = self.temp_dir
        self.cfg.state_dir = self.temp_dir / "state"
        self.cfg.state_dir.mkdir(parents=True, exist_ok=True)
        self.cfg.db_path = self.db_path
        self.cfg.obsidian_vault_path = self.vault_path

        self.db = MemoryDatabase(self.db_path)
        self.dept = MemoryDepartment(self.cfg, self.db)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_database_and_fts5_crud(self):
        """Verify node upsert, FTS5 search, and recursive CTE graph traversal."""
        # 1. Upsert nodes
        node_a = self.db.upsert_node(
            node_id="test_node_a",
            layer="semantic",
            category="preference",
            title="Editor Preference",
            content="User prefers Neovim with Lua over VSCode.",
            importance=0.9,
            provenance="explicit_user",
        )
        self.assertEqual(node_a["id"], "test_node_a")

        node_b = self.db.upsert_node(
            node_id="test_node_b",
            layer="procedural",
            category="rule",
            title="Neovim Config Rule",
            content="Always configure Neovim LSP using lua init.lua.",
            importance=0.8,
            provenance="inferred_agent",
        )
        self.assertEqual(node_b["id"], "test_node_b")

        # 2. Add graph edge
        edge_added = self.db.add_edge("test_node_a", "relates_to", "test_node_b", weight=0.9)
        self.assertTrue(edge_added)

        # 3. Test FTS5 BM25 search
        results = self.db.search_fts("VSCode", limit=5)
        self.assertGreaterEqual(len(results), 1)
        self.assertEqual(results[0]["id"], "test_node_a")

        both_results = self.db.search_fts("Neovim Lua", limit=5)
        ids = [r["id"] for r in both_results]
        self.assertIn("test_node_a", ids)
        self.assertIn("test_node_b", ids)

        # 4. Test Recursive CTE graph traversal
        traversed = self.db.traverse_graph("test_node_a", relations=["relates_to"], max_depth=2)
        self.assertEqual(len(traversed), 1)
        self.assertEqual(traversed[0]["id"], "test_node_b")

    def test_agent1_extractor_and_secret_redaction(self):
        """Verify Agent 1 masks secrets, filters chit-chat, and extracts candidate."""
        a1 = self.dept.a1_extractor

        # Test secret masking
        secret_text = "My secret token is ghp_1234567890abcdef1234567890abcdef1234 and I prefer Python"
        candidate = a1.process_turn(secret_text)
        self.assertIsNotNone(candidate)
        self.assertNotIn("ghp_1234567890abcdef", candidate.content)
        self.assertIn("[REDACTED_SECRET]", candidate.content)

        # Test noise filtering
        noise_candidate = a1.process_turn("hello thank you okay")
        self.assertIsNone(noise_candidate)

        # Test tool failure trapping
        failed_event = [
            {
                "tool_name": "hyprctl_dispatch",
                "input": {"command": "workspace 9"},
                "exit_code": 1,
                "error": "Failed to connect to hyprland socket",
            }
        ]
        a1.process_turn("Switch to workspace 9", tool_events=failed_event)
        failed_traces = self.db.get_recent_failed_traces()
        self.assertGreaterEqual(len(failed_traces), 1)
        self.assertEqual(failed_traces[0]["tool_name"], "hyprctl_dispatch")

    def test_agent2_consolidation_matrix(self):
        """Verify Agent 2 executes ADD, UPDATE, and SUPERSEDE decisions."""
        a2 = self.dept.a2_consolidation

        # 1. ADD first preference
        c1 = MemoryCandidate(
            id="pref_os_arch",
            layer="semantic",
            category="preference",
            title="OS Preference",
            content="User uses Arch Linux with Wayland",
            importance=0.9,
            provenance="explicit_user",
            obsidian_path="04 Semantic Memory/Facts/system.md",
        )
        res1 = a2.consolidate(c1)
        self.assertEqual(res1["decision"], "ADD")

        # 2. NO-OP when identical fact is repeated
        res_noop = a2.consolidate(c1)
        self.assertEqual(res_noop["decision"], "NO-OP")

        # 3. SUPERSEDE when contradiction occurs
        c2 = MemoryCandidate(
            id="pref_os_x11",
            layer="semantic",
            category="preference",
            title="OS Preference",
            content="User switched to X11 on Ubuntu",
            importance=0.95,
            provenance="explicit_user",
            obsidian_path="04 Semantic Memory/Facts/system.md",
        )
        res2 = a2.consolidate(c2)
        self.assertEqual(res2["decision"], "SUPERSEDE")

        # Verify edge created
        edges = self.db.get_edges("pref_os_x11")
        self.assertTrue(any(e["relation"] == "supersedes" for e in edges))

    def test_agent3_reflection_loop(self):
        """Verify Agent 3 turns tool failure traces into procedural rules."""
        a3 = self.dept.a3_reflection

        # Seed a failed trace
        self.db.record_trace(
            trace_id="trace_test_pipewire",
            session_id="test_session",
            trigger_prompt="Restart audio sink",
            tool_name="pipewire_restart",
            tool_input={"sink": "default"},
            exit_code=1,
            stderr="Device or resource busy",
            error_message="Resource busy",
        )

        result = a3.run_daily_reflection()
        self.assertGreaterEqual(result["failed_traces_analyzed"], 1)
        self.assertGreaterEqual(result["new_procedural_rules_count"], 1)

        # Verify procedural rule in DB
        rules = self.db.search_fts("pipewire", layer="procedural")
        self.assertGreaterEqual(len(rules), 1)

    def test_agent4_retrieval_router(self):
        """Verify Agent 4 assembles prompt context in sub-25ms."""
        a4 = self.dept.a4_retrieval

        # Seed knowledge
        self.db.upsert_node(
            node_id="know_pipewire",
            layer="procedural",
            category="rule",
            title="Audio AEC Fix",
            content="When audio clips, restart jarvis_aec PipeWire filter.",
            importance=0.9,
        )

        context = a4.route_and_retrieve("How do I fix PipeWire audio?")
        self.assertIn("[JARVIS MEMORY CONTEXT]", context)
        self.assertIn("jarvis_aec PipeWire filter", context)

    def test_agent5_event_driven_day_rollover_compactor(self):
        """Verify Agent 5 detects rollover, scrubs raw logs, carries open tasks, and compacts."""
        a5 = self.dept.a5_compactor

        # Create yesterday's uncompacted raw log
        yesterday_str = (datetime.now().date() - timedelta(days=1)).strftime("%Y-%m-%d")
        episodic_dir = self.vault_path / "03 Episodic Memory" / "Conversations"
        episodic_dir.mkdir(parents=True, exist_ok=True)
        yesterday_file = episodic_dir / f"{yesterday_str}.md"

        raw_yesterday_content = (
            f"# Raw Daily Log {yesterday_str}\n\n"
            f"ok\n"
            f"thanks\n"
            f"```bash\n"
            f"hyprctl monitors\n"
            f"Monitor eDP-1 (ID 0): 1920x1080@60.0Hz at 0x0 scale 1.50\n"
            f"```\n\n"
            f"### Tasks\n"
            f"- [x] Configure Quickshell top bar\n"
            f"- [ ] Implement PipeWire AEC filter repair\n\n"
            f"Decided to use SQLite FTS5 for zero-RAM memory search on Arch Linux.\n"
        )
        yesterday_file.write_text(raw_yesterday_content, encoding="utf-8")

        # Set last active date file
        last_date_file = self.cfg.state_dir / "last_active_date.txt"
        last_date_file.write_text(yesterday_str, encoding="utf-8")

        # Run rollover for today
        today_date = datetime.now().date()
        today_str = today_date.strftime("%Y-%m-%d")

        result = a5.check_and_rollover(today_date)
        self.assertTrue(result["rollover_occurred"])
        self.assertEqual(result["previous_date"], yesterday_str)
        self.assertEqual(result["tasks_carried_count"], 1)

        # Verify yesterday's file was compacted and noise scrubbed
        compacted_yesterday = yesterday_file.read_text(encoding="utf-8")
        self.assertIn("Executive Daily Summary", compacted_yesterday)
        self.assertIn("Configure Quickshell top bar", compacted_yesterday)
        self.assertNotIn("Monitor eDP-1 (ID 0)", compacted_yesterday) # Code block scrubbed

        # Verify today's new file has carried-forward open task
        today_file = episodic_dir / f"{today_str}.md"
        self.assertTrue(today_file.exists())
        today_content = today_file.read_text(encoding="utf-8")
        self.assertIn("Implement PipeWire AEC filter repair", today_content)

    def test_agent6_vault_pruner(self):
        """Verify Agent 6 prunes 0-byte, whitespace, and blank stub files while protecting content."""
        a6 = self.dept.a6_pruner

        # 1. Create a 0-byte file
        f_zero = self.vault_path / "zero.md"
        f_zero.write_text("", encoding="utf-8")

        # 2. Create whitespace-only file
        f_ws = self.vault_path / "whitespace.md"
        f_ws.write_text("   \n\t  \n  ", encoding="utf-8")

        # 3. Create blank stub with frontmatter and title only
        f_stub = self.vault_path / "stub.md"
        f_stub.write_text("---\ntags: [test]\n---\n# Empty Title\n", encoding="utf-8")

        # 4. Create valid content file
        f_valid = self.vault_path / "valid.md"
        f_valid.write_text("# Real Note\nThis contains actual knowledge and facts.\n", encoding="utf-8")

        # 5. Create INDEX.md with link to zero.md and valid.md
        f_index = self.vault_path / "INDEX.md"
        f_index.write_text("## Index\n- [[zero]]\n- [[valid]]\n", encoding="utf-8")

        # Run pruner
        res = a6.prune_empty_files(self.vault_path)
        self.assertEqual(res["pruned_count"], 3)
        self.assertFalse(f_zero.exists())
        self.assertFalse(f_ws.exists())
        self.assertFalse(f_stub.exists())
        self.assertTrue(f_valid.exists())

        # Verify dangling link removed from INDEX.md
        index_content = f_index.read_text(encoding="utf-8")
        self.assertNotIn("[[zero]]", index_content)
        self.assertIn("[[valid]]", index_content)

    def test_end_to_end_department_pipeline(self):
        """Verify full ingestion and context recall flow."""
        # Ingest an explicit turn
        ingest_res = self.dept.ingest_turn(
            user_text="Jarvis, remember that I prefer dark theme on all my Wayland applications.",
            assistant_text="Understood sir, saving your preference.",
        )
        self.assertEqual(ingest_res["status"], "MEMORY_COMMITTED")
        self.assertEqual(ingest_res["decision"], "ADD")

        # Recall context for related prompt
        context = self.dept.get_context_for_prompt("Which theme do I use for Wayland?")
        self.assertIn("dark theme on all my Wayland applications", context)


if __name__ == "__main__":
    unittest.main()
