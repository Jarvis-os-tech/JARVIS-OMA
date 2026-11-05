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
import signal
from typing import Any, Dict, List, Optional

from connectors import credentials
from core.secret_env import sanitized_subprocess_env

# Path to the api-anything project & daemon
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DAEMON_PROJECT_DIR = Path(os.environ.get("API_ANYTHING_DIR", Path.home() / "Projects/api-anything"))
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

    # Explicitly supply all Gemini keys loaded from /home/g0pi/JARVIS OS/.env
    for k in (
        "GEMINI_API_KEY",
        "GEMINI_API_KEY_4",
        "GEMINI_API_KEY_1",
        "GEMINI_API_KEY_3",
        "GEMINI_API_KEY_5",
    ):
        val = credentials.get(k)
        if val:
            env[k] = val

    if not env.get("GEMINI_API_KEY"):
        env["GEMINI_API_KEY"] = env.get("GEMINI_API_KEY_4") or env.get("GEMINI_API_KEY_1") or ""

    # Explicitly supply all NVIDIA keys
    for k in ("NVIDIA_API_KEY", "NVIDIA_NIM_API_KEY"):
        val = credentials.get(k)
        if val:
            env[k] = val

    if not env.get("NVIDIA_API_KEY"):
        env["NVIDIA_API_KEY"] = env.get("NVIDIA_NIM_API_KEY") or ""

    nvidia_url = credentials.get("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
    if nvidia_url:
        env["NVIDIA_BASE_URL"] = nvidia_url

    env["JARVIS_ENV_PATH"] = str(PROJECT_ROOT / ".env")
    env["NO_COLOR"] = "1"
    return env


async def _exec_bun_cmd(*args: str, timeout: float = 60.0, cwd: Optional[Path] = None) -> Dict[str, Any]:
    """Execute a bun command asynchronously and parse JSON output."""
    bun = _resolve_bun()
    env = _child_env()
    work_dir = str(cwd or DAEMON_PROJECT_DIR)

    try:
        proc = await asyncio.create_subprocess_exec(
            bun, *args, stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            cwd=work_dir, env=env, start_new_session=True,
        )
    except OSError as exc:
        return {'ok': False, 'status': 'unavailable', 'error': str(exc)}

    async def terminate():
        # The API agent may own an MCP/browser subprocess. Cancel its whole
        # process group so an outer tool deadline cannot leave it working.
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        await proc.wait()

    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        await terminate()
        return {'ok': False, 'status': 'unknown', 'completed': False,
                'error': f'Command timed out after {timeout}s; final effect is unknown. Do not replay a write.'}
    except asyncio.CancelledError:
        await terminate()
        raise

    out_text = stdout.decode("utf-8", errors="replace").strip()
    err_text = stderr.decode("utf-8", errors="replace").strip()

    # Both channels are used by the upstream machine interface. An exit
    # failure always wins over an earlier success-shaped log line.
    payload = None
    for line in reversed((out_text if proc.returncode == 0 else err_text + '\n' + out_text).splitlines()):
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                candidate = json.loads(line)
                if isinstance(candidate, dict):
                    if payload is None or candidate.get('ok') is False:
                        payload = candidate
                    if candidate.get('ok') is False:
                        break
            except json.JSONDecodeError:
                continue

    if proc.returncode != 0:
        return {'ok': False, 'completed': False, 'status': 'failed',
                'error': (payload or {}).get('error') or f'API process exited with code {proc.returncode}',
                'exit_code': proc.returncode}

    if payload is None:
        # CLI lists legitimately return arrays; parse the complete stdout too.
        try:
            value = json.loads(out_text)
            if isinstance(value, list):
                return {'ok': True, 'data': value}
        except ValueError:
            pass
        return {'ok': False, 'status': 'unverified', 'completed': False,
                'error': 'API process returned no machine-readable result'}
    if payload.get('write') in ('accepted', 'may_have_applied'):
        payload.update(status='unverified', completed=False,
                       reason='Write was submitted but its effect has not been verified; do not repeat it.')
    return payload


async def _request(operation: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    from connectors.api_service import request, dispatch_local
    # Only a failure to connect permits local execution. Once a request was
    # submitted, an interrupted response must never replay an external action.
    result = await request(operation, arguments)
    return await dispatch_local(operation, arguments) if result is None else result


async def search(query: str) -> Dict[str, Any]:
    """Search for existing website API operations in local ledger and shared registry."""
    if not query.strip():
        return {"ok": False, "error": "Query cannot be empty"}
    return await _request('search', {'query': query.strip()})


async def list_operations(site: str) -> Dict[str, Any]:
    """List available operations, parameter schemas, and caveats for a site."""
    if not site.strip():
        return {"ok": False, "error": "Site name cannot be empty"}
    return await _request('operations', {'site': site.strip()})


async def call_operation(site: str, op: str, args: Optional[Dict[str, Any]] = None,
                         allow_writes: bool = False, request_key: Optional[str] = None) -> Dict[str, Any]:
    """Execute a learned API operation on a site with specified arguments."""
    return await _request('call', {'site': site, 'op': op, 'args': args or {},
                                 'allow_writes': allow_writes, 'request_key': request_key})


async def propose_blueprint(problem: str) -> Dict[str, Any]:
    """Propose an API Blueprint for a new website using Gemini 2.5 Flash."""
    return await _request('propose', {'problem': problem.strip()})


async def learn_and_activate(blueprint: Dict[str, Any]) -> Dict[str, Any]:
    """Execute traffic capture, parameter learning, and NVIDIA NIM integrity validation."""
    return await _request('learn', {'blueprint': blueprint})
