"""Memory Department Lead & Orchestrator for JARVIS OS.
Coordinates the 5 specialized memory agents into cohesive read, write, update,
and day-rollover compaction pipelines.
"""

from dataclasses import dataclass
from datetime import datetime
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config import config, MemoryConfig
from .db import MemoryDatabase
from .agents import (
    ExtractorGatekeeperAgent,
    ConsolidationAgent,
    ReflectionAgent,
    RetrievalRouterAgent,
    DayRolloverCompactorAgent,
    VaultPrunerAgent,
)

logger = logging.getLogger("departments.memory.department")


class MemoryDepartment:
    """Department Lead orchestrating all 5 memory specialist agents."""

    def __init__(self, cfg: Optional[MemoryConfig] = None, db: Optional[MemoryDatabase] = None):
        self.cfg = cfg or config
        self.db = db or MemoryDatabase(self.cfg.db_path)

        # Instantiate all 5 agents
        self.a1_extractor = ExtractorGatekeeperAgent(self.cfg, self.db)
        self.a2_consolidation = ConsolidationAgent(self.cfg, self.db)
        self.a3_reflection = ReflectionAgent(self.cfg, self.db)
        self.a4_retrieval = RetrievalRouterAgent(self.cfg, self.db)
        self.a5_compactor = DayRolloverCompactorAgent(self.cfg, self.db)
        self.a6_pruner = VaultPrunerAgent(self.cfg, self.db)

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
        """Read Path: fetch top context in <25ms for prompt injection into Gemini Live."""
        return self.a4_retrieval.route_and_retrieve(prompt)

    def check_daily_rollover(self) -> Dict[str, Any]:
        """Event-Driven Rollover: compact previous day and initialize today's note."""
        return self.a5_compactor.check_and_rollover()

    def compact_all_history(self) -> List[Dict[str, Any]]:
        """Compact all historical daily files into clean executive summaries."""
        return self.a5_compactor.compact_all_history()

    def prune_empty_files(self, dry_run: bool = False) -> Dict[str, Any]:
        """Scan and remove empty, whitespace-only, or blank stub markdown files from the vault."""
        return self.a6_pruner.prune_empty_files(dry_run=dry_run)

    def run_nightly_reflection(self) -> Dict[str, Any]:
        """Learning Loop: audit failed traces and synthesize procedural rules."""
        return self.a3_reflection.run_daily_reflection()

    def purge_expired(self) -> int:
        """Purge temporary memory nodes whose TTL has elapsed."""
        return self.db.purge_expired_ttl()


# Global default department instance
memory_dept = MemoryDepartment()
