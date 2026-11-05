#!/usr/bin/env python3
"""JARVIS Midnight Conversation Summarizer and Sovereign Obsidian Vault Sync.

Runs daily at midnight (or on demand) to:
1. Scan sessions.db for all recorded user turns from the day.
2. Extract user identity, instructions, preferences, constraints, and facts into knowledge.db.
3. Generate structured daily executive summaries for each conversation session.
4. Synchronize all unified conversation notes and personal data into the Obsidian vault.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
import sqlite3
import sys
import time

# Ensure project root is in path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from jarvis_memory.bridge import MemoryBridge
from jarvis_memory.config import load_config
from jarvis_memory.capture import extract_memories
from jarvis_memory.scanner import InjectionScanner

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
log = logging.getLogger("midnight-sync")


def run_midnight_sync(vault_path: str | None = None, force: bool = True) -> dict:
    config_file = Path.home() / ".config/jarvis-voice/config.toml"
    cfg_wrapper = load_config(config_file if config_file.is_file() else None)
    memory_cfg = cfg_wrapper.memory
    
    # Enforce sovereign layout
    memory_cfg.obsidian_layout = "sovereign"
    if vault_path:
        memory_cfg.obsidian_vault = str(vault_path)
    elif not memory_cfg.obsidian_vault:
        memory_cfg.obsidian_vault = str(Path.home() / "Documents/JARVIS Memory")

    state_path = Path(memory_cfg.path).expanduser() if memory_cfg.path else (Path.home() / ".local/state/jarvis/memory")
    vault_dir = Path(memory_cfg.obsidian_vault).expanduser().resolve()
    vault_dir.mkdir(parents=True, exist_ok=True, mode=0o700)

    log.info("Starting midnight memory consolidation...")
    log.info("State directory: %s", state_path)
    log.info("Obsidian vault:  %s", vault_dir)

    bridge = MemoryBridge(memory_cfg)
    bridge.start()

    # 1. Backfill and extract any new memories from sessions.db into knowledge.db
    sessions_db = state_path / "sessions.db"
    extracted_count = 0
    if sessions_db.is_file():
        scanner = InjectionScanner()
        conn = sqlite3.connect(sessions_db)
        try:
            cursor = conn.execute(
                "SELECT id, role, content, channel, timestamp FROM session_messages "
                "WHERE role='user' ORDER BY timestamp ASC, id ASC"
            )
            rows = cursor.fetchall()
            log.info("Processing %d session messages for structured capture...", len(rows))
            for msg_id, role, content, channel, ts in rows:
                if not content or not scanner.scan(content).is_clean:
                    continue
                items = extract_memories(content)
                for item in items:
                    text = item["text"]
                    kind = item["kind"]
                    key = item.get("key", "")
                    confidence = item.get("confidence", 0.9)
                    quote = item.get("evidence", content)
                    if not scanner.scan(text).is_clean:
                        continue
                    dev_source = f"{channel or 'pc'}-conversation"
                    bridge.knowledge.upsert(
                        text, kind=kind, key=key, source=dev_source,
                        evidence={"role": "user", "quote": quote},
                        confidence=confidence, observed_at=ts
                    )
                    extracted_count += 1
        finally:
            conn.close()

    log.info("Extracted / updated %d structured memory entries in knowledge ledger.", extracted_count)

    # 2. Sync sovereign Obsidian vault
    result = bridge.sync_obsidian(force=force, vault_dir=str(vault_dir))
    log.info("Obsidian sync complete: status=%s, written=%s, removed=%s, conflicts=%s",
             result.get("status"), result.get("written"), result.get("removed"), len(result.get("conflicts", [])))
    
    bridge.close()
    return result


def main():
    vault_arg = None
    if len(sys.argv) > 1 and not sys.argv[1].startswith("-"):
        vault_arg = sys.argv[1]
    res = run_midnight_sync(vault_path=vault_arg, force=True)
    print("\n=== JARVIS Midnight Sync Summary ===")
    print(f"Vault:     {res.get('vault')}")
    print(f"Status:    {res.get('status')}")
    print(f"Notes:     {res.get('nodes')} total")
    print(f"Written:   {res.get('written')} updated")
    print(f"Conflicts: {len(res.get('conflicts', []))}")
    print(f"Dashboard: {res.get('start_here')}")


if __name__ == "__main__":
    main()
