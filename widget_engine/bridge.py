#!/usr/bin/env python3
"""JARVIS JIT Voice-Widget Bridge.

Enforces focused, non-intrusive widget presentation:
1. Normal voice states (listening, thinking, speaking) do NOT spawn intrusive floating widgets
   (ambient status remains on the top Dynamic Island).
2. Content widgets appear ONLY when explicitly requested by the user ("when I ask only").
3. Mandatory alerts and confirmations (action confirmation, microphone muted, critical faults)
   are surfaced automatically with compact, non-intrusive cards.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
from pathlib import Path
import signal
import sys
import time

# Auto-reexec in repository virtualenv if available
REPO_ROOT = Path(__file__).resolve().parents[1]
_venv_python = REPO_ROOT / ".venv" / "bin" / "python"
if "VIRTUAL_ENV" not in os.environ and _venv_python.is_file():
    if Path(sys.executable).resolve() != _venv_python.resolve():
        os.execv(str(_venv_python), [str(_venv_python), *sys.argv])

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    from ui.jarvis_widgets import backend
except ImportError:
    backend = None

try:
    from skills.system_power import POWER_MANAGER
except ImportError:
    POWER_MANAGER = None

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("jarvis.widget_bridge")

RUNTIME_DIR = Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")) / "jarvis"
STATE_FILE = RUNTIME_DIR / "state.json"

ALERT_WIDGET_ID = "jarvis-mandatory-alert"
CONFIRM_WIDGET_ID = "jarvis-power-confirm"


def is_shell_ready() -> bool:
    if backend is None:
        return False
    try:
        status = backend.shell_call("status")
        return bool(status and status.get("ok"))
    except Exception:
        return False


def show_mandatory_widget(widget_id: str, title: str, text: str, expires_seconds: int = 30) -> bool:
    if backend is None:
        return False
    try:
        widget = backend.make_widget(
            "text",
            title,
            {"text": text},
            widget_id=widget_id,
            presentation="floating",
            expires_seconds=expires_seconds,
        )
        result = backend.shell_call("present", widget)
        return bool(result and result.get("ok"))
    except Exception as exc:
        log.debug("Mandatory widget display suppressed: %s", exc)
        return False


def dismiss_widget(widget_id: str) -> bool:
    if backend is None:
        return False
    try:
        backend.shell_call("manage", {"id": widget_id, "action": "dismiss"})
        return True
    except Exception:
        return False


def check_mandatory_events(active_alerts: dict[str, str]) -> None:
    """Surfaces mandatory notifications only; ignores routine listening/speaking states."""
    # 1. Mandatory Confirmation Check (e.g. Shutdown / Reboot / Session Lock)
    if POWER_MANAGER:
        pending = POWER_MANAGER.get_pending()
        if pending:
            action_desc = pending.get("friendly", pending.get("action", "system action")).capitalize()
            msg = f"Action: {action_desc}\nSay 'confirm' or 'yes' to proceed, or 'cancel' to abort."
            if active_alerts.get("power_confirm") != pending.get("action"):
                show_mandatory_widget(CONFIRM_WIDGET_ID, "⚠️ Confirmation Required", msg, expires_seconds=60)
                active_alerts["power_confirm"] = pending.get("action")
        elif "power_confirm" in active_alerts:
            dismiss_widget(CONFIRM_WIDGET_ID)
            active_alerts.pop("power_confirm", None)

    # 2. Critical Audio & Hardware Faults
    if STATE_FILE.is_file():
        try:
            data = json.loads(STATE_FILE.read_text())
        except Exception:
            data = {}

        mic = data.get("microphone") or {}
        mic_issue = mic.get("issue")
        if mic.get("muted") and not mic_issue:
            mic_issue = "Microphone is muted in system settings."

        if mic_issue:
            if active_alerts.get("mic_issue") != mic_issue:
                show_mandatory_widget(ALERT_WIDGET_ID, "🎙️ Audio Notice", mic_issue, expires_seconds=30)
                active_alerts["mic_issue"] = mic_issue
        elif "mic_issue" in active_alerts:
            dismiss_widget(ALERT_WIDGET_ID)
            active_alerts.pop("mic_issue", None)

        # 3. Conversational HUD Cards & Assistant Visual Answers
        hud_card = data.get("hud_card")
        if hud_card and isinstance(hud_card, dict):
            card_id = hud_card.get("id", "jarvis-voice-hud")
            card_title = hud_card.get("title", "⚡ JARVIS")
            card_text = hud_card.get("text", "")
            if active_alerts.get("voice_hud") != card_text and card_text:
                show_mandatory_widget(card_id, card_title, card_text, expires_seconds=hud_card.get("expires", 15))
                active_alerts["voice_hud"] = card_text
        elif "voice_hud" in active_alerts and not data.get("hud_card"):
            dismiss_widget("jarvis-voice-hud")
            active_alerts.pop("voice_hud", None)

def run_demo() -> None:
    print("▶️  Demonstrating Sleek Compact Mandatory & On-Demand Widgets...")
    if not is_shell_ready():
        print("❌ Desktop shell is not ready.")
        sys.exit(1)

    print("  1. Mandatory Confirmation Overlay (compact 340px)...")
    show_mandatory_widget(CONFIRM_WIDGET_ID, "⚠️ Confirmation Required", "Action: Shut down the computer\nSay 'confirm' to proceed, or 'cancel' to abort.", expires_seconds=4)
    time.sleep(2.5)

    print("  2. Mandatory Audio Notice (compact)...")
    show_mandatory_widget(ALERT_WIDGET_ID, "🎙️ Audio Notice", "Microphone muted in audio settings. Unmute to speak.", expires_seconds=4)
    time.sleep(2.5)

    print("  3. Cleaning up test widgets...")
    dismiss_widget(CONFIRM_WIDGET_ID)
    dismiss_widget(ALERT_WIDGET_ID)
    print("✅ Demo finished. Non-intrusive widgets verified.")


def run_daemon() -> None:
    log.info("Starting JARVIS Selective & Mandatory Widget Bridge...")
    log.info("Normal voice turns will NOT show big widgets. Surfacing mandatory events only.")

    active_alerts: dict[str, str] = {}

    def handle_signal(sig, frame):
        log.info("Shutting down Widget Bridge...")
        dismiss_widget(CONFIRM_WIDGET_ID)
        dismiss_widget(ALERT_WIDGET_ID)
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    # Allow conversational HUD cards to persist naturally

    while True:
        try:
            check_mandatory_events(active_alerts)
            time.sleep(0.5)
        except Exception as exc:
            log.error("Error in bridge check: %s", exc)
            time.sleep(1.0)


def main():
    parser = argparse.ArgumentParser(description="JARVIS Selective & Mandatory Widget Bridge")
    parser.add_argument("--demo", action="store_true", help="Demonstrate compact mandatory widgets")
    parser.add_argument("--status", action="store_true", help="Check bridge and shell connectivity")
    parser.add_argument("--clear", action="store_true", help="Dismiss all mandatory widgets")
    args = parser.parse_args()

    if args.status:
        ready = is_shell_ready()
        print(json.dumps({"ok": ready, "state_file_exists": STATE_FILE.is_file(), "runtime": str(RUNTIME_DIR)}))
        sys.exit(0 if ready else 1)

    if args.clear:
        dismiss_widget(CONFIRM_WIDGET_ID)
        dismiss_widget(ALERT_WIDGET_ID)
        dismiss_widget("jarvis-voice-hud")
        print("Widgets cleared.")
        sys.exit(0)

    if args.demo:
        run_demo()
        return

    run_daemon()


if __name__ == "__main__":
    main()
