# Universal memory service

JARVIS universal memory lets local AI clients share one evidence-backed SQLite
ledger without giving those clients direct database access. The transport is a
local stdio MCP server. It does not open a network port.

## Current scope

Implemented:

- Backward-compatible metadata migration for the existing knowledge ledger.
- Scoped search, read, proposal, commit, correction, history and deletion.
- Explicit agent identity and per-client read/write permissions.
- Content-free mutation audit log.
- Read-only sibling-session import with provenance, checkpoints and dry runs.

Not implemented:

- A public or hosted ChatGPT connector.
- An HTTPS gateway or tunnel.
- Automatic promotion of agent proposals into trusted user facts.

Do not expose the stdio server through an unauthenticated tunnel. Remote access
requires a separately reviewed authenticated gateway with TLS, revocable
credentials and sensitivity filtering.

## Local server command

Run the server from the repository root with an absolute database path. Replace
the example state path with the configured JARVIS memory path on this machine.

```bash
PYTHONPATH=/home/g0pi/Projects/JARVIS-OMA/memory/codes-dev \
  /home/g0pi/Projects/JARVIS-OMA/.venv/bin/python \
  -m jarvis_memory.mcp_server \
  --database /absolute/path/to/jarvis-memory/knowledge.db \
  --client-id codex \
  --read-scope user \
  --read-scope project:jarvis-oma \
  --write-scope project:jarvis-oma \
  --permission propose
```

Give ordinary coding agents `propose` permission first. Reserve `commit`,
`correct` and `forget` for an explicitly trusted reviewer client. Every agent
process must use the same absolute database path or it will create a separate
memory ledger.

For a Claude-compatible or Codex-compatible MCP client, configure a stdio
server with:

- Command: `/home/g0pi/Projects/JARVIS-OMA/.venv/bin/python`
- Arguments: `-m`, `jarvis_memory.mcp_server`, followed by the arguments above.
- Environment: `PYTHONPATH=/home/g0pi/Projects/JARVIS-OMA/memory/codes-dev`

Use a different `--client-id` and permission set for each client. Do not give
clients wildcard scope unless the client always supplies explicit scopes.

## Historical session import

Importers accept only caller-supplied paths. They do not search the home
directory and never modify source stores. Start with `dry_run=True`, inspect the
counts, then run the same explicit `SessionSource` list without dry-run. Imported
messages remain `agent`-authority proposals until reviewed and committed.

Supported sources are Claude, Codex, Gemini, OpenCode, Hermes and OMP exports in
Markdown, JSONL or the supported read-only Hermes SQLite layout. Secret-like and
prompt-injection content is quarantined.

## Backup and restore

Stop writers or use SQLite's backup API before copying `knowledge.db`. Back up
the database, importer checkpoint file and MCP audit log together. Never copy a
live SQLite database while ignoring its WAL state.

Restore into a private directory, set database permissions to owner-only, and
run the memory tests before reconnecting clients:

```bash
.venv/bin/pytest tests/test_memory -q
python3 scripts/verify_voice_lock.py
```

The audit log contains identifiers and operation metadata, not memory content.
Treat both it and the database as private user data.
