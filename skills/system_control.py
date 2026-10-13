"""Native Omarchy desktop and system controlling utilities for JARVIS-OMA.

Adapted from Omarchy-AI to provide direct, native Wayland/Hyprland input
simulation, top-bar shell control, keybinding dispatch, and hardware adjustments
without external CUA agent dependencies.
"""
from __future__ import annotations

import asyncio
import difflib
import json
import logging
import os
import re
import shutil
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

_TIMEOUT = 10.0
_KEYBINDINGS_SCRIPT = "/usr/share/omarchy/bin/omarchy-menu-keybindings"
_WTYPE_MODIFIERS = {"shift", "ctrl", "alt", "logo", "altgr", "capslock"}
_TERMINAL_CLASSES = ("foot", "kitty", "alacritty", "ghostty", "wezterm", "konsole", "terminal")


def _desktop_env() -> dict[str, str]:
    """Preserve essential desktop session and Wayland environment variables."""
    env = dict(os.environ)
    if "OMARCHY_PATH" not in env:
        env["OMARCHY_PATH"] = "/usr/share/omarchy"
    return env


async def _run_command(*args: str, timeout: float = _TIMEOUT, env: dict[str, str] | None = None) -> tuple[int, str, str]:
    """Execute an async subprocess and return (exit_code, stdout, stderr)."""
    process = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env or _desktop_env(),
    )
    try:
        stdout_bytes, stderr_bytes = await asyncio.wait_for(process.communicate(), timeout=timeout)
        stdout = stdout_bytes.decode("utf-8", errors="replace").strip()
        stderr = stderr_bytes.decode("utf-8", errors="replace").strip()
        return process.returncode or 0, stdout, stderr
    except asyncio.TimeoutError:
        try:
            process.kill()
        except OSError:
            pass
        return -1, "", "command timed out"


async def type_text(text: str) -> dict[str, Any]:
    """Type text into the focused window using wtype.

    Multi-line text uses wl-copy + paste shortcut to preserve indentation and
    prevent premature execution from newline key events.
    """
    if not text:
        return {"status": "error", "message": "no text provided"}

    wtype = shutil.which("wtype")
    if not wtype:
        return {"status": "error", "message": "wtype is not installed"}

    clean_text = text.rstrip("\r\n")
    if not clean_text:
        return {"status": "error", "message": "no text provided"}

    # Handle multi-line text via clipboard paste
    if "\n" in clean_text:
        wl_copy = shutil.which("wl-copy")
        if wl_copy:
            try:
                proc = await asyncio.create_subprocess_exec(
                    wl_copy,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                    env=_desktop_env(),
                )
                await asyncio.wait_for(proc.communicate(clean_text.encode("utf-8")), timeout=5)
            except (OSError, asyncio.TimeoutError):
                return {"status": "error", "message": "failed to copy multi-line text to clipboard"}

            # Determine if current window is a terminal to send Ctrl+Shift+V
            code, stdout, _ = await _run_command("hyprctl", "activewindow", "-j", timeout=2)
            is_terminal = False
            if code == 0 and stdout:
                try:
                    active = json.loads(stdout)
                    app_class = str(active.get("class", "")).casefold()
                    is_terminal = any(term in app_class for term in _TERMINAL_CLASSES)
                except (ValueError, TypeError):
                    pass

            argv = [wtype, "-M", "ctrl"] + (["-M", "shift"] if is_terminal else []) + ["-k", "v"]
            argv += (["-m", "shift"] if is_terminal else []) + ["-m", "ctrl"]
            code, _, stderr = await _run_command(*argv)
            if code == 0:
                return {"status": "success", "method": "clipboard_paste", "length": len(clean_text)}
            return {"status": "error", "message": f"paste keypress failed: {stderr}"}

    # Single-line typing
    code, _, stderr = await _run_command(wtype, "--", clean_text)
    if code == 0:
        return {"status": "success", "method": "typed", "length": len(clean_text)}
    return {"status": "error", "message": f"wtype typing failed: {stderr}"}


async def press_key(key: str, modifiers: str | list[str] | None = None) -> dict[str, Any]:
    """Press a key or key combination with modifiers using wtype."""
    if not key:
        return {"status": "error", "message": "no key provided"}

    wtype = shutil.which("wtype")
    if not wtype:
        return {"status": "error", "message": "wtype is not installed"}

    if isinstance(modifiers, str):
        mods_list = [m.strip() for m in re.split(r"[,+\s]+", modifiers) if m.strip()]
    elif isinstance(modifiers, list):
        mods_list = modifiers
    else:
        mods_list = []

    normalized_mods = []
    for mod in mods_list:
        m = str(mod).strip().lower()
        if m in ("super", "win"):
            m = "logo"
        if m not in _WTYPE_MODIFIERS:
            return {"status": "error", "message": f"unknown modifier '{mod}'"}
        normalized_mods.append(m)

    argv = [wtype]
    for m in normalized_mods:
        argv += ["-M", m]
    argv += ["-k", key]
    for m in reversed(normalized_mods):
        argv += ["-m", m]

    code, _, stderr = await _run_command(*argv)
    if code == 0:
        return {"status": "success", "key": key, "modifiers": normalized_mods}
    return {"status": "error", "message": f"wtype press_key failed: {stderr}"}


