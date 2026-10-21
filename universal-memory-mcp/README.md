# Universal Memory MCP Service

This is the standalone Universal Memory service. It runs as an MCP server over
stdio and does not require JARVIS-OMA, ChatGPT, an OpenAI API key, or network
access.

## Run locally

```bash
python -m universal_memory_mcp.server \
  --database ~/.local/state/universal-memory/knowledge.db \
  --client-id local-agent \
  --read-scope user \
  --read-scope project:my-project \
  --write-scope project:my-project \
  --permission propose
```

The service keeps all data in the SQLite database path supplied with
`--database`. Agents communicate with it using MCP JSON-RPC over stdin/stdout.

The package is intentionally self-contained; JARVIS-OMA is not imported or
required at runtime.

## Layout

- `src/`: standalone service code
- `agents/claude-code/`: Claude Code connector notes
- `agents/opencode/`: OpenCode connector notes
- `integrations/obsidian/`: Obsidian publisher
- `data/`: local SQLite database and audit log
