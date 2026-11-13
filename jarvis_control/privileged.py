"""Privileged command execution engine with SUDO_ASKPASS Wayland popup,
spoken voice rationale, microphone mute protection, and automatic pre-change Btrfs snapshots.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import re
import shlex
import socket
import subprocess
import time
from typing import Any

from .security import check_package_removal, validate_package_removal, ProtectedPackageError

log = logging.getLogger('jarvis.privileged')

ASKPASS_BIN = Path(os.environ.get("JARVIS_ASKPASS_PATH", "/home/g0pi/.local/bin/jarvis-askpass"))
SPEAK_SOCK = Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")) / "jarvis-voice-speak.sock"
CONTROL_SOCK = Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")) / "jarvis" / "control.sock"


def speak_explanation(text: str) -> None:
    """Send spoken explanation to JARVIS Voice or OS Speaker before prompting."""
    if not text or not text.strip():
        return
    payload = json.dumps({
        "command": "speak",
        "text": text.strip(),
        "priority": "critical",
        "source": "privileged_control",
        "dedup_key": f"priv_{abs(hash(text)) % 100000}"
    }) + "\n"

    for sock_path in (SPEAK_SOCK, CONTROL_SOCK):
        if sock_path.exists():
            try:
                with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
                    s.settimeout(0.5)
                    s.connect(str(sock_path))
                    s.sendall(payload.encode())
                    _ = s.recv(1024)
                    return
            except Exception as err:
                log.debug("Speech socket error on %s: %s", sock_path, err)


def set_voice_listening_paused(paused: bool) -> None:
    """Signal JARVIS voice IPC to pause/resume microphone capture while typing password."""
    if not CONTROL_SOCK.exists():
        return
    req = json.dumps({"command": "set_mute", "muted": bool(paused)}) + "\n"
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            s.connect(str(CONTROL_SOCK))
            s.sendall(req.encode())
            _ = s.recv(1024)
    except Exception as err:
        log.debug("Failed toggling voice mute on %s: %s", CONTROL_SOCK, err)


def build_btrfs_snapshot_command(target_cmd: list[str]) -> list[str]:
    """Wraps target command with a pre-change Btrfs snapshot in a single root batch."""
    escaped_target = " ".join(shlex.quote(c) for c in target_cmd)
    batch_script = (
        'if command -v snapper >/dev/null 2>&1; then '
        'snapper -c root create -d "jarvis-pre-$(date +%Y%m%d%H%M%S)" -t pre || true; '
        'elif [ -d /.snapshots ]; then '
        'btrfs subvolume snapshot -r / "/.snapshots/jarvis-pre-$(date +%Y%m%d%H%M%S)" 2>/dev/null || true; '
        'fi; '
        f'exec {escaped_target}'
    )
    return ["bash", "-c", batch_script]


def run_privileged_action(
    command: list[str],
    reason: str = "Administrative privileges are required for this action.",
    destructive: bool = False,
    timeout: float = 300.0
) -> dict[str, Any]:
    """Execute a command with root privileges using SUDO_ASKPASS, voice explanations,
    listening suppression, and automated safety snapshots.
    """
    if not command:
        return {"ok": False, "output": "Empty command provided", "code": 1}

    cmd_str = " ".join(shlex.quote(c) for c in command)

    # Step A: Spoken explanation first so the user knows WHY access is requested
    if reason:
        speak_explanation(reason)

    # Step B: Pause microphone listening during typing to prevent VAD false triggers
    set_voice_listening_paused(True)

    try:
        # Step C: Prepare command batch (prepending Btrfs snapshot if destructive)
        final_cmd = build_btrfs_snapshot_command(command) if destructive else command

        # Step D: Execute via sudo -A
        env = dict(os.environ)
        if ASKPASS_BIN.exists():
            env["SUDO_ASKPASS"] = str(ASKPASS_BIN)
        env["JARVIS_SUDO_REASON"] = reason
        env["JARVIS_SUDO_CMD"] = cmd_str

        full_argv = ["sudo", "-A", *final_cmd]

        proc = subprocess.run(
            full_argv,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout
        )

        ok = (proc.returncode == 0)
        output = (proc.stdout + ("\n" + proc.stderr if proc.stderr else "")).strip()

        if ok:
            log.info("Privileged action succeeded: %s", cmd_str)
        else:
            log.warning("Privileged action failed (code %d): %s", proc.returncode, output)
            if proc.returncode == 1 and not output:
                output = "Authentication cancelled or timed out."

        return {
            "ok": ok,
            "output": output,
            "code": proc.returncode,
            "command": cmd_str,
            "destructive": destructive
        }

    except subprocess.TimeoutExpired:
        log.warning("Privileged action timed out after %ds: %s", timeout, cmd_str)
        return {"ok": False, "output": f"Command timed out after {timeout} seconds", "code": 124}
    except Exception as exc:
        log.error("Privileged execution error: %s", exc)
        return {"ok": False, "output": str(exc), "code": 1}
    finally:
        # Step B resume: Resume microphone listening immediately after dialog dismisses
        set_voice_listening_paused(False)


# --- Full-Range System Tool Handlers ---

def execute_manage_packages(
    action: str,
    packages: list[str] | str | None = None,
    reason: str = ""
) -> dict[str, Any]:
    """Execute package management (install, remove, search, list_installed, update_system)."""
    action = str(action).strip().lower()
    if packages is None:
        pkg_list = []
    elif isinstance(packages, str):
        pkg_list = [p.strip() for p in re.split(r'[\s,]+', packages) if p.strip()]
    else:
        pkg_list = [str(p).strip() for p in packages if str(p).strip()]

    if action == "remove":
        if not pkg_list:
            return {"ok": False, "output": "No packages specified for removal", "code": 1}
        # Check core OS package protection denylist
        err = validate_package_removal(pkg_list)
        if err:
            return {"ok": False, "output": f"ERROR: {err}", "code": 1}

        spk_reason = reason or f"I need administrator access to remove package(s): {', '.join(pkg_list)}."
        cmd = ["pacman", "-Rns", "--noconfirm", *pkg_list]
        return run_privileged_action(cmd, reason=spk_reason, destructive=True)

    elif action == "install":
        if not pkg_list:
            return {"ok": False, "output": "No packages specified for installation", "code": 1}
        spk_reason = reason or f"I need administrator access to install package(s): {', '.join(pkg_list)}."
        cmd = ["pacman", "-S", "--noconfirm", "--needed", *pkg_list]
        res = run_privileged_action(cmd, reason=spk_reason, destructive=False)
        # Fallback to yay for AUR packages if not in main repos
        if not res["ok"] and any("target not found" in res["output"].lower() for _ in [1]):
            log.info("Pacman could not find target, attempting yay for %s", pkg_list)
            cmd_yay = ["yay", "-S", "--noconfirm", "--needed", *pkg_list]
            return run_privileged_action(cmd_yay, reason=spk_reason, destructive=False)
        return res

    elif action == "update_system":
        spk_reason = reason or "I need administrator access to perform a full system update."
        cmd = ["pacman", "-Syu", "--noconfirm"]
        return run_privileged_action(cmd, reason=spk_reason, destructive=True)

    elif action == "search":
        query = " ".join(pkg_list) if pkg_list else ""
        if not query:
            return {"ok": False, "output": "No search query provided", "code": 1}
        proc = subprocess.run(["pacman", "-Ss", query], capture_output=True, text=True, timeout=30)
        return {"ok": proc.returncode == 0, "output": proc.stdout[:4000].strip(), "code": proc.returncode}

    elif action in ("list_installed", "query"):
        proc = subprocess.run(["pacman", "-Qe"], capture_output=True, text=True, timeout=30)
        return {"ok": proc.returncode == 0, "output": proc.stdout[:4000].strip(), "code": proc.returncode}

    else:
        return {"ok": False, "output": f"Unknown package action: {action}", "code": 1}


def execute_manage_system_service(
    unit: str,
    action: str,
    scope: str = "system",
    reason: str = ""
) -> dict[str, Any]:
    """Execute systemd unit management."""
    unit = str(unit).strip()
    action = str(action).strip().lower()
    scope = str(scope).strip().lower()

    if not unit.endswith(('.service', '.socket', '.timer', '.target')):
        unit = f"{unit}.service"

    if scope == "user":
        if action == "logs":
            cmd = ["journalctl", "--user", "-u", unit, "-n", "50", "--no-pager"]
        elif action == "status":
            cmd = ["systemctl", "--user", "status", unit]
        else:
            cmd = ["systemctl", "--user", action, unit]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return {"ok": proc.returncode == 0, "output": (proc.stdout + proc.stderr).strip(), "code": proc.returncode}

    # System scope
    if action in ("status", "is-active", "is-enabled"):
        proc = subprocess.run(["systemctl", action, unit], capture_output=True, text=True, timeout=30)
        return {"ok": proc.returncode == 0, "output": (proc.stdout + proc.stderr).strip(), "code": proc.returncode}
    elif action == "logs":
        proc = subprocess.run(["journalctl", "-u", unit, "-n", "50", "--no-pager"], capture_output=True, text=True, timeout=30)
        return {"ok": proc.returncode == 0, "output": (proc.stdout + proc.stderr).strip(), "code": proc.returncode}
    else:
        # State-modifying actions require sudo
        spk_reason = reason or f"I need administrator access to {action} {unit}."
        destructive = (action in ("stop", "disable"))
        return run_privileged_action(["systemctl", action, unit], reason=spk_reason, destructive=destructive)


def execute_modify_system_config(
    path: str,
    patch_or_content: str,
    reason: str = "",
    append: bool = False
) -> dict[str, Any]:
    """Safely back up and modify user or system configurations."""
    raw_path = str(path).strip()
    target_path = Path(os.path.expanduser(raw_path)).resolve()
    is_system = str(target_path).startswith("/etc") or not os.access(target_path.parent, os.W_OK)

    # 1. Automatic backup
    backup_path = target_path.with_name(f"{target_path.name}.jarvis.bak")
    if target_path.exists():
        try:
            if not is_system:
                import shutil
                shutil.copy2(target_path, backup_path)
            else:
                spk_reason = reason or f"Backing up system configuration {target_path}."
                run_privileged_action(["cp", "-a", str(target_path), str(backup_path)], reason=spk_reason, destructive=False)
        except Exception as err:
            log.warning("Could not create backup of %s: %s", target_path, err)

    # 2. Write modification
    if not is_system:
        try:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            mode = "a" if append else "w"
            with open(target_path, mode, encoding="utf-8") as f:
                f.write(patch_or_content)
            return {"ok": True, "output": f"Successfully updated {target_path} (backup at {backup_path.name})", "code": 0}
        except Exception as exc:
            return {"ok": False, "output": f"Failed writing {target_path}: {exc}", "code": 1}
    else:
        # Write to temporary file, then copy via privileged action
        import tempfile
        spk_reason = reason or f"I need administrator access to modify system configuration {target_path}."
        with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8") as tmp:
            tmp_name = tmp.name
            if append and target_path.exists():
                tmp.write(target_path.read_text(encoding="utf-8", errors="ignore"))
            tmp.write(patch_or_content)

        try:
            res = run_privileged_action(["cp", tmp_name, str(target_path)], reason=spk_reason, destructive=True)
            if res["ok"]:
                # Ensure correct permissions
                run_privileged_action(["chmod", "644", str(target_path)], reason="", destructive=False)
                res["output"] = f"Successfully modified {target_path} (backup at {backup_path.name})"
            return res
        finally:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass


def execute_general_command(
    command: str,
    requires_sudo: bool = False,
    reason: str = ""
) -> dict[str, Any]:
    """Execute arbitrary system command with or without sudo."""
    cmd_str = str(command).strip()
    if not cmd_str:
        return {"ok": False, "output": "Empty command string", "code": 1}

    if requires_sudo:
        spk_reason = reason or f"I need administrator access to execute: {cmd_str[:60]}."
        destructive = any(kw in cmd_str for kw in ("rm -r", "mkfs", "dd", "pacman -R", "reboot", "poweroff"))
        return run_privileged_action(["bash", "-c", cmd_str], reason=spk_reason, destructive=destructive)
    else:
        proc = subprocess.run(["bash", "-c", cmd_str], capture_output=True, text=True, timeout=120)
        return {
            "ok": proc.returncode == 0,
            "output": (proc.stdout + proc.stderr).strip(),
            "code": proc.returncode
        }
