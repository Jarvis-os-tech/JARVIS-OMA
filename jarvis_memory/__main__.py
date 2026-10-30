"""CLI entrypoint for jarvis-memory (python -m jarvis_memory)."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .bridge import MemoryBridge
from .config import Config, load_config
from .paths import DEFAULT_CONFIG_DIR


def cmd_stats(bridge: MemoryBridge, args: argparse.Namespace) -> int:
    status = bridge.status()
    if args.json:
        print(json.dumps(status, indent=2))
    else:
        sm = status.get('structured_memory', {})
        print("=== JARVIS OS Sovereign Memory Status ===")
        print(f"Directory:           {status.get('path', 'N/A')}")
        print(f"Total Facts:         {status.get('facts', 0)}")
        print(f"Structured Active:   {sm.get('active', 0)}")
        print(f"Structured Total:    {sm.get('total', 0)}")
        print(f"Retrieval Engine:    {status.get('retrieval_backend', 'N/A')}")
        print(f"Documents Backend:   {status.get('documents_backend', 'N/A')}")
        print(f"Semantic Retrieval:  {status.get('semantic_status', 'disabled')}")
        print(f"Obsidian Vault:      {status.get('obsidian_vault') or 'Not configured'}")
    return 0


def cmd_search(bridge: MemoryBridge, args: argparse.Namespace) -> int:
    query = " ".join(args.query)
    results = bridge.recall(query=query, limit=args.limit)
    if args.json:
        print(json.dumps(results, indent=2))
        return 0

    facts = results.get("facts", [])
    docs = results.get("documents", [])
    memories = results.get("memories", [])

    print(f"Found {len(facts)} facts, {len(docs)} documents, {len(memories)} structured memories for '{query}':\n")
    if facts:
        print("--- Facts ---")
        for f in facts:
            score = f.get("score", "")
            sc_str = f" [score: {score:.3f}]" if isinstance(score, (int, float)) else ""
            print(f"• {f.get('text', '')}{sc_str}")
    if memories:
        print("\n--- Structured Memories ---")
        for m in memories:
            print(f"• [{m.get('kind', 'memory').upper()}] {m.get('text', '')}")
    if docs:
        print("\n--- Documents ---")
        for d in docs:
            print(f"• {d.get('path', '')}: {d.get('snippet', '')[:100]}...")
    return 0


def cmd_store(bridge: MemoryBridge, args: argparse.Namespace) -> int:
    text = " ".join(args.text)
    res = bridge.remember(text=text)
    if args.json:
        print(json.dumps(res, indent=2))
    else:
        status = res.get("status", "saved")
        if res.get("quarantined"):
            print(f"Warning: memory input was quarantined (untrusted/injection detected).")
        else:
            print(f"Memory recorded [{status}]: {text}")
    return 0


def cmd_sync(bridge: MemoryBridge, args: argparse.Namespace) -> int:
    vault = args.vault or bridge.config.obsidian_vault
    if not vault:
        print("Error: No Obsidian vault configured. Specify --vault <path> or set in config.")
        return 1
    res = bridge.sync_obsidian(vault_dir=vault)
    if args.json:
        print(json.dumps(res, indent=2))
    else:
        print(f"Obsidian sync complete: {res.get('status', 'synced')}")
    return 0


def cmd_mcp(bridge: MemoryBridge, args: argparse.Namespace) -> int:
    from .mcp_server import main as run_mcp
    return run_mcp()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="jarvis-memory",
        description="JARVIS OS Sovereign Memory Management CLI",
    )
    parser.add_argument("--config", "-c", type=str, help="Path to config file")
    parser.add_argument("--json", action="store_true", help="Format output as JSON")

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # stats
    stats_p = subparsers.add_parser("stats", help="Show memory storage and statistics")
    stats_p.set_defaults(func=cmd_stats)

    # status alias
    status_p = subparsers.add_parser("status", help="Alias for stats")
    status_p.set_defaults(func=cmd_stats)

    # search
    search_p = subparsers.add_parser("search", help="Search memory using hybrid retrieval")
    search_p.add_argument("query", nargs="+", help="Query string")
    search_p.add_argument("--limit", "-n", type=int, default=10, help="Max results to return")
    search_p.set_defaults(func=cmd_search)

    # store
    store_p = subparsers.add_parser("store", help="Store a fact in memory")
    store_p.add_argument("text", nargs="+", help="Fact text to store")
    store_p.set_defaults(func=cmd_store)

    # sync
    sync_p = subparsers.add_parser("sync", help="Sync memory notes with Obsidian vault")
    sync_p.add_argument("--vault", type=str, help="Path to Obsidian vault")
    sync_p.set_defaults(func=cmd_sync)

    # mcp
    mcp_p = subparsers.add_parser("mcp", help="Run Model Context Protocol stdio server")
    mcp_p.set_defaults(func=cmd_mcp)

    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 0

    cfg = load_config(args.config)
    bridge = MemoryBridge(cfg.memory)

    try:
        bridge.start()
        return args.func(bridge, args)
    finally:
        bridge.close()


if __name__ == "__main__":
    sys.exit(main())
