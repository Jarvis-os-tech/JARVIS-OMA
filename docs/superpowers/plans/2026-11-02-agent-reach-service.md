# Agent-Reach System Service & Multi-Agent Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and deploy Agent-Reach as an isolated systemd user service with a Universal MCP Bridge, and configure all sibling agents (`claude`, `codex`, `hermes`, `opencode`, `gemini`) and `JARVIS OS` to query it.

**Architecture:** A standalone Python virtual environment and source tree in `~/.local/share/agent-reach` runs a lightweight async daemon under systemd (`agent-reach.service`) exposing local HTTP and Unix socket APIs. A universal stdio MCP server (`~/.local/bin/agent-reach-mcp`) proxies JSON-RPC tool calls to the daemon. All sibling agents have their MCP configuration files updated, and JARVIS OS receives an async connector and tool router.

**Tech Stack:** Python 3.10+, `uv`, FastAPI/Starlette (or Python `http.server`/`asyncio`), JSON-RPC 2.0 (MCP Protocol), Systemd user services, `yt-dlp`, `cloakbrowser`.

**Spec:** `docs/superpowers/specs/2026-11-02-agent-reach-service-design.md`

## Global Constraints

- Isolated installation under `~/.local/share/agent-reach/`; never pollute global system packages or modify existing workspace dependencies.
- Daemon must bind strictly to localhost (`127.0.0.1:8765`) and Unix socket `$XDG_RUNTIME_DIR/agent-reach/daemon.sock` with file mode `0600`.
- All operations are strictly read-only: no posting, commenting, liking, or messaging.
- Never store or solicit user passwords.
- Existing MCP servers across agent configurations (`graph-codebase-mcp`, `node_repl`, `rea`, `jarvis_orchestrator`) must be preserved without corruption.

---

### Task 1: Environment & Agent-Reach Runtime Setup

**Files:**
- Create: `~/.local/share/agent-reach/` (directory tree)
- Source: `~/.local/share/agent-reach/src`
- Virtualenv: `~/.local/share/agent-reach/venv`

**Interfaces:**
- Produces: Working executable `~/.local/share/agent-reach/venv/bin/agent-reach` able to execute `agent-reach channels`.

- [ ] **Step 1: Create isolated directories and clone or copy Agent-Reach source**

```bash
mkdir -p ~/.local/share/agent-reach/src
cp -r /home/g0pi/.gemini/antigravity/brain/b98ed06a-5530-4ed7-91d2-9a88e1b65331/scratch/Agent-Reach/* ~/.local/share/agent-reach/src/
```

- [ ] **Step 2: Initialize dedicated Python venv with uv and install dependencies**

```bash
uv venv ~/.local/share/agent-reach/venv --python 3.11
source ~/.local/share/agent-reach/venv/bin/activate
uv pip install -e ~/.local/share/agent-reach/src
uv pip install httpx uvicorn fastapi
```

- [ ] **Step 3: Verify the isolated agent-reach CLI binary works**

Run: `~/.local/share/agent-reach/venv/bin/agent-reach channels`
Expected: Output showing table of available channels (github, youtube, reddit, etc.).

---

### Task 2: Agent-Reach Daemon & Systemd User Service

**Files:**
- Create: `~/.local/share/agent-reach/src/agent_reach_daemon.py`
- Create: `~/.config/systemd/user/agent-reach.service`
- Test: `tests/test_agent_reach_service.py`

**Interfaces:**
- Produces: Running systemd service `agent-reach.service` listening on `127.0.0.1:8765` providing:
  - `GET /health`
  - `GET /channels`
  - `POST /read`
  - `POST /search`
  - `POST /transcript`

- [ ] **Step 1: Write `agent_reach_daemon.py`**

Implement the async REST/socket server wrapping Agent Reach's internal channel dispatchers (`agent_reach.runtime.dispatch` or CLI execution) with timeout handling and JSON envelopes.

- [ ] **Step 2: Create unit test for daemon endpoints**

Write `tests/test_agent_reach_service.py` asserting `/health` returns status `ok` and `/channels` lists supported platforms.

- [ ] **Step 3: Write and install systemd user unit file `agent-reach.service`**

```ini
[Unit]
Description=Agent-Reach sovereign retrieval service
After=network.target

[Service]
WorkingDirectory=%h/.local/share/agent-reach/src
ExecStart=%h/.local/share/agent-reach/venv/bin/python agent_reach_daemon.py
Restart=always
RestartSec=3
Environment=PYTHONPATH=%h/.local/share/agent-reach/src
Environment=PATH=%h/.local/share/agent-reach/venv/bin:/usr/local/bin:/usr/bin:/bin
NoNewPrivileges=true

[Install]
WantedBy=default.target
```

- [ ] **Step 4: Enable and start systemd service**

```bash
systemctl --user daemon-reload
systemctl --user enable --now agent-reach.service
systemctl --user status agent-reach.service
curl -s http://127.0.0.1:8765/health
```
Expected: Service is `active (running)` and curl returns `{"status":"ok"}`.

---

### Task 3: Universal MCP Server Implementation (`agent-reach-mcp`)

**Files:**
- Create: `~/.local/share/agent-reach/src/mcp_server.py`
- Create: `~/.local/bin/agent-reach-mcp` (executable symlink/wrapper)
- Test: `tests/test_agent_reach_mcp.py`

**Interfaces:**
- Consumes: `http://127.0.0.1:8765` daemon (with CLI fallback).
- Produces: Standard stdio JSON-RPC MCP server providing tools:
  - `reach_read`
  - `reach_search`
  - `reach_transcript`
  - `reach_status`

