"""JARVIS Privileged Execution Gate with Pre-Action Spoken Explanation & Visual Quickshell Card.

Enforces security and transparency:
1. Pushes visual authorization card to Quickshell HUD overlay.
2. Explains the exact reason aloud via JARVIS voice before prompting.
3. Summons native graphical Polkit authentication dialog via pkexec.
"""
from __future__ import annotations

import asyncio
import json
import shlex
import shutil
from typing import Callable, Awaitable, Optional


async def _run_omarchy_cmd(action: str, payload: dict) -> None:
    if not shutil.which("omarchy-shell"):
        return
    try:
        proc = await asyncio.create_subprocess_exec(
            "omarchy-shell", "jarvis-canvas", action, json.dumps(payload),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.wait()
    except Exception:
        pass


async def push_hud_card(payload: dict) -> None:
    await _run_omarchy_cmd("present", payload)


async def dismiss_hud_card(card_id: str) -> None:
    await _run_omarchy_cmd("manage", {"id": card_id, "action": "dismiss"})


async def run_privileged_command(
    command: list[str],
    reason: str,
    speak_fn: Optional[Callable[[str], Awaitable[None]]] = None,
) -> tuple[int, str, str]:
    """1. Presents visual verification card in Quickshell HUD.

    2. Speaks explanation aloud before password prompt appears.
    3. Summons native Hyprland Polkit password dialog via pkexec.
    """
    cmd_str = shlex.join(command)

    # 1. Present visual verification card in Quickshell HUD
    await push_hud_card({
        "id": "jarvis-mandatory-alert",
        "title": "Root Authorization Required",
        "severity": "warning",
        "body": f"{reason}\nCommand: {cmd_str}",
        "ttl_ms": 15000,
    })

    # 2. Speak explanation aloud before password prompt appears
    if speak_fn is not None and callable(speak_fn):
        try:
            await speak_fn(f"Wait a sec. I need administrator permission to {reason}.")
        except Exception:
            pass

    # 3. Summon native Hyprland Polkit password dialog
    try:
        proc = await asyncio.create_subprocess_exec(
            "pkexec", *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        return proc.returncode, stdout.decode(errors="replace"), stderr.decode(errors="replace")
    finally:
        # Dismiss authorization card when action completes
        await dismiss_hud_card("jarvis-mandatory-alert")
