"""Deterministic ground-truth verification engine for JARVIS-OMA.

Adapts Google Artemis ground-truth verification patterns: validates real physical state
changes (filesystem, processes, Hyprland windows, clipboard) before declaring steps complete.
"""
from __future__ import annotations

import asyncio
from contextvars import ContextVar
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import shutil
import time
from typing import Any
from core.secret_env import sanitized_subprocess_env

log = logging.getLogger(__name__)
MAX_FILE_CONTENT_SCAN_BYTES = 1024 * 1024
ACTION_TARGET = ContextVar('jarvis_verified_action_target', default=None)


def window_identity(window: Any) -> tuple[str, int | None] | None:
    """Use a compositor address, plus PID when known, never class/title equality."""
    if not isinstance(window, dict):
        return None
    address = window.get('address')
    if not isinstance(address, str) or not re.fullmatch(r'0x[0-9a-fA-F]+', address):
        return None
    number = int(address, 16)
    if number <= 0:
        return None
    pid = window.get('pid')
    return f'0x{number:x}', pid if type(pid) is int and pid > 0 else None


def same_window(expected: Any, actual: Any) -> bool:
    first, second = window_identity(expected), window_identity(actual)
    return bool(first and second and first[0] == second[0] and
                (first[1] is None or second[1] is None or first[1] == second[1]))


def accessibility_fingerprint(state: Any) -> str | None:
    """Hash meaningful bounded AX state; ephemeral tokens/snapshot IDs do not count."""
    if not isinstance(state, dict) or state.get('degraded') or not isinstance(state.get('elements'), list):
        return None
    keys = ('role', 'label', 'name', 'value', 'text', 'description', 'enabled',
            'selected', 'checked', 'focused', 'bounds', 'states')
    elements = [{key: item[key] for key in keys if key in item}
                for item in state['elements'][:100] if isinstance(item, dict)]
    elements = [item for item in elements if item]
    if not elements:
        return None
    raw = json.dumps(elements, sort_keys=True, ensure_ascii=False, default=str)[:131072]
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


async def prepare_action_target(arguments: dict, gui=None) -> dict[str, Any]:
    """Bind one foreground target and heal focus once before any mutation."""
    from skills import system_control, modal_healing
    active = await system_control._query_active_window()
    dialog = modal_healing.classify_dialog(active) if active else None
    if dialog and dialog.requires_user_auth:
        return {'verified': False, 'reason': 'authentication prompt requires the user'}
    target = None
    healed = False
    named = arguments.get('target_window')
    if named:
        ok, reason, target = await system_control._focus_window_target(named)
        if not ok:
            return {'verified': False, 'reason': reason}
        healed = reason == 'verified_active_healed'
    elif gui is not None and arguments.get('target_window_id', arguments.get('window_id')) is not None:
        requested = arguments.get('target_window_id', arguments.get('window_id'))
        windows = (await gui.list_windows()).get('windows', [])
        target = next((item for item in windows if item.get('window_id') == requested
                       and (arguments.get('pid') is None or item.get('pid') == arguments['pid'])), None)
        if target is None or window_identity(target) is None:
            return {'verified': False, 'reason': 'exact target window could not be resolved'}
    elif gui is not None and 'x' in arguments and 'y' in arguments:
        windows = (await gui.list_windows()).get('windows', [])
        target = next((item for item in windows if same_window(active, item)), None)
        if target is None:
            return {'verified': False, 'reason': 'choose an exact observable target window before coordinate input'}
    active = await system_control._query_active_window()
    dialog = modal_healing.classify_dialog(active) if active else None
    if dialog and dialog.requires_user_auth:
        return {'verified': False, 'reason': 'authentication prompt requires the user'}
    if target is None:
        target = active
    if window_identity(target) is None:
        return {'verified': False, 'reason': 'foreground window identity unavailable'}
    if not same_window(target, active):
        await modal_healing.heal_window_focus(window_identity(target)[0])
        healed = True
        active = await system_control._query_active_window()
    if not same_window(target, active):
        return {'verified': False, 'reason': 'focus recovery did not restore the exact target'}
    return {'verified': True, 'window': target, 'healed': healed}


