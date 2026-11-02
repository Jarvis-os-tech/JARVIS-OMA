"""Tests for Agent-Reach Universal MCP Server."""
import json
import subprocess
import sys
from pathlib import Path

MCP_BIN = Path.home() / ".local/bin/agent-reach-mcp"

def test_mcp_initialize():
    proc = subprocess.Popen(
        [str(MCP_BIN)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    req = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "test", "version": "1.0"}
        }
    }
    stdout, stderr = proc.communicate(input=json.dumps(req) + "\n", timeout=5)
    assert proc.returncode == 0
    resp = json.loads(stdout.strip())
    assert resp["id"] == 1
    assert "result" in resp
    assert resp["result"]["serverInfo"]["name"] == "agent-reach"

def test_mcp_tools_list():
    proc = subprocess.Popen(
        [str(MCP_BIN)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    req = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
    stdout, stderr = proc.communicate(input=json.dumps(req) + "\n", timeout=5)
    assert proc.returncode == 0
    resp = json.loads(stdout.strip())
    assert resp["id"] == 2
    tools = resp["result"]["tools"]
    tool_names = [t["name"] for t in tools]
    assert "reach_read" in tool_names
    assert "reach_search" in tool_names
    assert "reach_transcript" in tool_names
    assert "reach_status" in tool_names
