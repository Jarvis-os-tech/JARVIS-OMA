"""Autonomous modal detection, safe dialog handling, and focus self-healing for Hyprland desktop.

Adapts Google Artemis reliability patterns to detect interruptions (authentication prompts,
file conflicts, confirmation alerts, focus theft) and recover or safely yield to the user.
"""
from __future__ import annotations

import asyncio
from enum import Enum
import json
import logging
import os
import re
import shutil
from typing import Any

log = logging.getLogger(__name__)

# Known authentication prompt window classes (polkit, keyring, pinentry)
_AUTH_CLASSES = {
    "polkit-gnome-authentication-agent-1",
    "org.kde.polkit-kde-authentication-agent-1",
    "gcr-prompter",
    "pinentry",
    "pinentry-gtk",
    "pinentry-gtk-2",
    "pinentry-qt",
    "pinentry-curses",
    "lxpolkit",
    "mate-polkit",
    "xfce-polkit",
    "org.freedesktop.impl.portal.desktop.gtk",
}

_AUTH_TITLE_PATTERNS = [
    r"\bauthenticate\b",
    r"\bauthentication required\b",
    r"\benter password\b",
    r"\bunlock keyring\b",
    r"\bpolkit\b",
]

_FILE_PROMPT_PATTERNS = [
    r"\balready exists\b",
    r"\bconfirm save as\b",
    r"\breplace file\b",
    r"\bconfirm overwrite\b",
    r"\boverwrite\b",
    r"\bfile exists\b",
]

_CONFIRMATION_PATTERNS = [
    r"\bconfirm\b",
    r"\bunsaved changes\b",
    r"\bare you sure\b",
    r"\bsave changes\b",
    r"\bdiscard changes\b",
    r"\bwarning\b",
]

_ALERT_PATTERNS = [
    r"\berror\b",
    r"\balert\b",
    r"\bnotice\b",
    r"\battention\b",
]

_DIALOG_TOOL_CLASSES = {
    "zenity",
    "kdialog",
    "xmessage",
    "yad",
}


class DialogType(str, Enum):
    AUTH_PROMPT = "auth_prompt"
    FILE_OVERWRITE = "file_overwrite"
    CONFIRMATION = "confirmation"
    ALERT = "alert"
    GENERIC_MODAL = "generic_modal"


class DesktopDialog:
    """Represents a detected on-screen desktop modal or prompt."""

    def __init__(
        self,
        address: str,
        title: str,
        app_class: str,
        dialog_type: DialogType,
        is_floating: bool = True,
        requires_user_auth: bool = False,
        safe_to_dismiss: bool = True,
        suggested_actions: list[str] | None = None,
        workspace_id: int | None = None,
    ):
        self.address = address
        self.title = title
        self.app_class = app_class
        self.dialog_type = dialog_type
        self.is_floating = is_floating
        self.requires_user_auth = requires_user_auth
        self.safe_to_dismiss = safe_to_dismiss
        self.suggested_actions = suggested_actions or ["dismiss", "cancel"]
        self.workspace_id = workspace_id

    def to_dict(self) -> dict[str, Any]:
        return {
            "address": self.address,
            "title": self.title,
            "class": self.app_class,
            "dialog_type": self.dialog_type.value,
            "floating": self.is_floating,
            "requires_user_auth": self.requires_user_auth,
            "safe_to_dismiss": self.safe_to_dismiss,
            "suggested_actions": list(self.suggested_actions),
            "workspace_id": self.workspace_id,
        }


def _desktop_env() -> dict[str, str]:
    env = os.environ.copy()
    if "XDG_RUNTIME_DIR" not in env:
        env["XDG_RUNTIME_DIR"] = f"/run/user/{os.getuid()}"
    if "WAYLAND_DISPLAY" not in env:
        env["WAYLAND_DISPLAY"] = "wayland-1"
    return env


