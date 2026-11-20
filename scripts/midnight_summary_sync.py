#!/usr/bin/env python3
"""JARVIS Midnight Conversation Summarizer and Sovereign Obsidian Vault Sync.

Runs daily at midnight (or on demand) to sync recorded turns, compact daily
agent notes, prune empty agent notes, and publish the configured memory vault.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
import sqlite3
import sys

# Ensure project root is in path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from jarvis_memory.bridge import MemoryBridge
from jarvis_memory.config import load_config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
log = logging.getLogger("midnight-sync")


def run_midnight_sync(vault_path: str | None = None, force: bool = True) -> dict:
    config_home = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    config_file = config_home / "jarvis-voice" / "config.toml"
    cfg_wrapper = load_config(config_file if config_file.is_file() else None)
    memory_cfg = cfg_wrapper.memory
    
    # Enforce sovereign layout
    memory_cfg.obsidian_layout = "sovereign"
    if vault_path:
        memory_cfg.obsidian_vault = str(vault_path)
    elif not memory_cfg.obsidian_vault:
        memory_cfg.obsidian_vault = str(Path.home() / "Documents/JARVIS Memory")

    vault_dir = Path(memory_cfg.obsidian_vault).expanduser().resolve()
    vault_dir.mkdir(parents=True, exist_ok=True, mode=0o700)

    log.info("Starting midnight memory consolidation...")
    log.info("Obsidian vault:  %s", vault_dir)

    bridge = MemoryBridge(memory_cfg)
    try:
        bridge.start()
        dept_prune_res = {}
        try:
            dept_sync_res = bridge.memory_department("sync_sessions_to_vault", vault_dir=vault_dir)
            dept_prune_res = bridge.memory_department("prune_empty_files", vault_dir=vault_dir)
        except (OSError, ValueError, sqlite3.Error, RuntimeError) as exc:
            log.exception("Memory Department maintenance failed")
            dept_sync_res = {"status": "ERROR", "error": type(exc).__name__}

        result = bridge.sync_obsidian(force=force, vault_dir=str(vault_dir))
        result["memory_department"] = {"sync": dept_sync_res, "prune": dept_prune_res}
        log.info("Obsidian sync complete: status=%s, written=%s, conflicts=%s",
                 result.get("status"), result.get("written"), len(result.get("conflicts", [])))
    finally:
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
    department = res["memory_department"]
    print(f"Agent sync: {department['sync']['status']}")
    if department["sync"]["status"] == "ERROR" or department["prune"].get("status") == "ERROR":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