async def list_desktop_commands(query: str | None = None, limit: int = 25) -> dict[str, Any]:
    """Extract and list desktop keybindings/actions from omarchy-menu-keybindings."""
    script_path = _KEYBINDINGS_SCRIPT if Path(_KEYBINDINGS_SCRIPT).exists() else shutil.which("omarchy-menu-keybindings")
    if not script_path:
        return {"status": "error", "message": "omarchy-menu-keybindings is not installed"}

    extract_cmd = f"set -- --print; source {script_path} >/dev/null 2>&1; output_binding_records"
    process = await asyncio.create_subprocess_exec(
        "bash", "-c", extract_cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=_desktop_env(),
    )
    try:
        stdout_bytes, _ = await asyncio.wait_for(process.communicate(), timeout=_TIMEOUT)
        stdout = stdout_bytes.decode("utf-8", errors="replace")
    except asyncio.TimeoutError:
        try:
            process.kill()
        except OSError:
            pass
        return {"status": "error", "message": "keybindings loading timed out"}

    bindings = []
    for line in stdout.splitlines():
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        left = parts[0]
        dispatcher = parts[1] if len(parts) > 1 else ""
        arg = parts[2] if len(parts) > 2 else ""

        if "→" in left:
            keys, title = left.split("→", 1)
        else:
            keys, title = "", left

        keys = keys.strip()
        title = title.strip()
        if "MOUSE" in keys.upper():
            continue

        bindings.append({
            "title": title,
            "keys": keys,
            "dispatcher": dispatcher,
            "arg": arg,
        })

    if query:
        q = query.strip().lower()
        titles = [b["title"] for b in bindings]
        exact = [b for b in bindings if q in b["title"].lower() or (b["keys"] and q in b["keys"].lower())]
        fuzzy_titles = difflib.get_close_matches(q, titles, n=limit, cutoff=0.4)
        fuzzy = [b for b in bindings if b["title"] in fuzzy_titles and b not in exact]
        results = (exact + fuzzy)[:limit]
    else:
        results = bindings[:limit]

    return {
        "status": "success",
        "commands": [{"title": b["title"], "keys": b["keys"]} for b in results],
        "count": len(results),
        "total_available": len(bindings),
    }


async def execute_desktop_command(title: str) -> dict[str, Any]:
    """Execute an Omarchy keybinding command by its title."""
    if not title:
        return {"status": "error", "message": "command title is required"}

    script_path = _KEYBINDINGS_SCRIPT if Path(_KEYBINDINGS_SCRIPT).exists() else shutil.which("omarchy-menu-keybindings")
    if not script_path:
        return {"status": "error", "message": "omarchy-menu-keybindings is not installed"}

    extract_cmd = f"set -- --print; source {script_path} >/dev/null 2>&1; output_binding_records"
    process = await asyncio.create_subprocess_exec(
        "bash", "-c", extract_cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=_desktop_env(),
    )
    try:
        stdout_bytes, _ = await asyncio.wait_for(process.communicate(), timeout=_TIMEOUT)
        stdout = stdout_bytes.decode("utf-8", errors="replace")
    except asyncio.TimeoutError:
        return {"status": "error", "message": "keybindings loading timed out"}

    bindings = []
    for line in stdout.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            left = parts[0]
            dispatcher = parts[1]
            arg = parts[2] if len(parts) > 2 else ""
            t = left.split("→", 1)[1].strip() if "→" in left else left.strip()
            bindings.append({"title": t, "dispatcher": dispatcher, "arg": arg})

    if not bindings:
        return {"status": "error", "message": "no keybindings available"}

    target = title.strip().lower()
    match = next((b for b in bindings if b["title"].lower() == target), None)
    if not match:
        matches = [b for b in bindings if target in b["title"].lower()]
        if matches:
            match = matches[0]
        else:
            close = difflib.get_close_matches(title, [b["title"] for b in bindings], n=1, cutoff=0.5)
            if close:
                match = next(b for b in bindings if b["title"] == close[0])

    if not match:
        return {"status": "error", "message": f"no command matching '{title}' found"}

    dispatch_cmd = f"set -- --print; source {script_path} >/dev/null 2>&1; dispatch_binding \"$DISPATCHER\" \"$ARG\""
    env = {**_desktop_env(), "DISPATCHER": match["dispatcher"], "ARG": match["arg"]}
    code, stdout, stderr = await _run_command("bash", "-c", dispatch_cmd, env=env)
    if code == 0:
        return {"status": "success", "executed": match["title"]}
    return {"status": "error", "message": stderr or stdout or "dispatch failed"}