async def _run_command(*args: str, timeout: float = 3.0) -> tuple[int, str, str]:
    try:
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=_desktop_env(),
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return proc.returncode, stdout.decode("utf-8", errors="replace").strip(), stderr.decode("utf-8", errors="replace").strip()
    except (OSError, asyncio.TimeoutError) as exc:
        return 1, "", str(exc)


async def _query_clients() -> list[dict[str, Any]]:
    hyprctl = shutil.which("hyprctl")
    if not hyprctl:
        return []
    code, stdout, _ = await _run_command(hyprctl, "clients", "-j", timeout=2)
    if code == 0 and stdout:
        try:
            windows = json.loads(stdout)
            if isinstance(windows, list):
                return [w for w in windows if isinstance(w, dict)]
        except (ValueError, TypeError):
            pass
    return []


async def _query_active_window() -> dict[str, Any] | None:
    hyprctl = shutil.which("hyprctl")
    if not hyprctl:
        return None
    code, stdout, _ = await _run_command(hyprctl, "activewindow", "-j", timeout=2)
    if code == 0 and stdout:
        try:
            active = json.loads(stdout)
            if isinstance(active, dict) and active.get("address"):
                return active
        except (ValueError, TypeError):
            pass
    return None


def classify_dialog(window: dict[str, Any]) -> DesktopDialog | None:
    """Classify a Hyprland window client as a modal/dialog if it matches known patterns."""
    if not isinstance(window, dict):
        return None

    app_class = str(window.get("class", "")).strip().casefold()
    title = str(window.get("title", "")).strip()
    title_lower = title.casefold()
    is_floating = bool(window.get("floating", False))
    address = str(window.get("address", "")).strip()
    ws_id = window.get("workspace", {}).get("id") if isinstance(window.get("workspace"), dict) else None

    if not address:
        return None

    # Check 1: Authentication prompt (Polkit, Keyring, Pinentry)
    is_auth = (
        app_class in _AUTH_CLASSES
        or any(auth_cls in app_class for auth_cls in ("polkit", "pinentry", "gcr-prompter", "gnome-keyring"))
        or any(re.search(pat, title_lower) for pat in _AUTH_TITLE_PATTERNS)
    )
    if is_auth:
        return DesktopDialog(
            address=address,
            title=title,
            app_class=app_class,
            dialog_type=DialogType.AUTH_PROMPT,
            is_floating=is_floating,
            requires_user_auth=True,
            safe_to_dismiss=False,
            suggested_actions=["user_auth_required", "cancel"],
            workspace_id=ws_id,
        )

    # Check 2: File prompt / overwrite dialog
    if any(re.search(pat, title_lower) for pat in _FILE_PROMPT_PATTERNS):
        return DesktopDialog(
            address=address,
            title=title,
            app_class=app_class,
            dialog_type=DialogType.FILE_OVERWRITE,
            is_floating=is_floating,
            requires_user_auth=False,
            safe_to_dismiss=True,
            suggested_actions=["confirm", "cancel", "dismiss"],
            workspace_id=ws_id,
        )

    # Check 3: Dialog CLI tools (zenity, kdialog, yad)
    if app_class in _DIALOG_TOOL_CLASSES:
        return DesktopDialog(
            address=address,
            title=title,
            app_class=app_class,
            dialog_type=DialogType.GENERIC_MODAL,
            is_floating=is_floating,
            requires_user_auth=False,
            safe_to_dismiss=True,
            suggested_actions=["confirm", "cancel", "dismiss"],
            workspace_id=ws_id,
        )

    # Check 4: Floating windows with dialog/alert titles
    if is_floating:
        if any(re.search(pat, title_lower) for pat in _CONFIRMATION_PATTERNS):
            return DesktopDialog(
                address=address,
                title=title,
                app_class=app_class,
                dialog_type=DialogType.CONFIRMATION,
                is_floating=True,
                requires_user_auth=False,
                safe_to_dismiss=True,
                suggested_actions=["confirm", "cancel", "dismiss"],
                workspace_id=ws_id,
            )
        if any(re.search(pat, title_lower) for pat in _ALERT_PATTERNS):
            return DesktopDialog(
                address=address,
                title=title,
                app_class=app_class,
                dialog_type=DialogType.ALERT,
                is_floating=True,
                requires_user_auth=False,
                safe_to_dismiss=True,
                suggested_actions=["dismiss", "confirm"],
                workspace_id=ws_id,
            )
        # Check window title or class containing 'dialog' or 'popup'
        if "dialog" in title_lower or "dialog" in app_class or "prompt" in title_lower or "popup" in app_class:
            return DesktopDialog(
                address=address,
                title=title,
                app_class=app_class,
                dialog_type=DialogType.GENERIC_MODAL,
                is_floating=True,
                requires_user_auth=False,
                safe_to_dismiss=True,
                suggested_actions=["confirm", "cancel", "dismiss"],
                workspace_id=ws_id,
            )

    return None


