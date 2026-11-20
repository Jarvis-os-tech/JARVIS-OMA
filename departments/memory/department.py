"""Memory Department Lead & Orchestrator for JARVIS OS.
Coordinates the six specialized memory agents into cohesive read, write, update,
and day-rollover compaction pipelines.
"""

from contextlib import contextmanager
from datetime import date, datetime, timedelta
import fcntl
from hashlib import sha256
from itertools import groupby
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

from jarvis_memory.paths import get_config_dir

from .config import config, MemoryConfig
from .agents.a5_day_rollover_compactor import SYNC_CURSOR, is_compacted, write_note
from .db import MemoryDatabase
from .agents import (
    ExtractorGatekeeperAgent,
    ConsolidationAgent,
    ReflectionAgent,
    RetrievalRouterAgent,
    DayRolloverCompactorAgent,
    VaultPrunerAgent,
)

class MemoryDepartment:
    """Department Lead orchestrating all six memory specialist agents."""

    def __init__(self, cfg: Optional[MemoryConfig] = None, db: Optional[MemoryDatabase] = None):
        self.cfg = cfg or config
        self.cfg.state_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.db = db or MemoryDatabase(self.cfg.db_path)

        self.a1_extractor = ExtractorGatekeeperAgent(self.cfg, self.db)
        self.a2_consolidation = ConsolidationAgent(self.cfg, self.db)
        self.a3_reflection = ReflectionAgent(self.cfg, self.db)
        self.a4_retrieval = RetrievalRouterAgent(self.cfg, self.db)
        self.a5_compactor = DayRolloverCompactorAgent(self.cfg, self.db)
        self.a6_pruner = VaultPrunerAgent(self.cfg, self.db)

    @classmethod
    def for_bridge(cls, bridge, vault_dir=None):
        vault = vault_dir or bridge.config.obsidian_vault
        if not vault:
            raise ValueError("Configure memory.obsidian_vault first")
        cfg = MemoryConfig()
        cfg.obsidian_vault_path = Path(vault).expanduser().resolve()
        key = sha256(str(cfg.obsidian_vault_path).encode()).hexdigest()[:20]
        cfg.state_dir = bridge.root / "department" / key
        cfg.state_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        cfg.db_path = cfg.state_dir / "memory_graph.db"
        return cls(cfg)

    @contextmanager
    def _vault_lock(self):
        folder = self.a5_compactor._get_conversations_folder()
        folder.mkdir(parents=True, exist_ok=True, mode=0o700)
        lock = folder / ".maintenance.lock"
        if lock.is_symlink():
            raise ValueError("Memory Department lock must not be a symlink")
        with lock.open("a") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            yield

    def ingest_turn(
        self,
        user_text: str,
        assistant_text: str = "",
        tool_events: Optional[List[Dict[str, Any]]] = None,
        session_id: str = "default_session",
    ) -> Dict[str, Any]:
        """Write Path: extract candidate fact, filter noise, and consolidate to DB/Obsidian."""
        candidate = self.a1_extractor.process_turn(
            user_text=user_text,
            assistant_text=assistant_text,
            tool_events=tool_events,
            session_id=session_id,
        )

        if not candidate:
            return {"status": "NO_FACT_EXTRACTED", "reason": "filtered_noise_or_low_importance"}

        result = self.a2_consolidation.consolidate(candidate)
        return {
            "status": "MEMORY_COMMITTED",
            "decision": result.get("decision"),
            "node_id": result.get("node_id"),
            "layer": candidate.layer,
            "category": candidate.category,
            "title": candidate.title,
        }

    def get_context_for_prompt(self, prompt: str) -> str:
        """Retrieve context from the department’s own graph."""
        return self.a4_retrieval.route_and_retrieve(prompt)

    def ensure_today_file(self) -> Path:
        """Ensure today's daily note exists in Obsidian, compacting yesterday immediately and rolling over open tasks."""
        with self._vault_lock():
            return self.a5_compactor.ensure_today_file()

    def check_daily_rollover(self) -> Dict[str, Any]:
        """Event-Driven Rollover: compact previous day and initialize today's note."""
        with self._vault_lock():
            return self.a5_compactor.check_and_rollover()

    def append_turn_to_today(
        self,
        user_text: str,
        assistant_text: str = "",
        timestamp: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Ensure today's note exists (compacting yesterday if new day), append turn, and ingest candidate facts."""
        if not user_text.strip() and not assistant_text.strip():
            return {"status": "SKIPPED_EMPTY"}
        ts = datetime.fromtimestamp(timestamp) if timestamp is not None else datetime.now()
        with self._vault_lock():
            today_file = self.a5_compactor.ensure_today_file()
            lines = [self._format_message(role, text, ts) for role, text in
                     (("user", user_text), ("assistant", assistant_text)) if text.strip()]
            write_note(today_file, today_file.read_text(encoding="utf-8") + "\n" + "\n".join(lines) + "\n")
        return {"status": "APPENDED", "daily_file": str(today_file),
                "memory_result": self.ingest_turn(user_text=user_text, assistant_text=assistant_text)}

    def get_status(self) -> Dict[str, Any]:
        """Report memory department metrics, nodes, today's note, and vault location."""
        today_file = self.a5_compactor._resolve_daily_file(date.today().isoformat())
        node_count = 0
        edge_count = 0
        with self.db.connection() as c:
            node_count = c.execute("SELECT count(*) FROM memory_nodes").fetchone()[0]
            edge_count = c.execute("SELECT count(*) FROM memory_edges").fetchone()[0]

        return {
            "status": "OPERATIONAL",
            "active_today_file": str(today_file) if today_file is not None else None,
            "vault_path": str(self.cfg.obsidian_vault_path),
            "total_nodes": node_count,
            "total_edges": edge_count,
            "zero_ram_sql_fts": True,
        }

    def compact_all_history(self) -> List[Dict[str, Any]]:
        """Compact all historical daily files into clean executive summaries."""
        with self._vault_lock():
            return self.a5_compactor.compact_all_history()

    def compact_date(self, target_date: str) -> Dict[str, Any]:
        with self._vault_lock():
            return self.a5_compactor.compact_date(target_date)

    def prune_empty_files(self, dry_run: bool = False) -> Dict[str, Any]:
        """Scan and remove empty, whitespace-only, or blank stub markdown files from the vault."""
        with self._vault_lock():
            return self.a6_pruner.prune_empty_files(self.a5_compactor._get_conversations_folder(), dry_run=dry_run)

    def run_nightly_reflection(self) -> Dict[str, Any]:
        """Learning Loop: audit failed traces and synthesize procedural rules."""
        with self._vault_lock():
            return self.a3_reflection.run_daily_reflection()

    def purge_expired(self) -> int:
        """Purge temporary memory nodes whose TTL has elapsed."""
        return self.db.purge_expired_ttl()

    def _format_message(self, role, content, timestamp, note_date=None):
        speaker = "User" if role == "user" else "Jarvis"
        text = self.a5_compactor.mask_secrets(" ".join(content.splitlines()).strip())
        if timestamp.date() != (note_date or date.today()):
            text = f"({timestamp.date().isoformat()}) {text}"
        return f"- `[{timestamp:%H:%M:%S}]` **{speaker}**: {text}"

    def sync_sessions_to_vault(self, sessions_db_path: Optional[Path] = None) -> Dict[str, Any]:
        """Publish recorded turns once, saving the cursor in the same write as the note."""
        sessions_db = (sessions_db_path or get_config_dir() / "sessions.db").resolve()
        if not sessions_db.is_file():
            return {"status": "NO_SESSIONS_DB"}
        identity = sessions_db.stat()
        source = sha256(f"{sessions_db}:{identity.st_dev}:{identity.st_ino}".encode()).hexdigest()[:20]
        with self._vault_lock():
            today = date.today()
            folder = self.a5_compactor._get_conversations_folder()
            cursors = {}
            for note in folder.glob("*.md"):
                if note.is_file() and not note.is_symlink():
                    for key, row_id in SYNC_CURSOR.findall(note.read_text(encoding="utf-8")):
                        cursors[key] = max(cursors.get(key, 0), int(row_id))

            conn = sqlite3.connect(sessions_db.as_uri() + "?mode=ro", uri=True)
            try:
                conn.execute("BEGIN")
                last_id = cursors.get(source, 0)
                had_cursor = bool(last_id)
                cutoff_file = self.cfg.state_dir / f"session-start-{source}.txt"
                if conn.execute("SELECT 1 FROM sqlite_master WHERE name = 'session_message_migration'").fetchone():
                    legacy_max = conn.execute("SELECT last_legacy_id FROM session_message_migration").fetchone()[0]
                    source = sha256(f"{source}:monotonic".encode()).hexdigest()[:20]
                    # A deleted legacy tail may leave a cursor beyond the migration high-water mark.
                    last_id = cursors.get(source, min(last_id, legacy_max))
                    had_cursor = had_cursor or bool(last_id)
                cutoff = 0.0
                if not had_cursor:
                    if not cutoff_file.exists():
                        initial_day = today - timedelta(days=1)
                        write_note(cutoff_file, str(datetime.combine(initial_day, datetime.min.time()).timestamp()))
                    cutoff = float(cutoff_file.read_text(encoding="utf-8"))
                rows = conn.execute(
                    "SELECT id, role, content, timestamp FROM session_messages "
                    "WHERE id > ? AND (? > 0 OR timestamp >= ?) ORDER BY id",
                    (last_id, int(had_cursor), cutoff),
                ).fetchall()
            finally:
                conn.close()
            synced = 0
            for day, batch in groupby(rows, key=lambda row: min(datetime.fromtimestamp(row[3]).date(), today)):
                source_note = self.a5_compactor._resolve_daily_file(day.isoformat())
                current = source_note.read_text(encoding="utf-8") if source_note else ""
                if day == today or is_compacted(current):
                    day = today
                    source_note = self.a5_compactor.ensure_today_file(today)
                    current = source_note.read_text(encoding="utf-8")
                elif source_note is None:
                    source_note = self.a5_compactor._initialize_today_file(day, [], None)
                    current = source_note.read_text(encoding="utf-8")

                lines = []
                for row_id, role, content, timestamp in batch:
                    if role not in {"user", "assistant"} or not content or not content.strip():
                        continue
                    if "[System Alert" not in content and "Temperature critical" not in content:
                        lines.append(self._format_message(role, content, datetime.fromtimestamp(timestamp), day))
                cursor = f"<!-- memory-department-session-id: {source} {row_id} -->"
                write_note(source_note, "\n".join([current.rstrip(), "", *lines, cursor, ""]))
                synced += len(lines)

            today_file = self.a5_compactor.ensure_today_file(today)
            if not rows:
                return {"status": "UP_TO_DATE", "messages_synced": 0}
            return {"status": "SYNCED", "messages_synced": synced,
                    "today_note": str(today_file), "last_message_id": rows[-1][0]}


def __getattr__(name):
    if name == "memory_dept":
        department = MemoryDepartment()
        globals()[name] = department
        return department
    raise AttributeError(name)
