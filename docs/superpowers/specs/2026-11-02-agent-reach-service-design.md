# Agent-Reach Standalone System Service & Multi-Agent Integration Design

**Date:** 2026-11-02  
**Status:** Approved  
**Author:** Antigravity (Pair Programming with User)

---

## 1. Overview & Problem Statement

AI coding agents and personal voice assistants (Claude Code, Codex, Hermes, OpenCode, Gemini/Antigravity, and JARVIS OS) excel at reasoning and local execution, but frequently hit brick walls when querying the live internet:
1. **Protected & Dynamic Platforms:** Reddit, Twitter/X, LinkedIn, Xiaohongshu, Bilibili, and Xueqiu require session cookies, JavaScript execution, or anti-bot challenge solving.
2. **Multimedia & Audio Content:** Technical YouTube talks, conference presentations, and podcasts cannot be read via standard HTML scrapers without subtitle/transcript extraction pipelines.
3. **Redundant & Costly Overkill:** Currently, JARVIS OS falls back to `gpt-6-astra` computer-use (taking desktop screenshots and clicking coordinates), which has high latency (15–40s) and heavy token consumption.
4. **Agent Fragmentation:** Each sibling agent currently manages web browsing independently, leading to duplicate scraping, uncoordinated rate-limiting, and inconsistent tools.

This design introduces **Agent-Reach** as an independent, sovereign system-level service on the host machine, fronted by a **Universal Model Context Protocol (MCP) Bridge** and plugged directly into all sibling agents and the JARVIS OS core.

---

## 2. Architecture & Components

```
+---------------------------------------------------------------------------------------+
|                                    Sibling Agents                                     |
|  [Claude Code]   [Codex]   [Hermes]   [OpenCode]   [Gemini/Antigravity]   [JARVIS OS] |
|        |            |         |           |                 |                  |      |
|        +------------+---------+-----------+-----------------+                  |      |
|                               |                                                |      |
|                     (Stdio MCP JSON-RPC)                             (Async Client)   |
|                               v                                                v      |
|               +-------------------------------+                                |      |
|               |  ~/.local/bin/agent-reach-mcp  |                                |      |
|               |    (Universal MCP Bridge)     |                                |      |
|               +---------------+---------------+                                |      |
|                               |                                                |      |
|                    (Unix Domain Socket / HTTP)                                 |      |
+-------------------------------|------------------------------------------------|------+
                                v                                                v
+---------------------------------------------------------------------------------------+
|                       agent-reach.service (Systemd User Service)                      |
|                                                                                       |
|   +-------------------------------------------------------------------------------+   |
|   |                       Agent Reach Daemon (FastAPI / HTTP)                     |   |
|   |         Listens on 127.0.0.1:8765 & $XDG_RUNTIME_DIR/agent-reach.sock         |   |
|   +---------------------------------------+---------------------------------------+   |
|                                           |                                           |
|       +-----------------------------------+-----------------------------------+       |
|       |                                   |                                   |       |
|       v                                   v                                   v       |
|  [Tier 1: Public Web]           [Tier 2: Direct Tool/CLI]         [Tier 3: Browser Pool]  |
|  - Jina Reader                  - yt-dlp subtitles                - CloakBrowser      |
|  - Exa MCP                      - gh CLI fallback                 - OpenCLI Chrome    |
|                                 - Whisper transcription           - Session / Cookie  |
+---------------------------------------------------------------------------------------+
```

### 2.1 The Standalone Service: `agent-reach.service`

* **Installation Path:** `~/.local/share/agent-reach/`
  * Repository: Cloned cleanly into `~/.local/share/agent-reach/src`
  * Environment: Isolated virtual environment at `~/.local/share/agent-reach/venv` using `uv`
* **Daemon Script:** `agent_reach_daemon.py`
  * Exposes an async HTTP API bound strictly to `127.0.0.1:8765` and Unix domain socket `$XDG_RUNTIME_DIR/agent-reach/daemon.sock` (permissions `0600`).
  * Endpoints:
    * `GET /health` -> `{"status": "ok", "version": "...", "channels_ready": [...]}`
    * `GET /channels` -> Detailed capabilities and status of all 15 platforms.
    * `POST /read` -> Body `{"url": "...", "backend": "..."}` -> Returns structured items.
    * `POST /search` -> Body `{"channel": "...", "query": "...", "limit": 5}` -> Returns structured items.
    * `POST /transcript` -> Body `{"url": "..."}` -> Extracts subtitles or Whisper audio transcription.
  * Concurrency & Rate Limiting: Centralized queue ensures max 4 concurrent browser sessions globally and 2 per platform, avoiding IP blocks.
* **Systemd Unit File:** `~/.config/systemd/user/agent-reach.service`
  * Managed via `systemctl --user {start|stop|restart|status} agent-reach.service`.
  * Configured with `Restart=always`, `RestartSec=3`, `NoNewPrivileges=true`, and proper XDG environment variables.