async def list_bar_panels() -> dict[str, Any]:
    """Query omarchy-shell to discover installed top-bar panels and widgets."""
    shell = shutil.which("omarchy-shell")
    if not shell:
        return {"status": "error", "message": "omarchy-shell is not installed"}

    code, stdout, stderr = await _run_command(shell, "shell", "listPlugins")
    if code != 0:
        return {"status": "error", "message": f"failed to query plugins: {stderr}"}

    try:
        plugins = json.loads(stdout)
    except ValueError:
        return {"status": "error", "message": "invalid plugins response from shell"}

    panels = [
        {
            "id": p.get("id"),
            "name": p.get("name"),
            "enabled": p.get("enabled", False),
            "kinds": p.get("kinds", []),
        }
        for p in plugins
        if isinstance(p, dict) and p.get("id")
    ]
    return {"status": "success", "panels": panels, "count": len(panels)}


async def open_bar_panel(panel_id: str) -> dict[str, Any]:
    """Summon/open a top-bar settings panel by plugin ID."""
    if not panel_id:
        return {"status": "error", "message": "panel_id is required"}

    shell = shutil.which("omarchy-shell")
    if not shell:
        return {"status": "error", "message": "omarchy-shell is not installed"}

    code, stdout, stderr = await _run_command(shell, "shell", "summon", panel_id, "{}")
    if code == 0 and stdout in ("ok", ""):
        return {"status": "success", "action": "summoned", "panel_id": panel_id}
    return {"status": "error", "message": stderr or stdout or "summon failed"}


async def close_bar_panel(panel_id: str) -> dict[str, Any]:
    """Dismiss/hide an open top-bar panel by plugin ID."""
    if not panel_id:
        return {"status": "error", "message": "panel_id is required"}

    shell = shutil.which("omarchy-shell")
    if not shell:
        return {"status": "error", "message": "omarchy-shell is not installed"}

    code, stdout, stderr = await _run_command(shell, "shell", "hide", panel_id)
    if code == 0:
        return {"status": "success", "action": "hidden", "panel_id": panel_id}
    return {"status": "error", "message": stderr or stdout or "hide failed"}


async def set_volume(percent: int) -> dict[str, Any]:
    """Set master speaker volume to an exact percentage (0-100%)."""
    wpctl = shutil.which("wpctl")
    if not wpctl:
        return {"status": "error", "message": "wpctl is not installed"}

    clamped = max(0, min(100, int(percent)))
    fraction = f"{clamped / 100.0:.2f}"

    code, _, stderr = await _run_command(wpctl, "set-volume", "@DEFAULT_AUDIO_SINK@", fraction)
    if code != 0:
        return {"status": "error", "message": f"failed to set volume: {stderr}"}

    # Ensure audio sink is unmuted if setting volume > 0
    if clamped > 0:
        await _run_command(wpctl, "set-mute", "@DEFAULT_AUDIO_SINK@", "0")

    return {"status": "success", "volume_percent": clamped}


async def control_microphone(action: str) -> dict[str, Any]:
    """Mute, unmute, or toggle default microphone mute state."""
    wpctl = shutil.which("wpctl")
    if not wpctl:
        return {"status": "error", "message": "wpctl is not installed"}

    action_lower = str(action).strip().lower()
    arg = {
        "mute": "1",
        "unmute": "0",
        "toggle": "toggle",
    }.get(action_lower)

    if not arg:
        return {"status": "error", "message": "action must be 'mute', 'unmute', or 'toggle'"}

    code, _, stderr = await _run_command(wpctl, "set-mute", "@DEFAULT_AUDIO_SOURCE@", arg)
    if code != 0:
        return {"status": "error", "message": f"failed to control microphone: {stderr}"}

    return {"status": "success", "action": action_lower}


async def set_brightness(percent: int) -> dict[str, Any]:
    """Set display brightness to an exact percentage (1-100%)."""
    brightnessctl = shutil.which("brightnessctl")
    if not brightnessctl:
        return {"status": "error", "message": "brightnessctl is not installed"}

    clamped = max(1, min(100, int(percent)))
    code, _, stderr = await _run_command(brightnessctl, "set", f"{clamped}%")
    if code != 0:
        return {"status": "error", "message": f"failed to set brightness: {stderr}"}

    return {"status": "success", "brightness_percent": clamped}


async def move_window_to_workspace(workspace: int) -> dict[str, Any]:
    """Move the currently active window to a specific workspace number."""
    hyprctl = shutil.which("hyprctl")
    if not hyprctl:
        return {"status": "error", "message": "hyprctl is not installed"}

    ws = int(workspace)
    code, _, stderr = await _run_command(hyprctl, "dispatch", "movetoworkspacesilent", str(ws))
    if code != 0:
        return {"status": "error", "message": f"failed to move window: {stderr}"}

    return {"status": "success", "workspace": ws}
