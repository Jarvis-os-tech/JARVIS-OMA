"""Comprehensive test suite for the JARVIS OS Memory Department.
Tests the 5 agents, SQLite WAL schema, FTS5 BM25 search, recursive CTE graph traversal,
and event-driven day rollover compaction.
"""

from datetime import datetime, date, timedelta
from pathlib import Path
import json
import shutil
import sqlite3
import tempfile
import time
import unittest
from unittest.mock import patch

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
                "input": {"command": "workspace 9", "headers": {"Authorization": "fixture-secret"}},
                "exit_code": 1,
                "error": "Failed to connect to hyprland socket",
            }
        ]
        a1.process_turn("Switch to workspace 9", tool_events=failed_event)
        failed_traces = self.db.get_recent_failed_traces()
        self.assertGreaterEqual(len(failed_traces), 1)
        self.assertEqual(failed_traces[0]["tool_name"], "hyprctl_dispatch")
        self.assertNotIn("fixture-secret", failed_traces[0]["tool_input"])
        self.assertIn("[REDACTED_SECRET]", failed_traces[0]["tool_input"])

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
        self.assertEqual([row["id"] for row in self.db.search_fts("X11 Wayland")], [c2.id])
        a2.consolidate(c1)
        self.assertEqual([row["id"] for row in self.db.search_fts("X11 Wayland")], [c1.id])

    def test_agent2_retry_repairs_fact_projection(self):
        candidate = MemoryCandidate("retry_fact", "semantic", "preference", "Editor", "I prefer Neovim")
        with patch("departments.memory.agents.a2_consolidation_agent.write_private_text",
                   side_effect=PermissionError):
            with self.assertRaises(PermissionError):
                self.dept.a2_consolidation.consolidate(candidate)
        self.assertIsNotNone(self.db.get_node(candidate.id))
        self.assertEqual(self.dept.a2_consolidation.consolidate(candidate)["decision"], "NO-OP")
        note = self.vault_path / "Memory Department" / "Facts" / "preference.md"
        self.assertEqual(note.read_text().count(candidate.content), 1)

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
        self.assertEqual(a3.run_daily_reflection()["new_procedural_rules_count"], 0)
        self.assertEqual(len(json.loads((self.cfg.state_dir / "procedural_rules.json").read_text())), 1)

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

    def test_agent4_excludes_expired_nodes_and_related_context(self):
        self.db.upsert_node("current", "semantic", "fact", "Current detail", "Audio gateway works.")
        self.db.upsert_node("expired", "semantic", "fact", "Expired detail", "Audio gateway expired.",
                            ttl_expires_at=int(time.time()) - 1)
        self.db.add_edge("current", "relates_to", "expired")
        context = self.dept.get_context_for_prompt("Audio gateway")
        self.assertIn("Current detail", context)
        self.assertNotIn("Expired detail", context)

    def test_agent5_event_driven_day_rollover_compactor(self):
        """Verify Agent 5 detects rollover, scrubs raw logs, carries open tasks, and compacts."""
        a5 = self.dept.a5_compactor

        # Create yesterday's uncompacted raw log
        yesterday_str = (datetime.now().date() - timedelta(days=1)).strftime("%Y-%m-%d")
        episodic_dir = a5._get_conversations_folder()
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
        self.assertEqual(self.dept.compact_all_history(), [])
        self.assertEqual(yesterday_file.read_text(), compacted_yesterday)
        self.assertEqual((episodic_dir / ".raw_backups" / yesterday_file.name).read_text(),
                         raw_yesterday_content)

    def test_compact_only_accepts_past_dates_and_real_agent_notes(self):
        folder = self.dept.ensure_today_file().parent
        past = (date.today() - timedelta(days=1)).isoformat()
        outside = self.vault_path / "outside.md"
        outside.write_text("My original note")
        (folder / f"{past}.md").symlink_to(outside)
        for invalid in (str(outside.with_suffix("")), date.today().isoformat(), past):
            with self.subTest(target=invalid), self.assertRaises(ValueError):
                self.dept.compact_date(invalid)
        self.assertEqual(self.dept.compact_all_history(), [])
        self.assertEqual(outside.read_text(), "My original note")

    def test_existing_today_note_repairs_stale_rollover_marker(self):
        today = date.today()
        self.dept.a5_compactor._initialize_today_file(today, [], None)
        marker = self.cfg.state_dir / "last_active_date.txt"
        marker.write_text((today - timedelta(days=1)).isoformat())

        first = self.dept.check_daily_rollover()
        self.assertTrue(first["rollover_occurred"])
        self.assertEqual(marker.read_text(), today.isoformat())
        self.assertFalse(self.dept.check_daily_rollover()["rollover_occurred"])

    def test_failed_sync_can_retry_without_duplicate_notes(self):
        sessions = self.temp_dir / "sessions.db"
        with sqlite3.connect(sessions) as conn:
            conn.execute("CREATE TABLE session_messages (id INTEGER PRIMARY KEY, role TEXT, content TEXT, timestamp REAL)")
            conn.execute("INSERT INTO session_messages VALUES (1, 'user', ?, ?)",
                         ("Schedule the test review", (datetime.now() - timedelta(days=1)).timestamp()))
            conn.execute("INSERT INTO session_messages VALUES (2, 'assistant', ?, ?)",
                         ("The review is pending", datetime.now().timestamp()))
        from departments.memory.agents.base_memory_agent import write_private_text

        def fail_note_only(path, content):
            if path.suffix == ".md":
                raise PermissionError(path)
            write_private_text(path, content)

        with patch("departments.memory.department.write_note", side_effect=fail_note_only):
            with self.assertRaises(PermissionError):
                self.dept.sync_sessions_to_vault(sessions)
        self.assertEqual(len(list(self.cfg.state_dir.glob("session-start-*.txt"))), 1)

        self.assertEqual(self.dept.sync_sessions_to_vault(sessions)["messages_synced"], 2)
        files = self.dept.a5_compactor._get_conversations_folder()
        yesterday = files / f"{date.today() - timedelta(days=1)}.md"
        self.assertIn("Schedule the test review", yesterday.read_text())
        self.assertIn("episodic_compacted_summary", yesterday.read_text())
        today = files / f"{date.today()}.md"
        self.assertEqual(self.dept.sync_sessions_to_vault(sessions)["status"], "UP_TO_DATE")
        self.assertEqual(today.read_text().count("The review is pending"), 1)

    def test_sync_recovers_when_legacy_cursor_exceeds_migration_high_water(self):
        from jarvis_memory.session import SessionStore

        sessions = self.temp_dir / "sessions.db"
        with sqlite3.connect(sessions) as conn:
            conn.execute("""CREATE TABLE session_messages (
                id INTEGER PRIMARY KEY, session_id TEXT NOT NULL, role TEXT NOT NULL,
                content TEXT NOT NULL, channel TEXT, timestamp REAL, metadata TEXT
            )""")
            for row in [(1, "Keep this message"), (8, "Delete the last legacy message")]:
                conn.execute("INSERT INTO session_messages VALUES (?, 'legacy', 'user', ?, '', ?, '{}')",
                             (*row, time.time()))
        self.assertEqual(self.dept.sync_sessions_to_vault(sessions)["last_message_id"], 8)
        with sqlite3.connect(sessions) as conn:
            conn.execute("DELETE FROM session_messages WHERE id = 8")

        store = SessionStore(sessions)
        try:
            session_id = store.get_or_create("local-user").session_id
            store.save_message(session_id, "user", "New message after migration")
            first = self.dept.sync_sessions_to_vault(sessions)
            self.assertEqual(first["messages_synced"], 1)
            with sqlite3.connect(sessions) as conn:
                conn.execute("DELETE FROM session_messages WHERE id = ?", (first["last_message_id"],))
            store.save_message(session_id, "assistant", "New message after deletion")
            second = self.dept.sync_sessions_to_vault(sessions)
            self.assertGreater(second["last_message_id"], first["last_message_id"])
            self.assertEqual(second["messages_synced"], 1)
            self.assertEqual(self.dept.sync_sessions_to_vault(sessions)["status"], "UP_TO_DATE")
            content = Path(first["today_note"]).read_text()
            self.assertEqual(content.count("Keep this message"), 1)
            self.assertEqual(content.count("New message after migration"), 1)
            self.assertIn("New message after deletion", content)
        finally:
            store.close()

    def test_bridge_uses_selected_vault_and_respects_recording_setting(self):
        from jarvis_memory.bridge import MemoryBridge
        from jarvis_memory.config import MemoryConfig as BridgeConfig

        configured = self.vault_path / "default"
        selected = self.vault_path / "selected"
        shared = selected / "Conversations"
        shared.mkdir(parents=True)
        untouched = shared / "empty.md"
        untouched.touch()
        bridge = MemoryBridge(BridgeConfig(path=str(self.temp_dir / "bridge"),
                                           obsidian_vault=str(configured), record_sessions=False))
        try:
            self.assertEqual(bridge.memory_department("sync_sessions_to_vault", vault_dir=selected)["status"],
                             "RECORDING_DISABLED")
            self.assertFalse((selected / "Memory Department").exists())
            bridge.config.record_sessions = True
            bridge.start()
            bridge.memory_department("sync_sessions_to_vault", vault_dir=selected)
            bridge.memory_department("prune_empty_files", vault_dir=selected)
            self.assertTrue((selected / "Memory Department" / "Conversations").is_dir())
            self.assertTrue(untouched.exists())
            self.assertFalse(configured.exists())
        finally:
            bridge.close()

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
        f_index.write_text("## Index\n- [[zero]]\n- [[valid]]\nSee [[zero]] and [[valid]] for context.\n",
                           encoding="utf-8")
        checkpoint = self.vault_path / "checkpoint.md"
        checkpoint.write_text("<!-- memory-department-session-id: 1234567890abcdef1234 42 -->\n")

        # Run pruner
        res = a6.prune_empty_files(self.vault_path)
        self.assertEqual(res["pruned_count"], 3)
        self.assertFalse(f_zero.exists())
        self.assertFalse(f_ws.exists())
        self.assertFalse(f_stub.exists())
        self.assertTrue(f_valid.exists())
        self.assertTrue(checkpoint.exists())

        # Verify dangling link removed from INDEX.md
        index_content = f_index.read_text(encoding="utf-8")
        self.assertNotIn("- [[zero]]", index_content)
        self.assertIn("[[valid]]", index_content)
        self.assertIn("See [[zero]] and [[valid]] for context.", index_content)

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
