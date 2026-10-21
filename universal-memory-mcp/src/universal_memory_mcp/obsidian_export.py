"""Publish the standalone memory ledger into an Obsidian vault."""

from __future__ import annotations

import argparse
import html
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from .knowledge import KnowledgeStore


def _safe_name(text: str) -> str:
    value = re.sub(r"[^A-Za-z0-9._ -]+", "", text).strip()[:80]
    return value or "memory"


def export(database: Path, vault: Path) -> int:
    vault = vault.expanduser().resolve(strict=True)
    if not vault.is_dir() or vault.is_symlink():
        raise ValueError("vault must be an existing non-symlink directory")
    root = vault / "Universal Memory"
    root.mkdir(mode=0o700, exist_ok=True)
    store = KnowledgeStore(database.expanduser().resolve())
    daily = defaultdict(list)
    for record in store.list(active_only=False):
        if record.get("status") != "active":
            continue
        agent = record.get("agent_id") or "shared"
        stamp = record.get("updated_at") or record.get("created_at") or 0
        day = datetime.fromtimestamp(float(stamp), timezone.utc).strftime("%Y-%m-%d")
        daily[(agent, day)].append(record)
    count = 0
    for (agent, day), records in daily.items():
        folder = root / "Agents" / ("Claude Code" if agent == "claude-code" else
                                    "OpenCode" if agent == "opencode" else _safe_name(agent))
        folder.mkdir(mode=0o700, parents=True, exist_ok=True)
        path = folder / f"{day}.md"
        kinds = sorted({record.get("kind", "memory") for record in records})
        bullets = []
        for record in records:
            text = " ".join(str(record.get("text", "")).split())
            # Keep a short extractive summary; never copy the complete record.
            brief = re.split(r"(?<=[.!?])\s+", text, maxsplit=1)[0][:180]
            bullets.append(f"- **{record.get('kind', 'memory')}**: {html.escape(brief, quote=False)}")
        content = ("---\n" f"agent: {agent}\n" f"date: {day}\n"
                   f"memory_count: {len(records)}\n" f"kinds: {', '.join(kinds)}\n" "---\n\n"
                   f"# Daily memory summary — {day}\n\n"
                   f"{len(records)} memory item(s) recorded for this agent.\n\n"
                   "## Brief summary\n\n" + "\n".join(bullets) + "\n")
        path.write_text(content, encoding="utf-8")
        path.chmod(0o600)
        count += 1
    return count


def main(argv=None):
    parser = argparse.ArgumentParser(description="Export Universal Memory to Obsidian")
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--vault", type=Path, required=True)
    args = parser.parse_args(argv)
    print(f"exported {export(args.database, args.vault)} memories")


if __name__ == "__main__":
    main()
