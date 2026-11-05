"""System Power & Session Lifecycle Management with Mandatory Confirmation.

Provides secure sequences for shutdown, restart, and screen locking with
spoken and programmatic confirmation gates to prevent accidental invocations.
"""
from __future__ import annotations

import asyncio
import logging
import os
import shutil
import subprocess
import time
from typing import Any, Callable

log = logging.getLogger("system_power")

# Expiration window for unconfirmed actions (seconds)
CONFIRMATION_TIMEOUT_SECONDS = 60.0

# Supported confirmation words/phrases
CONFIRM_PHRASES = frozenset({
    "yes", "confirm", "proceed", "do it", "sure", "yeah", "yep",
    "go ahead", "ok", "okay", "affirmative", "absolutely", "please do",
})

# Supported cancellation words/phrases
CANCEL_PHRASES = frozenset({
    "no", "cancel", "stop", "abort", "don't", "dont", "nevermind", "wait",
})


class SystemPowerManager:
    """Manages pending confirmation state and execution of power/session actions."""

    def __init__(self, run_cmd: Callable[..., Any] | None = None) -> None:
        self._pending: dict[str, Any] | None = None
        self._run_cmd = run_cmd or self._default_run_cmd

    @staticmethod
    def _default_run_cmd(cmd: list[str]) -> subprocess.CompletedProcess:
        return subprocess.run(cmd, capture_output=True, text=True, check=False)

    def get_pending(self) -> dict[str, Any] | None:
        """Return the current active pending action, or None if empty or expired."""
        if self._pending is None:
            return None
        elapsed = time.monotonic() - self._pending.get("created_at", 0)
        if elapsed > CONFIRMATION_TIMEOUT_SECONDS:
            log.info("Pending power action '%s' expired after %.1fs", self._pending.get("action"), elapsed)
            self._pending = None
            return None
        return dict(self._pending)

    def clear_pending(self) -> dict[str, Any] | None:
        """Clear and return any pending action."""
        prev = self.get_pending()
        self._pending = None
        self._dismiss_confirmation_widget()
        return prev

    def _show_confirmation_widget(self, action: str, friendly: str) -> None:
        """Mandatory visual confirmation overlay on screen."""
        try:
            from ui.jarvis_widgets import backend
            widget = backend.make_widget(
                "text",
                "⚠️ Confirmation Required",
                {"text": f"Action: {friendly.capitalize()}\nSay 'confirm' or 'yes' to proceed, or 'cancel' to abort."},
                widget_id="jarvis-power-confirm",
                presentation="floating",
                expires_seconds=int(CONFIRMATION_TIMEOUT_SECONDS),
            )
            backend.shell_call("present", widget)
        except Exception as exc:
            log.debug("Power confirmation widget display suppressed: %s", exc)

    def _dismiss_confirmation_widget(self) -> None:
        """Dismiss the visual confirmation overlay."""
        try:
            from ui.jarvis_widgets import backend
            backend.shell_call("manage", {"id": "jarvis-power-confirm", "action": "dismiss"})
        except Exception:
            pass

    def _get_action_command(self, action: str) -> list[str]:
        norm = action.lower().strip().replace("-", "_")
        if norm in ("shutdown", "poweroff", "power_off"):
            omarchy_sys = shutil.which("omarchy-system") or "/usr/share/omarchy/bin/omarchy-system"
            if os.path.exists(omarchy_sys) and os.access(omarchy_sys, os.X_OK):
                return [omarchy_sys, "shutdown"]
            systemctl = shutil.which("systemctl") or "/usr/bin/systemctl"
            return [systemctl, "poweroff"]
        if norm in ("restart", "reboot"):
            omarchy_sys = shutil.which("omarchy-system") or "/usr/share/omarchy/bin/omarchy-system"
            if os.path.exists(omarchy_sys) and os.access(omarchy_sys, os.X_OK):
                return [omarchy_sys, "reboot"]
            systemctl = shutil.which("systemctl") or "/usr/bin/systemctl"
            return [systemctl, "reboot"]
        if norm in ("lock", "lock_screen", "screen_lock"):
            omarchy_lock = shutil.which("omarchy-system-lock") or "/usr/share/omarchy/bin/omarchy-system-lock"
            if os.path.exists(omarchy_lock) and os.access(omarchy_lock, os.X_OK):
                return [omarchy_lock]
            for locker in ("hyprlock", "swaylock", "waylock"):
                path = shutil.which(locker)
                if path:
                    return [path]
            loginctl = shutil.which("loginctl") or "/usr/bin/loginctl"
            return [loginctl, "lock-session"]
        raise ValueError(f"Unsupported system power action: {action}")

    def _get_friendly_name(self, action: str) -> str:
        norm = action.lower().strip().replace("-", "_")
        if norm in ("shutdown", "poweroff", "power_off"):
            return "shut down the computer"
        if norm in ("restart", "reboot"):
            return "restart the computer"
        if norm in ("lock", "lock_screen", "screen_lock"):
            return "lock the screen"
        return action

    def request_action(
        self,
        action: str,
        confirm: bool = False,
        delay: float = 2.0,
    ) -> dict[str, Any]:
        """Request a power action.

        If confirm is True, dispatches the action immediately (or schedules deferred
        execution for shutdown/restart). If False, holds the action in a pending state
        and returns a prompt requesting confirmation.
        """
        norm = action.lower().strip().replace("-", "_")
        if norm in ("confirm", "proceed"):
            return self.confirm_action(heard_phrase="yes", delay=delay)
        if norm in ("cancel", "abort"):
            return self.cancel_action()

        friendly = self._get_friendly_name(norm)
        cmd = self._get_action_command(norm)

        if not confirm:
            self._pending = {
                "action": norm,
                "command": cmd,
                "friendly": friendly,
                "created_at": time.monotonic(),
            }
            self._show_confirmation_widget(norm, friendly)
            return {
                "status": "needs_confirmation",
                "action": norm,
                "confirmed": False,
                "prompt": f"Are you sure you want to {friendly}? Please confirm out loud to proceed, or say cancel.",
                "message": f"Confirmation required to {friendly}.",
            }

        # Confirmed execution
        self._pending = None
        self._dismiss_confirmation_widget()
        return self._execute_action(norm, cmd, delay=delay)

    def confirm_action(self, heard_phrase: str = "yes", delay: float = 2.0) -> dict[str, Any]:
        """Confirm and execute the currently pending power action."""
        pending = self.get_pending()
        if not pending:
            return {
                "status": "error",
                "message": "No system action is currently waiting for confirmation.",
            }

        cleaned = heard_phrase.lower().strip().strip("!.,?\"'")
        words = set(cleaned.split())
        is_confirmed = bool(words & CONFIRM_PHRASES or cleaned in CONFIRM_PHRASES)

        if not is_confirmed:
            return {
                "status": "error",
                "message": f"'{heard_phrase}' is not a recognized confirmation. Say confirm to proceed, or cancel to abort.",
                "pending_action": pending["action"],
            }

        self._pending = None
        self._dismiss_confirmation_widget()
        return self._execute_action(pending["action"], pending["command"], delay=delay)

    def cancel_action(self) -> dict[str, Any]:
        """Cancel the currently pending power action."""
        pending = self.clear_pending()
        if not pending:
            return {
                "status": "ok",
                "message": "Nothing was waiting for confirmation.",
            }
        return {
            "status": "cancelled",
            "action": pending["action"],
            "message": f"Cancelled {pending['friendly']}.",
        }

    def _execute_action(self, action: str, cmd: list[str], delay: float = 2.0) -> dict[str, Any]:
        """Execute or schedule execution of the power action command."""
        friendly = self._get_friendly_name(action)

        if action in ("shutdown", "poweroff", "restart", "reboot"):
            # Schedule execution with a brief delay so audio acknowledgements and IPC responses finish cleanly
            def _deferred_exec():
                if delay > 0:
                    time.sleep(delay)
                self._run_cmd(cmd)

            import threading
            thread = threading.Thread(target=_deferred_exec, daemon=True)
            thread.start()

            return {
                "status": "executing",
                "action": action,
                "confirmed": True,
                "message": f"Confirmation received. {friendly.capitalize()} in {delay:.1f} seconds.",
            }

        # Lock screen executes immediately
        res = self._run_cmd(cmd)
        if isinstance(res, subprocess.CompletedProcess) and res.returncode != 0:
            return {
                "status": "error",
                "action": action,
                "message": f"Failed to {friendly}: {res.stderr or 'command exited with code ' + str(res.returncode)}",
            }
        return {
            "status": "locked",
            "action": action,
            "confirmed": True,
            "message": "Screen session locked.",
        }


# Global singleton instance
POWER_MANAGER = SystemPowerManager()