async def ensure_dispatch_focus() -> tuple[bool, str]:
    """Recheck the bound identity immediately before the input subprocess starts."""
    from skills import system_control, modal_healing
    context = ACTION_TARGET.get()
    if context is None:
        return True, 'no registry verification context'
    active = await system_control._query_active_window()
    dialog = modal_healing.classify_dialog(active) if active else None
    if dialog and dialog.requires_user_auth:
        return False, 'authentication prompt requires the user'
    if same_window(context['window'], active):
        return True, 'exact target is focused'
    if not context.get('healed'):
        context['healed'] = True
        await modal_healing.heal_window_focus(window_identity(context['window'])[0])
        active = await system_control._query_active_window()
    return (True, 'exact target restored') if same_window(context['window'], active) else (
        False, 'focus changed before input dispatch; no input was sent')


def _inspect_file_state(
    target: Path,
    *,
    min_bytes: int,
    expected_content: str | None,
    is_dir: bool,
) -> tuple[dict[str, Any], bool]:
    """Inspect one file-system snapshot without blocking the event loop caller."""
    if not target.exists():
        return {"path": str(target), "exists": False}, False
    st = target.stat()
    details = {
        "path": str(target),
        "exists": True,
        "is_dir": target.is_dir(),
        "size_bytes": st.st_size,
        "modified_time": st.st_mtime,
    }
    if is_dir:
        return details, target.is_dir()
    if not target.is_file() or st.st_size < min_bytes:
        return details, False
    if expected_content is None:
        return details, True
    with target.open("rb") as stream:
        content = stream.read(MAX_FILE_CONTENT_SCAN_BYTES)
    details["content_scan_bytes"] = len(content)
    details["content_scan_truncated"] = st.st_size > len(content)
    matched = expected_content in content.decode("utf-8", errors="replace")
    if matched:
        details["content_matched"] = True
    return details, matched


def _desktop_env() -> dict[str, str]:
    env = sanitized_subprocess_env()
    if "XDG_RUNTIME_DIR" not in env:
        env["XDG_RUNTIME_DIR"] = f"/run/user/{os.getuid()}"
    if "WAYLAND_DISPLAY" not in env:
        env["WAYLAND_DISPLAY"] = "wayland-1"
    return env


async def _run_command(*args: str, timeout: float = 3.0) -> tuple[int, str, str]:
    proc = None
    try:
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=_desktop_env(),
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return proc.returncode, stdout.decode("utf-8", errors="replace").strip(), stderr.decode("utf-8", errors="replace").strip()
    except BaseException as exc:
        if proc is not None:
            if proc.returncode is None:
                try:
                    proc.kill()
                except ProcessLookupError:
                    pass
            try:
                await asyncio.wait_for(proc.communicate(), 1)
            except (TimeoutError, OSError):
                pass
        if isinstance(exc, (OSError, TimeoutError)):
            return 1, "", str(exc)
        raise


async def verify_file_state(
    path: str,
    min_bytes: int = 1,
    expected_content: str | None = None,
    is_dir: bool = False,
    timeout: float = 3.0,
) -> dict[str, Any]:
    """Verify that a target file or directory exists on disk and meets size/content expectations.

    Polls periodically up to timeout seconds to accommodate asynchronous file writes.
    """
    if not path:
        return {"verified": False, "target_type": "file", "reason": "no path provided", "details": {}}

    target = Path(os.path.abspath(os.path.expanduser(path)))
    deadline = time.monotonic() + max(0.1, timeout)
    last_stat: dict[str, Any] = {}

    while time.monotonic() <= deadline:
        try:
            last_stat, matched = await asyncio.to_thread(
                _inspect_file_state,
                target,
                min_bytes=min_bytes,
                expected_content=expected_content,
                is_dir=is_dir,
            )
            if matched:
                return {"verified": True, "target_type": "file", "details": last_stat, "reason": None}
        except OSError:
            pass
        await asyncio.sleep(0.08)

    # Failed verification
    reason = "file does not exist"
    if last_stat.get("exists"):
        if is_dir and not last_stat.get("is_dir"):
            reason = "path exists but is not a directory"
        elif not is_dir and last_stat.get("is_dir"):
            reason = "path exists but is not a regular file"
        elif not is_dir and last_stat.get("size_bytes", 0) < min_bytes:
            reason = f"file size {last_stat.get('size_bytes')} bytes is less than expected {min_bytes} bytes"
        elif expected_content is not None:
            reason = "file exists and has valid size, but expected content snippet was not found"

    return {
        "verified": False,
        "target_type": "file",
        "reason": reason,
        "details": last_stat or {"path": str(target), "exists": False},
    }