async def detect_desktop_dialogs() -> list[dict[str, Any]]:
    """Scan open windows and return structured descriptors for all detected modals and prompts."""
    windows = await _query_clients()
    detected = []
    for w in windows:
        classified = classify_dialog(w)
        if classified:
            detected.append(classified.to_dict())
    return detected


async def handle_desktop_dialog(action: str, dialog_id: str | None = None) -> dict[str, Any]:
    """Safely dismiss, cancel, or confirm an active desktop dialog.

    Security Guardrail:
        Strictly blocks autonomous confirmation of authentication prompts (polkit, keyring,
        pinentry). When an auth prompt is active, returns a security notice requiring manual
        user authorization.

    Args:
        action: 'dismiss' (Escape / Close), 'cancel' (Escape), or 'confirm' (Enter).
        dialog_id: Optional window address of the dialog. If omitted, uses the active window
                   or first detected floating dialog.
    """
    clean_action = action.strip().casefold()
    if clean_action not in ("dismiss", "cancel", "confirm"):
        return {
            "status": "error",
            "message": "action must be one of: 'dismiss', 'cancel', 'confirm'",
        }

    hyprctl = shutil.which("hyprctl")
    wtype = shutil.which("wtype")
    if not hyprctl:
        return {"status": "error", "message": "hyprctl is not installed"}

    dialogs = await detect_desktop_dialogs()
    target_dialog = None

    if dialog_id:
        target_dialog = next((d for d in dialogs if d["address"].casefold() == dialog_id.casefold()), None)
        if not target_dialog:
            # Fallback check against open windows directly
            clients = await _query_clients()
            direct_win = next((w for w in clients if str(w.get("address", "")).casefold() == dialog_id.casefold()), None)
            if direct_win:
                target_dialog = (classify_dialog(direct_win) or DesktopDialog(
                    address=direct_win["address"],
                    title=direct_win.get("title", ""),
                    app_class=direct_win.get("class", ""),
                    dialog_type=DialogType.GENERIC_MODAL,
                    is_floating=bool(direct_win.get("floating", False)),
                )).to_dict()

    if not target_dialog:
        active = await _query_active_window()
        if active:
            active_dialog = classify_dialog(active)
            if active_dialog:
                target_dialog = active_dialog.to_dict()

    if not target_dialog and dialogs:
        target_dialog = dialogs[0]

    if not target_dialog:
        return {
            "status": "no_dialog_found",
            "message": "No active or blocking desktop dialog found to handle.",
            "remaining_dialogs": 0,
        }

    # SECURITY GUARDRAIL: Block autonomous confirmation of auth prompts
    if target_dialog.get("requires_user_auth"):
        if clean_action == "confirm":
            return {
                "status": "blocked_by_security",
                "message": (
                    f"Autonomous authorization of system authentication prompt '{target_dialog.get('title')}' "
                    f"({target_dialog.get('class')}) is strictly blocked for security. "
                    f"The user must manually enter credentials or confirm on screen."
                ),
                "dialog": target_dialog,
            }
        # Dismissing/cancelling an auth prompt is allowed to abort the privilege escalation
        log.info("Safely cancelling authentication prompt %s", target_dialog.get("address"))

    addr = target_dialog.get("address", "")

    # Focus the dialog first
    lua_focus = f'hl.dsp.focus({{ window = "address:{addr}" }})'
    await _run_command(hyprctl, "dispatch", lua_focus, timeout=2)
    await asyncio.sleep(0.06)

    # Dispatch resolution action
    if clean_action in ("dismiss", "cancel"):
        # Send Escape key
        if wtype:
            await _run_command(wtype, "-k", "Escape", timeout=2)
            await asyncio.sleep(0.08)

        # Check if still open; if so, send close dispatch
        active = await _query_active_window()
        if active and active.get("address", "").casefold() == addr.casefold():
            lua_close = f'hl.dsp.window.close({{ window = "address:{addr}" }})'
            code, _, _ = await _run_command(hyprctl, "dispatch", lua_close, timeout=2)
            if code != 0:
                await _run_command(hyprctl, "dispatch", "closewindow", f"address:{addr}", timeout=2)

    elif clean_action == "confirm":
        if wtype:
            await _run_command(wtype, "-k", "Return", timeout=2)
        else:
            return {"status": "error", "message": "wtype is required to confirm dialogs"}

    await asyncio.sleep(0.08)

    remaining = await detect_desktop_dialogs()
    return {
        "status": "handled",
        "action": clean_action,
        "handled_dialog": target_dialog,
        "remaining_dialogs": len(remaining),
    }


