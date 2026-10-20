"""Small, checked native controls beyond the desktop plugin's public tools.

Commands always use argument arrays, user services only, and freshly discovered
device/player identifiers. No optional backend is treated as a working backend.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import json
import re
import shutil
from typing import Any

_OUTPUT_LIMIT = 65536
_TIMEOUT = 6


async def _run(*args: str) -> tuple[int, str, str]:
    """Drain bounded output, kill and reap children on timeout or cancellation."""
    proc = await asyncio.create_subprocess_exec(
        *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )

    async def read(stream):
        result = bytearray()
        while chunk := await stream.read(4096):
            result.extend(chunk[:max(0, _OUTPUT_LIMIT + 1 - len(result))])
        return bytes(result)

    readers = [asyncio.create_task(read(proc.stdout)), asyncio.create_task(read(proc.stderr))]
    try:
        async with asyncio.timeout(_TIMEOUT):
            await proc.wait()
            stdout, stderr = await asyncio.gather(*readers)
        if len(stdout) > _OUTPUT_LIMIT or len(stderr) > _OUTPUT_LIMIT:
            return -1, "", "command output exceeded limit; observation incomplete"
        return proc.returncode, stdout.decode(errors="replace").strip(), stderr.decode(errors="replace").strip()
    except (TimeoutError, asyncio.CancelledError) as exc:
        if proc.returncode is None:
            try:
                proc.kill()
            except ProcessLookupError:
                pass
        await proc.wait()
        await asyncio.gather(*readers, return_exceptions=True)
        if isinstance(exc, asyncio.CancelledError):
            raise
        return -1, "", "command timed out"


def _result(status: str, source: str, **data: Any) -> dict[str, Any]:
    return {"status": status, "source": source,
            "observed_at": datetime.now(timezone.utc).isoformat(), **data}


async def _audio(category: str, action: str, target: str | None) -> dict[str, Any]:
    backend = shutil.which("pactl")
    if not backend:
        return _result("unavailable", "pactl", message="pactl is not installed")
    if action not in {"list", "status", "set_default"}:
        return _result("error", "pactl", message="audio actions: list, status, set_default")
    kind = "sink" if category == "audio_output" else "source"
    code, out, err = await _run(backend, "-f", "json", "list", kind + "s")
    if code:
        return _result("error", "pactl", message=err or "device discovery failed")
    try:
        raw = json.loads(out)
        if not isinstance(raw, list):
            raise ValueError("expected a device list")
        devices = [{"id": str(d["name"]), "index": d.get("index"),
                    "description": d.get("description"), "state": d.get("state")}
                   for d in raw if isinstance(d, dict) and d.get("name")]
    except (ValueError, TypeError) as exc:
        return _result("error", "pactl", message=f"invalid device observation: {exc}")
    code, default, err = await _run(backend, "get-default-" + kind)
    if action != "set_default":
        return _result("success" if code == 0 else "partial", "pactl",
                       devices=devices, default_id=default if code == 0 else None,
                       **({"message": err or "default unavailable"} if code else {}))
    if not target or target not in {d["id"] for d in devices}:
        return _result("error", "pactl", message="target must exactly match an id from the current device list", devices=devices)
    code, _, err = await _run(backend, "set-default-" + kind, target)
    if code:
        return _result("error", "pactl", message=err or "default selection failed")
    code, observed, err = await _run(backend, "get-default-" + kind)
    if code:
        return _result("dispatched_unverified", "pactl", verified=False, message=err or "default readback failed")
    return _result("success" if observed == target else "error", "pactl",
                   verified=observed == target, default_id=observed, requested_id=target)


async def _service(action: str, target: str | None) -> dict[str, Any]:
    backend = shutil.which("systemctl")
    if action not in {"list", "status", "start", "stop", "restart"}:
        return _result("error", "systemctl --user", message="service actions: list, status, start, stop, restart")
    if not backend:
        return _result("unavailable", "systemctl --user", message="systemctl is not installed")
    if action == "list":
        code, out, err = await _run(backend, "--user", "list-units", "--type=service", "--all", "--no-pager", "--plain", "--no-legend")
        return _result("error" if code else "success", "systemctl --user", units=out, message=err)
    if not isinstance(target, str) or not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.@:-]{0,190}\.service", target):
        return _result("error", "systemctl --user", message="target must be an exact .service unit name; patterns and paths are unsupported")

    async def observe():
        code, out, err = await _run(backend, "--user", "show", "--no-pager", "--property=Id,LoadState,ActiveState,SubState", "--", target)
        state = dict(line.split("=", 1) for line in out.splitlines() if "=" in line)
        return code, state, err

    code, before, err = await observe()
    if code or before.get("LoadState") != "loaded" or before.get("Id") != target:
        return _result("error", "systemctl --user", message=err or "unit is not loaded or is an alias; use its exact Id", state=before)
    if action == "status":
        return _result("success", "systemctl --user", state=before)
    code, _, err = await _run(backend, "--user", action, "--", target)
    if code:
        return _result("error", "systemctl --user", message=err or "service command failed")
    code, state, err = await observe()
    if code or not state.get("ActiveState"):
        return _result("dispatched_unverified", "systemctl --user", verified=False, message=err or "state readback failed")
    expected = {"inactive", "failed"} if action == "stop" else {"active"}
    verified = state.get("ActiveState") in expected
    # An executed oneshot may already be inactive: do not claim it failed to run.
    return _result("success" if verified else "dispatched_unverified", "systemctl --user",
                   verified=verified, state=state, action=action)


async def _media(action: str, target: str | None) -> dict[str, Any]:
    backend = shutil.which("playerctl")
    if action not in {"list", "status", "play", "pause", "play_pause", "stop", "next", "previous"}:
        return _result("error", "playerctl", message="unsupported media action")
    if not backend:
        return _result("unavailable", "playerctl", message="playerctl is not installed")
    code, out, err = await _run(backend, "--list-all")
    if code:
        return _result("error", "playerctl", message=err or "no media player available")
    players = out.splitlines()
    if action == "list":
        return _result("success", "playerctl", players=players)
    if target is None and len(players) == 1:
        target = players[0]
    if not target or target not in players:
        return _result("error", "playerctl", message="choose an exact player from the current list", players=players)
    code, out, err = await _run(backend, "--player=" + target, action.replace("_", "-"))
    if code:
        return _result("error", "playerctl", message=err or "media command failed")
    if action == "status":
        return _result("success", "playerctl", player=target, playback_status=out)
    code, state, err = await _run(backend, "--player=" + target, "status")
    expected = {"play": "Playing", "pause": "Paused", "stop": "Stopped"}.get(action)
    if code:
        return _result("dispatched_unverified", "playerctl", verified=False, message=err or "playback readback failed")
    verified = expected is not None and state == expected
    # Track changes and toggle cannot be proven by a playback-status observation.
    return _result("success" if verified else "dispatched_unverified", "playerctl",
                   verified=verified, player=target, playback_status=state, action=action)


async def system_control_extension(category: str, action: str, target: str | None = None,
                                   value: Any = None) -> dict[str, Any]:
    """Control audio defaults, exact user services, or media with fresh evidence.

`value` is reserved; callers must discover device/player IDs using list first.
No arbitrary command, privileged unit, wildcard selection, or shell is accepted.
"""
    if value is not None:
        return _result("error", "native", message="value is unsupported for these controls")
    try:
        if category in {"audio_output", "audio_input"}:
            return await _audio(category, action, target)
        if category == "user_service":
            return await _service(action, target)
        if category == "media":
            return await _media(action, target)
        return _result("error", "native", message="categories: audio_output, audio_input, user_service, media")
    except OSError as exc:
        return _result("error", "native", message=str(exc))