async def verify_process_state(
    process_name_or_pid: str | int,
    expected_running: bool = True,
    timeout: float = 3.0,
) -> dict[str, Any]:
    """Verify whether a process is running on the system by PID or process name."""
    deadline = time.monotonic() + max(0.1, timeout)
    found_info: dict[str, Any] = {}

    while time.monotonic() <= deadline:
        is_running = False
        if isinstance(process_name_or_pid, int) or (isinstance(process_name_or_pid, str) and process_name_or_pid.isdigit()):
            pid = int(process_name_or_pid)
            try:
                os.kill(pid, 0)
                is_running = True
                found_info = {"pid": pid, "running": True}
            except OSError:
                is_running = False
                found_info = {"pid": pid, "running": False}
        else:
            proc_name = str(process_name_or_pid).strip().casefold()
            pgrep = shutil.which("pgrep")
            if pgrep:
                code, stdout, _ = await _run_command(pgrep, "-f", proc_name, timeout=1.5)
                if code == 0 and stdout:
                    pids = [int(p) for p in stdout.split() if p.isdigit()]
                    if pids:
                        is_running = True
                        found_info = {"query": proc_name, "pids": pids[:5], "running": True}
            else:
                # Fallback to inspecting /proc
                pids = []
                try:
                    for entry in os.listdir("/proc"):
                        if entry.isdigit():
                            cmdline_file = Path(f"/proc/{entry}/cmdline")
                            if cmdline_file.is_file():
                                try:
                                    cmd = cmdline_file.read_bytes().replace(b"\x00", b" ").decode("utf-8", errors="replace").casefold()
                                    if proc_name in cmd:
                                        pids.append(int(entry))
                                except OSError:
                                    pass
                except OSError:
                    pass
                if pids:
                    is_running = True
                    found_info = {"query": proc_name, "pids": pids[:5], "running": True}
                else:
                    found_info = {"query": proc_name, "running": False}

        if is_running == expected_running:
            return {
                "verified": True,
                "target_type": "process",
                "details": found_info,
                "reason": None,
            }

        await asyncio.sleep(0.1)

    return {
        "verified": False,
        "target_type": "process",
        "reason": f"process {'expected running but not found' if expected_running else 'expected stopped but still running'}",
        "details": found_info,
    }


async def verify_window_state(
    query: str,
    expected_active: bool = False,
    expected_open: bool = True,
    timeout: float = 3.0,
) -> dict[str, Any]:
    """Verify that a window matching query is open and/or active via Hyprland IPC."""
    from skills import system_control

    cleaned = system_control._clean_window_target(query)
    target = cleaned if cleaned else query.strip().casefold()

    hyprctl = shutil.which("hyprctl")
    if not hyprctl:
        return {"verified": False, "target_type": "window", "reason": "hyprctl not installed", "details": {}}

    deadline = time.monotonic() + max(0.1, timeout)
    last_details: dict[str, Any] = {}

    while time.monotonic() <= deadline:
        windows = await system_control._query_open_windows()
        active = await system_control._query_active_window()

        match = None
        for w in windows:
            if w.get("address", "").casefold() == target or w.get("class", "").casefold() == target:
                match = w
                break
        if not match:
            for w in windows:
                w_class = w.get("class", "").casefold()
                if target in w_class or (len(w_class) >= 3 and w_class in target):
                    match = w
                    break
        if not match:
            for w in windows:
                if target in w.get("title", "").casefold():
                    match = w
                    break

        is_open = match is not None
        is_active = False
        if match and active:
            is_active = (
                active.get("address", "").casefold() == match.get("address", "").casefold()
                or active.get("class", "").casefold() == match.get("class", "").casefold()
            )

        last_details = {
            "query": query,
            "target": target,
            "matched_window": match,
            "active_window": active,
            "is_open": is_open,
            "is_active": is_active,
        }

        if expected_open and not is_open:
            await asyncio.sleep(0.1)
            continue

        if not expected_open and is_open:
            await asyncio.sleep(0.1)
            continue

        if expected_active and not is_active:
            await asyncio.sleep(0.1)
            continue

        return {"verified": True, "target_type": "window", "details": last_details, "reason": None}

    # Failed
    reason = "window not found" if expected_open and not last_details.get("is_open") else "window found but not active"
    return {"verified": False, "target_type": "window", "reason": reason, "details": last_details}