async def heal_window_focus(target_window: str) -> dict[str, Any]:
    """Diagnose and restore window focus if stolen by a background process, notification, or pop-up.

    Args:
        target_window: Application class, window title keyword, or window address to restore.
    """
    from skills import system_control

    cleaned = system_control._clean_window_target(target_window)
    query_str = cleaned if cleaned else target_window.strip().casefold()

    hyprctl = shutil.which("hyprctl")
    if not hyprctl:
        return {"status": "error", "message": "hyprctl is not installed"}

    windows = await _query_clients()
    active = await _query_active_window()

    if not windows:
        return {"status": "error", "message": "no open windows found"}

    # Find expected target window
    match = None
    for w in windows:
        if w.get("address", "").casefold() == query_str or w.get("class", "").casefold() == query_str:
            match = w
            break
    if not match:
        for w in windows:
            w_class = w.get("class", "").casefold()
            if query_str in w_class or (len(w_class) >= 3 and w_class in query_str):
                match = w
                break
    if not match:
        for w in windows:
            if query_str in w.get("title", "").casefold():
                match = w
                break

    if not match:
        return {
            "status": "target_not_found",
            "message": f"Target window '{target_window}' not found among open windows.",
        }

    match_addr = match.get("address", "").casefold()
    active_addr = active.get("address", "").casefold() if active else ""

    # Check if target is already focused
    if active_addr and active_addr == match_addr:
        return {
            "status": "already_focused",
            "window": match,
            "was_stolen": False,
        }

    # Inspect active window to see why focus drifted
    active_dialog = classify_dialog(active) if active else None
    stolen_by = active or {}

    # Dispatched focus restoration
    lua_focus = f'hl.dsp.focus({{ window = "address:{match["address"]}" }})'
    code, _, _ = await _run_command(hyprctl, "dispatch", lua_focus, timeout=2)
    if code != 0:
        await _run_command(hyprctl, "dispatch", "focuswindow", f'address:{match["address"]}', timeout=2)

    await asyncio.sleep(0.08)
    new_active = await _query_active_window()
    recovered = bool(new_active and new_active.get("address", "").casefold() == match_addr)

    return {
        "status": "healed" if recovered else "healing_failed",
        "was_stolen": True,
        "stolen_by": stolen_by,
        "active_dialog": active_dialog.to_dict() if active_dialog else None,
        "target_window": match,
        "recovered": recovered,
    }
