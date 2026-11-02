#!/usr/bin/env python3
"""Switch JARVIS service between standalone production runtime and local test workspace."""
from __future__ import annotations

import argparse
import json
import logging
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any

log = logging.getLogger("jarvis_mode")


def get_production_root() -> Path:
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / "jarvis-runtime" / "current"


def get_test_root() -> Path:
    repo = Path(__file__).resolve().parents[1]
    if (repo / "jarvis_voice").is_dir():
        return repo.resolve()
    return (Path.home() / "JARVIS OS").resolve()


PRODUCTION_ROOT = get_production_root()
TEST_ROOT = get_test_root()

DROPIN_DIR = Path.home() / ".config" / "systemd" / "user" / "jarvis-voice.service.d"
DROPIN = DROPIN_DIR / "mode.conf"
BRIDGE_DROPIN_DIR = Path.home() / ".config" / "systemd" / "user" / "jarvis-device-bridge.service.d"
BRIDGE_DROPIN = BRIDGE_DROPIN_DIR / "mode.conf"
SHARE_VOICE = Path.home() / ".local" / "share" / "jarvis-voice"
BIN_DIR = Path.home() / ".local" / "bin"

MODES = {
    "production": ("JARVIS-OS", PRODUCTION_ROOT),
    "test": ("dev", TEST_ROOT),
}


def _update_symlinks(target_root: Path) -> None:
    """Update user symlinks to point to target_root."""
    try:
        if SHARE_VOICE.is_symlink() or SHARE_VOICE.exists():
            SHARE_VOICE.unlink(missing_ok=True)
        SHARE_VOICE.symlink_to(target_root)
    except Exception as e:
        log.warning("Failed to update %s: %s", SHARE_VOICE, e)

    target_bin = target_root / "bin"
    if target_bin.is_dir():
        for cli in ("jarvis", "jarvis-voice", "jarvis-control", "jarvis-memory"):
            cli_target = target_bin / cli
            cli_link = BIN_DIR / cli
            if cli_target.is_file():
                try:
                    if cli_link.is_symlink() or cli_link.exists():
                        cli_link.unlink(missing_ok=True)
                    cli_link.symlink_to(cli_target)
                except Exception as e:
                    log.warning("Failed to link %s: %s", cli_link, e)


def restart_services() -> bool:
    """Reload systemd and restart JARVIS services."""
    try:
        subprocess.run(["systemctl", "--user", "daemon-reload"], check=True, capture_output=True)
        subprocess.run(
            ["systemctl", "--user", "restart", "jarvis-voice.service", "jarvis-device-bridge.service"],
            check=True,
            capture_output=True,
            timeout=15,
        )
        return True
    except Exception as error:
        log.warning("Failed to restart services: %s", error)
        return False


def current_mode() -> dict[str, Any]:
    """Inspect active systemd configuration to determine running mode."""
    test_root = TEST_ROOT
    prod_root = PRODUCTION_ROOT

    mode = "production"
    branch = MODES.get("production", ("JARVIS-OS", prod_root))[0]
    root = prod_root

    # Check if drop-in override is active
    if DROPIN.exists():
        try:
            content = DROPIN.read_text(encoding="utf-8")
            if str(test_root) in content:
                mode = "test"
                branch = MODES.get("test", ("dev", test_root))[0]
                root = test_root
        except Exception:
            pass
    elif SHARE_VOICE.is_symlink() and SHARE_VOICE.resolve() == test_root.resolve():
        mode = "test"
        branch = MODES.get("test", ("dev", test_root))[0]
        root = test_root

    service_active = False
    pid = None
    try:
        proc = subprocess.run(
            ["systemctl", "--user", "is-active", "jarvis-voice.service"],
            capture_output=True,
            text=True,
            check=False,
        )
        service_active = (proc.stdout.strip() == "active")
        if service_active:
            pid_proc = subprocess.run(
                ["systemctl", "--user", "show", "jarvis-voice.service", "--property=MainPID"],
                capture_output=True,
                text=True,
                check=False,
            )
            for line in pid_proc.stdout.splitlines():
                if line.startswith("MainPID="):
                    pid_val = line.split("=", 1)[1].strip()
                    if pid_val.isdigit() and int(pid_val) > 0:
                        pid = int(pid_val)
    except Exception:
        pass

    return {
        "status": "active" if service_active else "inactive",
        "mode": mode,
        "branch": branch,
        "root": str(root),
        "service_active": service_active,
        "pid": pid,
    }


def switch_mode(mode: str, *, restart: bool = True, sync: bool = False) -> dict[str, Any]:
    """Switch JARVIS between production standalone runtime and local test workspace."""
    norm_mode = mode.lower().strip()
    if norm_mode in ("dev", "test"):
        target_mode = "test"
    elif norm_mode in ("prod", "production"):
        target_mode = "production"
    elif norm_mode == "status":
        return current_mode()
    else:
        raise ValueError(f"Invalid mode '{mode}'. Choose 'test' or 'production'.")

    test_root = TEST_ROOT
    prod_root = PRODUCTION_ROOT

    if target_mode == "test":
        # 1. Write drop-ins for systemd user services (quoting paths with spaces)
        DROPIN_DIR.mkdir(parents=True, exist_ok=True)
        DROPIN.write_text(
            f"[Service]\n"
            f'WorkingDirectory="{test_root}"\n'
            f"ExecStart=\n"
            f'ExecStart="{test_root}/bin/jarvis-voice" run\n'
            f'Environment=PYTHONPATH="{test_root}"\n',
            encoding="utf-8",
        )

        BRIDGE_DROPIN_DIR.mkdir(parents=True, exist_ok=True)
        BRIDGE_DROPIN.write_text(
            f"[Service]\n"
            f'WorkingDirectory="{test_root}"\n'
            f"ExecStart=\n"
            f'ExecStart="{test_root}/.venv/bin/python" -m jarvis_control.device_bridge\n'
            f'Environment=PYTHONPATH="{test_root}"\n',
            encoding="utf-8",
        )

        _update_symlinks(test_root)
        active_root = test_root
        msg = f"Testing mode activated. Connected to development workspace at {test_root}. Restarting services."

    else:  # production
        if DROPIN.exists():
            try:
                DROPIN.unlink()
            except Exception:
                pass
        if BRIDGE_DROPIN.exists():
            try:
                BRIDGE_DROPIN.unlink()
            except Exception:
                pass

        _update_symlinks(prod_root)
        active_root = prod_root
        msg = "Production mode activated. Connected to standalone compiled runtime. Restarting services."

    restarted = False
    if restart:
        restarted = restart_services()

    branch = MODES.get(target_mode, (target_mode, active_root))[0]

    return {
        "status": "success",
        "mode": target_mode,
        "branch": branch,
        "root": str(active_root),
        "restarted": restarted,
        "message": msg,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", nargs="?", choices=("production", "prod", "test", "dev", "status"), default="status")
    parser.add_argument("--no-restart", action="store_true", help="Do not restart systemd service")
    args = parser.parse_args(argv)

    try:
        result = switch_mode(args.mode, restart=not args.no_restart)
    except Exception as exc:
        sys.stderr.write(f"Error: {exc}\n")
        return 1

    if args.mode == "status":
        state = "running (PID {})".format(result["pid"]) if result.get("service_active") and result.get("pid") else (
            "active" if result.get("service_active") else "inactive"
        )
        print(f"JARVIS Mode: {result['mode'].upper()}\n  Root:    {result['root']}\n  Service: {state}")
    else:
        print(f"JARVIS switched to: {result['mode'].upper()} ({result['root']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