async def verify_clipboard_state(
    expected_snippet: str | None = None,
    min_length: int = 1,
    timeout: float = 2.0,
) -> dict[str, Any]:
    """Verify that the Wayland clipboard contains valid text and optionally matches expected text."""
    wl_paste = shutil.which("wl-paste")
    if not wl_paste:
        return {"verified": False, "target_type": "clipboard", "reason": "wl-paste not installed", "details": {}}

    deadline = time.monotonic() + max(0.1, timeout)
    last_content = ""

    while time.monotonic() <= deadline:
        code, stdout, _ = await _run_command(wl_paste, "--no-newline", timeout=1.5)
        if code == 0:
            last_content = stdout
            if len(stdout) >= min_length:
                if expected_snippet is None or expected_snippet in stdout:
                    return {
                        "verified": True,
                        "target_type": "clipboard",
                        "details": {
                            "length": len(stdout),
                            "preview": stdout[:100],
                            "snippet_matched": expected_snippet is not None,
                        },
                        "reason": None,
                    }
        await asyncio.sleep(0.06)

    reason = "clipboard is empty or shorter than minimum length"
    if expected_snippet is not None and last_content:
        reason = f"clipboard content does not contain expected snippet: '{expected_snippet[:50]}'"

    return {
        "verified": False,
        "target_type": "clipboard",
        "reason": reason,
        "details": {"length": len(last_content), "preview": last_content[:100]},
    }


async def verify_ground_truth(target_type: str, criteria: dict[str, Any]) -> dict[str, Any]:
    """Universal ground-truth verifier routing across file, process, window, and clipboard.

    Args:
        target_type: 'file', 'process', 'window', or 'clipboard'
        criteria: parameters for the verifier
    """
    clean_type = target_type.strip().casefold()
    if clean_type == "file":
        path = criteria.get("path", "")
        min_bytes = criteria.get("min_bytes", 1)
        expected_content = criteria.get("expected_content")
        is_dir = criteria.get("is_dir", False)
        timeout = criteria.get("timeout", 3.0)
        return await verify_file_state(path, min_bytes=min_bytes, expected_content=expected_content, is_dir=is_dir, timeout=timeout)

    elif clean_type == "process":
        proc = criteria.get("process_name") or criteria.get("pid")
        if proc is None:
            return {"verified": False, "target_type": "process", "reason": "process_name or pid required", "details": {}}
        expected_running = criteria.get("expected_running", True)
        timeout = criteria.get("timeout", 3.0)
        return await verify_process_state(proc, expected_running=expected_running, timeout=timeout)

    elif clean_type == "window":
        query = criteria.get("query") or criteria.get("window_query") or criteria.get("target_window", "")
        if not query:
            return {"verified": False, "target_type": "window", "reason": "window query required", "details": {}}
        expected_active = criteria.get("expected_active", False)
        expected_open = criteria.get("expected_open", True)
        timeout = criteria.get("timeout", 3.0)
        return await verify_window_state(query, expected_active=expected_active, expected_open=expected_open, timeout=timeout)

    elif clean_type == "clipboard":
        expected_snippet = criteria.get("expected_snippet") or criteria.get("text")
        min_length = criteria.get("min_length", 1)
        timeout = criteria.get("timeout", 2.0)
        return await verify_clipboard_state(expected_snippet=expected_snippet, min_length=min_length, timeout=timeout)

    else:
        return {
            "verified": False,
            "target_type": clean_type,
            "reason": f"unknown target_type '{target_type}'. Must be one of: 'file', 'process', 'window', 'clipboard'",
            "details": {},
        }
