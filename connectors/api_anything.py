"""API-Anything platform connector for JARVIS OS.

Bridges JARVIS OS with the api-anything reverse-engineering engine and the
Omarchy API Agent Daemon (daemon.ts).
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import shutil
from typing import Any, Dict, List, Optional

from connectors import credentials
from core.secret_env import sanitized_subprocess_env

# Path to the api-anything project & daemon
DAEMON_PROJECT_DIR = Path("/home/g0pi/Projects/api-anything")
DAEMON_DIR = DAEMON_PROJECT_DIR / "daemon"
DAEMON_SCRIPT = DAEMON_DIR / "daemon.ts"
CLI_SCRIPT = DAEMON_PROJECT_DIR / "src/cli.ts"


def _resolve_bun() -> str:
    """Locate bun executable on Omarchy."""
    for path in (
        os.path.expanduser("~/.bun/bin/bun"),
        "/usr/local/bin/bun",
        "/usr/bin/bun",
        shutil.which("bun") or "",
    ):
        if path and os.path.exists(path):
            return path
    return "bun"


def _child_env() -> Dict[str, str]:
    """Prepare environment for child processes with required keys from /home/g0pi/JARVIS OS/.env."""
    env = sanitized_subprocess_env()

    # Explicitly supply LLM API keys loaded from /home/g0pi/JARVIS OS/.env
    gemini_key = (
        credentials.get("GEMINI_API_KEY_4")
        or credentials.get("GEMINI_API_KEY")
        or credentials.get("GEMINI_API_KEY_1")
        or credentials.get("GEMINI_API_KEY_3")
        or credentials.get("GEMINI_API_KEY_5")
    )
    if gemini_key:
        env["GEMINI_API_KEY"] = gemini_key

    nvidia_key = (
        credentials.get("NVIDIA_API_KEY")
        or credentials.get("NVIDIA_NIM_API_KEY")
    )
    if nvidia_key:
        env["NVIDIA_API_KEY"] = nvidia_key
        env["NVIDIA_NIM_API_KEY"] = nvidia_key

    nvidia_url = credentials.get("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
    if nvidia_url:
        env["NVIDIA_BASE_URL"] = nvidia_url

    env["JARVIS_ENV_PATH"] = "/home/g0pi/JARVIS OS/.env"
    env["NO_COLOR"] = "1"
    return env


async def _exec_bun_cmd(*args: str, timeout: float = 60.0, cwd: Optional[Path] = None) -> Dict[str, Any]:
    """Execute a bun command asynchronously and parse JSON output."""
    bun = _resolve_bun()
    env = _child_env()
    work_dir = str(cwd or DAEMON_PROJECT_DIR)

    proc = await asyncio.create_subprocess_exec(
        bun,
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=work_dir,
        env=env,
    )

    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        return {"ok": False, "error": f"Command timed out after {timeout}s"}

    out_text = stdout.decode("utf-8", errors="replace").strip()
    err_text = stderr.decode("utf-8", errors="replace").strip()

    # Find last JSON line from stdout or stderr
    for line in reversed(out_text.splitlines()):
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue

    if proc.returncode != 0:
        return {"ok": False, "error": err_text or out_text or f"Process exited with code {proc.returncode}"}

    return {"ok": True, "raw": out_text}


async def search(query: str) -> Dict[str, Any]:
    """Search for existing website API operations in local ledger and shared registry."""
    if not query.strip():
        return {"ok": False, "error": "Query cannot be empty"}
    return await _exec_bun_cmd(str(CLI_SCRIPT), "search", query.strip(), cwd=DAEMON_PROJECT_DIR)


async def list_operations(site: str) -> Dict[str, Any]:
    """List available operations, parameter schemas, and caveats for a site."""
    if not site.strip():
        return {"ok": False, "error": "Site name cannot be empty"}
    return await _exec_bun_cmd(str(CLI_SCRIPT), "ops", site.strip(), cwd=DAEMON_PROJECT_DIR)


async def call_operation(site: str, op: str, args: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Execute a learned API operation on a site with specified arguments."""
    cmd_args = [str(CLI_SCRIPT), "call", site.strip(), op.strip()]
    if args:
        for k, v in args.items():
            cmd_args.append(f"{k}={v}")

    return await _exec_bun_cmd(*cmd_args, timeout=45.0, cwd=DAEMON_PROJECT_DIR)


async def propose_blueprint(problem: str) -> Dict[str, Any]:
    """Propose an API Blueprint for a new website using Gemini 2.5 Flash."""
    return await _exec_bun_cmd(str(DAEMON_SCRIPT), "--propose", problem.strip(), timeout=120.0, cwd=DAEMON_DIR)


async def learn_and_activate(blueprint: Dict[str, Any]) -> Dict[str, Any]:
    """Execute traffic capture, parameter learning, and NVIDIA NIM integrity validation."""
    blueprint_json = json.dumps(blueprint)
    return await _exec_bun_cmd(str(DAEMON_SCRIPT), "--learn", blueprint_json, timeout=180.0, cwd=DAEMON_DIR)
