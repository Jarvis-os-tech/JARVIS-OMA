# Obsidian connection

The Obsidian integration is a one-way, safe publisher: active memories are
grouped into one dated Markdown summary per agent per day in a caller-selected
vault. It does not copy raw sessions or full record text. It never scans
arbitrary folders, executes notes, or overwrites notes that were edited manually.

Use the exporter from the service root:

```bash
PYTHONPATH=src python -m universal_memory_mcp.obsidian_export \
  --database data/local-memory.db \
  --vault /absolute/path/to/your/ObsidianVault
```

The generated notes are placed under `Universal Memory/` in the vault. Agent
memories are grouped into `Agents/Claude Code/` and `Agents/OpenCode/`.
