#!/usr/bin/env python3
"""End-to-end Fleet Verification Script for Agent Reach.

Checks:
1. Systemd user service `agent-reach.service` status.
2. Daemon REST API endpoints (`/health`, `/channels`).
3. Universal MCP bridge (`agent-reach-mcp`) handshake and tool calls.
4. Sibling agent configuration files (Claude, Codex, Hermes, OpenCode, Gemini).
5. JARVIS OS `read_url` and `reach_search` tool execution.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
import urllib.request

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

GREEN = "\033[92m"
RED = "\033[91m"
RESET = "\033[0m"

def ok(msg: str):
    print(f"[{GREEN}PASS{RESET}] {msg}")

def fail(msg: str):
    print(f"[{RED}FAIL{RESET}] {msg}")
    sys.exit(1)

def check_systemd_service():
    res = subprocess.run(["systemctl", "--user", "is-active", "agent-reach.service"], capture_output=True, text=True)
    if res.stdout.strip() == "active":
        ok("Systemd service agent-reach.service is ACTIVE")
    else:
        fail(f"Systemd service is {res.stdout.strip()}")

def check_daemon_rest():
    try:
        with urllib.request.urlopen("http://127.0.0.1:8765/health", timeout=3) as resp:
            data = json.loads(resp.read().decode())
            if data.get("status") == "ok":
                ok(f"Daemon REST /health returned OK (PID {data.get('pid')})")
            else:
                fail(f"Daemon health returned unexpected: {data}")
    except Exception as e:
        fail(f"Failed to connect to daemon REST endpoint: {e}")

def check_mcp_bridge():
    mcp_bin = Path.home() / ".local/bin/agent-reach-mcp"
    if not mcp_bin.is_file() or not os.access(mcp_bin, os.X_OK):
        fail(f"MCP binary {mcp_bin} missing or not executable")
    
    # 1. Initialize
    p = subprocess.Popen([str(mcp_bin)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    req = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "fleet_verifier", "version": "1.0"}}}
    stdout, _ = p.communicate(input=json.dumps(req) + "\n", timeout=5)
    resp = json.loads(stdout.strip())
    if resp.get("result", {}).get("serverInfo", {}).get("name") == "agent-reach":
        ok("MCP initialize handshake successful")
    else:
        fail(f"MCP initialize response invalid: {resp}")

    # 2. Tools list
    p = subprocess.Popen([str(mcp_bin)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    req = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
    stdout, _ = p.communicate(input=json.dumps(req) + "\n", timeout=5)
    resp = json.loads(stdout.strip())
    tools = [t["name"] for t in resp.get("result", {}).get("tools", [])]
    if "reach_read" in tools and "reach_search" in tools:
        ok(f"MCP tools/list contains expected tools: {tools}")
    else:
        fail(f"MCP tools list missing tools: {tools}")

def check_agent_configs():
    # 1. Claude Code
    claude_json = Path.home() / ".claude.json"
    with open(claude_json) as f:
        cdata = json.load(f)
        if "agent-reach" in cdata.get("mcpServers", {}):
            ok("Claude Code (~/.claude.json) configured with agent-reach")
        else:
            fail("Claude Code missing agent-reach")

    # 2. Codex
    codex_toml = Path.home() / ".codex/config.toml"
    import tomllib
    with open(codex_toml, "rb") as f:
        xdata = tomllib.load(f)
        if "agent_reach" in xdata.get("mcp_servers", {}):
            ok("Codex (~/.codex/config.toml) configured with agent_reach")
        else:
            fail("Codex missing agent_reach")

    # 3. Hermes
    hermes_yaml = Path.home() / ".hermes/config.yaml"
    try:
        import yaml
        with open(hermes_yaml) as f:
            hdata = yaml.safe_load(f)
            if "agent_reach" in hdata.get("mcp_servers", {}):
                ok("Hermes (~/.hermes/config.yaml) configured with agent_reach")
            else:
                fail("Hermes missing agent_reach")
    except ImportError:
        content = hermes_yaml.read_text()
        if "agent_reach:" in content and "agent-reach-mcp" in content:
            ok("Hermes (~/.hermes/config.yaml) configured with agent_reach")
        else:
            fail("Hermes missing agent_reach")

    # 4. OpenCode
    opencode_jsonc = Path.home() / ".config/opencode/opencode.jsonc"
    with open(opencode_jsonc) as f:
        odata = json.load(f)
        if "agent-reach" in odata.get("mcp", {}).get("servers", {}):
            ok("OpenCode (~/.config/opencode/opencode.jsonc) configured with agent-reach")
        else:
            fail("OpenCode missing agent-reach")

    # 5. Gemini / Antigravity skill & MCP config
    gemini_skill = Path.home() / ".gemini/config/skills/agent-reach/SKILL.md"
    if gemini_skill.is_file():
        ok("Gemini/Antigravity skill (~/.gemini/config/skills/agent-reach/) installed")
    else:
        fail("Gemini skill missing")

    antigravity_mcp = Path.home() / ".config/Antigravity/mcp.json"
    if antigravity_mcp.is_file():
        with open(antigravity_mcp) as f:
            adata = json.load(f)
            if "agent-reach" in adata.get("mcpServers", {}):
                ok("Antigravity (~/.config/Antigravity/mcp.json) configured with agent-reach")
            else:
                fail("Antigravity missing agent-reach")

def check_jarvis_tools():
    import asyncio
    from jarvis_control.tools import Executor, Config
    e = Executor(Config())
    res = e.call("reach_search", {"channel": "github", "query": "agent-reach", "limit": 1})
    if res.ok and "Panniantong" in res.output:
        ok("JARVIS OS jarvis_control Executor.call reach_search verified")
    else:
        fail(f"JARVIS OS reach_search failed: {res.output}")

    res_stat = e.call("reach_status", {})
    if res_stat.ok and "ok" in res_stat.output:
        ok("JARVIS OS jarvis_control Executor.call reach_status verified")
    else:
        fail(f"JARVIS OS reach_status failed: {res_stat.output}")

    from skills.skills import DesktopSkills
    d = DesktopSkills()
    reach_skills = [k for k in d._skills.keys() if 'reach' in k]
    expected_reach = {'reach_search', 'reach_read', 'reach_transcript', 'reach_status'}
    if expected_reach.issubset(set(reach_skills)):
        ok(f"JARVIS OS DesktopSkills discovered reach tools: {reach_skills}")
    else:
        fail(f"JARVIS OS DesktopSkills missing reach tools: {reach_skills}")

    async def _test_desktop_exec():
        res_d = await d.execute("reach_status", {})
        if res_d.get("status") == "ok":
            ok("JARVIS OS DesktopSkills.execute reach_status verified")
        else:
            fail(f"JARVIS OS DesktopSkills.execute reach_status failed: {res_d}")
    asyncio.run(_test_desktop_exec())

def main():
    print("=== Running Agent-Reach Fleet Verification ===")
    check_systemd_service()
    check_daemon_rest()
    check_mcp_bridge()
    check_agent_configs()
    check_jarvis_tools()
    print(f"\n{GREEN}ALL VERIFICATIONS PASSED SUCCESSFULLY!{RESET}\n")

if __name__ == "__main__":
    main()