### 2.2 The Universal MCP Bridge: `agent-reach-mcp`

* **Location:** `~/.local/bin/agent-reach-mcp` (added to user PATH).
* **Protocol:** Standard Model Context Protocol (MCP) JSON-RPC 2.0 over `stdio`.
* **Exposed Tools:**
  1. `reach_read(url: str, backend?: str)`: Read content, discussions, or articles from any URL across all supported platforms.
  2. `reach_search(channel: str, query: str, limit?: int)`: Search platforms (e.g. `reddit`, `youtube`, `github`, `bilibili`, `v2ex`, `xueqiu`).
  3. `reach_transcript(url: str)`: Extract video subtitles or audio transcripts.
  4. `reach_status()`: Discover supported channels and diagnostic status.
* **Resiliency:** Connects via HTTP/socket to `agent-reach.service`; if the daemon is momentarily restarting, it falls back to direct execution of `agent-reach` CLI commands inside the isolated virtual environment.

---

## 3. Multi-Agent Integration Matrix

Each agent on the system will be configured to discover and use the MCP server:

| Agent | Configuration Target | Integration Method |
| :--- | :--- | :--- |
| **Claude Code** | `~/.claude.json` | Register `agent-reach` under `mcpServers` with command `/home/g0pi/.local/bin/agent-reach-mcp`. |
| **Codex** | `~/.codex/config.toml` | Add `[mcp_servers.agent_reach]` section pointing to `/home/g0pi/.local/bin/agent-reach-mcp`. |
| **Hermes** | `~/.hermes/config.yaml` | Add `agent_reach:` under `mcp_servers` with `command: /home/g0pi/.local/bin/agent-reach-mcp`. |
| **OpenCode** | `~/.config/opencode/opencode.jsonc` | Add `agent-reach` under `mcp.servers`. |
| **Antigravity / Gemini** | `~/.gemini/config/skills/agent-reach/` | Link official `SKILL.md` and declare MCP tool availability. |
| **JARVIS OS** | `connectors/agent_reach.py` & `jarvis_control/tools.py` | Add native async connector and integrate into `UnifiedSkills` for Gemini Live voice. |

---

## 4. JARVIS OS Native Integration

1. **New Connector ([`connectors/agent_reach.py`](file:///home/g0pi/JARVIS%20OS/connectors/agent_reach.py)):**
   * Async client communicating with `http://127.0.0.1:8765` or Unix socket.
   * Standard error translation into JARVIS error types.
2. **Desktop Actuator Tool Enhancement ([`jarvis_control/tools.py`](file:///home/g0pi/JARVIS%20OS/jarvis_control/tools.py)):**
   * Enhance `_tool_read_url(url)`: If standard `bounded_page_text` fails on anti-bot/Cloudflare or the domain matches an Agent Reach channel (Reddit, YouTube, Twitter/X, GitHub), delegate transparently to `agent-reach`.
   * Add explicit tools: `reach_search` and `reach_transcript`.
3. **Voice Registration ([`jarvis_control/skills.py`](file:///home/g0pi/JARVIS%20OS/jarvis_control/skills.py)):**
   * Register tools with Gemini Live tool definitions so the user can speak commands naturally.

---

## 5. Security & Isolation

* **Isolated Dependencies:** All Python dependencies (`uv`, `cloakbrowser`, `yt-dlp`, `opencli`) reside in `~/.local/share/agent-reach/` and `~/.agent-reach/`, avoiding conflicts with system or JARVIS OS packages.
* **No Secret Storage:** Passwords are never collected or stored. Authentication uses cookies extracted from the user's browser or interactive login windows.
* **Read-Only Verification:** All operations strictly search and read; write methods are blocked at both the daemon and MCP levels.
* **Network Binding:** Daemon binds only to `127.0.0.1` and a protected Unix socket with permissions `0600`.

---

## 6. Verification & Acceptance Criteria

1. **Daemon Service Verification:**
   * `systemctl --user status agent-reach.service` is active and running.
   * `curl http://127.0.0.1:8765/health` returns `{"status": "ok"}`.
2. **MCP Bridge Verification:**
   * Executing `agent-reach-mcp` with an MCP `initialize` JSON-RPC request returns valid protocol capabilities.
   * Tool calls for `reach_read` and `reach_search` execute and return structured items.
3. **Agent Integration Verification:**
   * Claude Code configuration contains `agent-reach` without breaking existing MCPs (`graph-codebase-mcp`).
   * Codex configuration contains `agent_reach` without breaking existing `node_repl` or `rea`.
   * Hermes configuration parses cleanly and detects `agent_reach`.
   * OpenCode configuration parses valid JSONC.
4. **JARVIS OS Voice / Control Verification:**
   * Unit tests in `tests/test_agent_reach_connector.py` pass.
   * `read_url` falls back to Agent Reach when given a dynamic/social media link.