- [ ] **Step 1: Write MCP server implementation in Python**

Implement standard JSON-RPC 2.0 protocol over stdio handling:
- `initialize` (declaring protocolVersion `2024-11-05`, tools capability)
- `tools/list` (exposing schemas for `reach_read`, `reach_search`, `reach_transcript`, `reach_status`)
- `tools/call` (invoking daemon endpoints and returning text content)

- [ ] **Step 2: Create launcher script `~/.local/bin/agent-reach-mcp`**

```bash
#!/usr/bin/env bash
exec ~/.local/share/agent-reach/venv/bin/python ~/.local/share/agent-reach/src/mcp_server.py "$@"
```
Make executable: `chmod +x ~/.local/bin/agent-reach-mcp`.

- [ ] **Step 3: Test MCP stdio protocol handshake**

Send an `initialize` JSON-RPC request and verify valid response:
```bash
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}' | ~/.local/bin/agent-reach-mcp
```
Expected: JSON response with `result.capabilities.tools`.

---

### Task 4: Sibling Agent Fleet Configuration Updates

**Files:**
- Modify: `~/.claude.json`
- Modify: `~/.codex/config.toml`
- Modify: `~/.hermes/config.yaml`
- Modify: `~/.config/opencode/opencode.jsonc`
- Create: `~/.gemini/config/skills/agent-reach/SKILL.md`

**Interfaces:**
- Consumes: `~/.local/bin/agent-reach-mcp`
- Produces: All agents configured with `agent-reach` as an MCP server.

- [ ] **Step 1: Backup all agent configs before editing**

```bash
cp ~/.claude.json ~/.claude.json.bak-agent-reach
cp ~/.codex/config.toml ~/.codex/config.toml.bak-agent-reach
cp ~/.hermes/config.yaml ~/.hermes/config.yaml.bak-agent-reach
cp ~/.config/opencode/opencode.jsonc ~/.config/opencode/opencode.jsonc.bak-agent-reach
```

- [ ] **Step 2: Update Claude Code configuration (`~/.claude.json`)**

Add under `"mcpServers"`:
```json
"agent-reach": {
  "command": "/home/g0pi/.local/bin/agent-reach-mcp",
  "args": []
}
```

- [ ] **Step 3: Update Codex configuration (`~/.codex/config.toml`)**

Add:
```toml
[mcp_servers.agent_reach]
command = "/home/g0pi/.local/bin/agent-reach-mcp"
args = []
startup_timeout_sec = 30
```

- [ ] **Step 4: Update Hermes configuration (`~/.hermes/config.yaml`)**

Add under `mcp_servers`:
```yaml
  agent_reach:
    command: /home/g0pi/.local/bin/agent-reach-mcp
    args: []
    enabled: true
```

- [ ] **Step 5: Update OpenCode configuration (`~/.config/opencode/opencode.jsonc`)**

Add under `"mcp"` -> `"servers"`:
```json
"agent-reach": {
  "type": "local",
  "command": [
    "/home/g0pi/.local/bin/agent-reach-mcp"
  ]
}
```

- [ ] **Step 6: Install Gemini / Antigravity skill**

Create `~/.gemini/config/skills/agent-reach/SKILL.md` copying from Agent-Reach's tested skill manifest.

---

### Task 5: JARVIS OS Connector & Desktop Tool Integration

**Files:**
- Create: `connectors/agent_reach.py`
- Modify: `jarvis_control/tools.py`
- Modify: `jarvis_control/skills.py`
- Test: `tests/test_agent_reach_connector.py`

**Interfaces:**
- Produces: `connectors.agent_reach.AgentReachClient` and tools registered in `UnifiedSkills`.

- [ ] **Step 1: Write `tests/test_agent_reach_connector.py`**

Test async queries to `AgentReachClient` for `read`, `search`, and `transcript`.

- [ ] **Step 2: Implement `connectors/agent_reach.py`**

Create `AgentReachClient` connecting to `http://127.0.0.1:8765` or falling back cleanly with error handling.

- [ ] **Step 3: Wire into `jarvis_control/tools.py` & `skills.py`**

- In `_tool_read_url(url)`: if URL matches supported platforms or public page fetch returns anti-bot error, fallback to `AgentReachClient.read(url)`.
- Expose `reach_search` and `reach_transcript` tool schemas.

- [ ] **Step 4: Run unit tests**

```bash
.venv/bin/pytest tests/test_agent_reach_connector.py -v
```
Expected: PASS.

---

### Task 6: End-to-End System Verification

**Files:**
- Create: `scripts/verify_agent_reach_fleet.py`

- [ ] **Step 1: Run comprehensive verification script**

Write and execute `scripts/verify_agent_reach_fleet.py` verifying:
1. `agent-reach.service` systemd status is `active (running)`.
2. Daemon REST endpoint `http://127.0.0.1:8765/health` returns status `ok`.
3. MCP handshake on `~/.local/bin/agent-reach-mcp` returns tools.
4. Live test: `agent-reach-mcp` tool call for a GitHub repo and YouTube video information.
5. JSON configs of all sibling agents parse cleanly without syntax errors.

- [ ] **Step 2: Commit implementation changes to git**

```bash
git add connectors/agent_reach.py jarvis_control/ scripts/verify_agent_reach_fleet.py tests/
git commit -m "feat(reach): integrate Agent-Reach system service and multi-agent MCP bridge"
```
