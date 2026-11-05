#!/usr/bin/env python3
"""CLI utility for system power and session lock operations with confirmation."""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Ensure we run in project or standalone venv if available
REPO_ROOT = Path(__file__).resolve().parents[1]
_venv_python = REPO_ROOT / ".venv" / "bin" / "python"
_standalone_python = Path.home() / ".local" / "share" / "jarvis-runtime" / "venv" / "bin" / "python"
if "VIRTUAL_ENV" not in os.environ:
    target_py = _standalone_python if _standalone_python.is_file() else (_venv_python if _venv_python.is_file() else None)
    if target_py and Path(sys.executable).resolve() != target_py.resolve():
        os.execv(str(target_py), [str(target_py), *sys.argv])

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import argparse
from skills.system_power import POWER_MANAGER


def confirm_prompt(prompt_text: str) -> bool:
    """Prompt user for confirmation in terminal."""
    if not sys.stdin.isatty():
        sys.stderr.write("Confirmation required. Pass -y or --yes in non-interactive mode.\n")
        return False
    try:
        reply = input(f"{prompt_text} [y/N]: ").strip().lower()
        return reply in ("y", "yes")
    except (KeyboardInterrupt, EOFError):
        print()
        return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["shutdown", "poweroff", "restart", "reboot", "lock", "status", "confirm", "cancel"])
    parser.add_argument("-y", "--yes", action="store_true", help="Bypass interactive confirmation prompt")
    parser.add_argument("--now", action="store_true", help="Execute immediately with 0s delay")
    args = parser.parse_args(argv)

    action = args.action.lower()

    if action == "status":
        pending = POWER_MANAGER.get_pending()
        if pending:
            print(f"Pending confirmation: {pending['action']} ({pending['friendly']})")
        else:
            print("No system power action is waiting for confirmation.")
        return 0

    if action == "confirm":
        res = POWER_MANAGER.confirm_action(delay=0 if args.now else 2.0)
        if res.get("status") == "error":
            print(f"Error: {res.get('message')}")
            return 1
        print(res.get("message", "Confirmed."))
        return 0

    if action == "cancel":
        res = POWER_MANAGER.cancel_action()
        print(res.get("message", "Cancelled."))
        return 0

    friendly = {
        "shutdown": "shut down the computer",
        "poweroff": "shut down the computer",
        "restart": "restart the computer",
        "reboot": "restart the computer",
        "lock": "lock the screen",
    }.get(action, action)

    # Check confirmation
    if not args.yes:
        confirmed = confirm_prompt(f"Are you sure you want to {friendly}?")
        if not confirmed:
            print(f"{friendly.capitalize()} cancelled.")
            return 1
    else:
        confirmed = True

    delay = 0.0 if args.now else (0.0 if action == "lock" else 2.0)
    res = POWER_MANAGER.request_action(action, confirm=confirmed, delay=delay)

    if res.get("status") == "error":
        print(f"Error: {res.get('message')}")
        return 1

    print(res.get("message", "Action accepted."))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
