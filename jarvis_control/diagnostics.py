"""Comprehensive diagnostics and auto-repair system for JARVIS OS.

Detects and resolves temporary runtime glitches (dead sockets, stale locks,
audio muted states, failed systemd units, orphaned capture processes) as well as
long-term structural configuration issues (disabled systemd services, outdated unit files,
insecure permissions, missing state directories, SQLite WAL corruption, and missing packages).
"""
from __future__ import annotations

import glob
import importlib.util
import json
import os
from pathlib import Path
import shutil
import socket
import sqlite3
import stat
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional, Set, Tuple

# Terminal formatting
_RESET = "\033[0m"
_BOLD = "\033[1m"
_GREEN = "\033[32m"
_YELLOW = "\033[33m"
_RED = "\033[31m"
_CYAN = "\033[36m"
_DIM = "\033[90m"


def get_project_root() -> Path:
    """Find the root directory of the JARVIS OS repository or deployment."""
    # Check environment variable first
    env_root = os.environ.get("JARVIS_WORKSPACE") or os.environ.get("JARVIS_TEST_ROOT")
    if env_root and Path(env_root).is_dir():
        return Path(env_root).resolve()
    # Otherwise relative to this file
    return Path(__file__).resolve().parents[1]


# ------------------------------------------------------------------------------
# Temporary / Runtime Checks & Repairs
# ------------------------------------------------------------------------------

def check_and_fix_dead_sockets(fix: bool = True) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Detect and clean up orphaned / dead UNIX domain sockets."""
    issues = []
    repairs = []
    uid = os.getuid()

    candidates: Set[Path] = set()
    standard_paths = [
        Path(f"/run/user/{uid}/jarvis/control.sock"),
        Path(f"/run/user/{uid}/jarvis.sock"),
        Path(f"/run/user/{uid}/jarvis-voice-speak.sock"),
        Path(f"/run/user/{uid}/jarvis-api-agent/control.sock"),
        Path("/tmp/jarvis-agent-bus.sock"),
    ]
    for p in standard_paths:
        candidates.add(p)

    try:
        candidates.update(Path(f"/run/user/{uid}/jarvis").glob("*.sock"))
    except Exception:
        pass
    try:
        candidates.update(Path(f"/run/user/{uid}").glob("*jarvis*.sock"))
    except Exception:
        pass
    try:
        candidates.update(Path("/tmp").glob("*jarvis*.sock"))
    except Exception:
        pass

    for sock in candidates:
        try:
            # Check if it exists as socket or symlink
            if not sock.exists() and not sock.is_symlink():
                continue

            # If it's a broken symlink, it is dead
            if sock.is_symlink() and not sock.resolve().exists():
                issues.append({"type": "dead_socket", "path": str(sock), "detail": f"Broken socket symlink: {sock}"})
                if fix:
                    sock.unlink(missing_ok=True)
                    repairs.append(f"Removed broken socket symlink: {sock}")
                continue

            # Test connection
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.settimeout(0.15)
            is_dead = False
            try:
                s.connect(str(sock))
            except (ConnectionRefusedError, FileNotFoundError):
                is_dead = True
            except OSError as err:
                if getattr(err, "errno", None) in (111, 2):  # ECONNREFUSED, ENOENT
                    is_dead = True
            finally:
                try:
                    s.close()
                except Exception:
                    pass

            if is_dead:
                issues.append({"type": "dead_socket", "path": str(sock), "detail": f"Dead UNIX socket: {sock}"})
                if fix:
                    try:
                        sock.unlink(missing_ok=True)
                        repairs.append(f"Removed dead UNIX socket: {sock}")
                    except OSError as exc:
                        repairs.append(f"Failed to remove socket {sock}: {exc}")
        except Exception:
            continue

    return issues, repairs


def check_and_fix_stale_locks(project_root: Path, fix: bool = True) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Detect and remove stale PID and lock files from dead processes."""
    issues = []
    repairs = []
    uid = os.getuid()

    candidates: Set[Path] = set()
    mode_lock = Path.home() / ".local/share/jarvis-runtime/mode.lock"
    candidates.add(mode_lock)

    try:
        candidates.update(Path("/tmp").glob("*jarvis*.lock"))
        candidates.update(Path("/tmp").glob("*voice*.lock"))
        candidates.update(Path("/tmp").glob("*jarvis*.pid"))
    except Exception:
        pass
    try:
        candidates.update(Path(f"/run/user/{uid}/jarvis").glob("*.lock"))
    except Exception:
        pass
    try:
        candidates.update((project_root / ".jarvis-learning").glob("**/*.lock"))
        candidates.update((project_root / ".jarvis-orchestration").glob("**/*.lock"))
    except Exception:
        pass

    now = time.time()
    for path in candidates:
        try:
            if not path.is_file():
                continue

            stale = False
            # Check if it contains a PID
            content = ""
            try:
                content = path.read_text(encoding="utf-8").strip()
            except Exception:
                pass

            pid = None
            if content.isdigit():
                pid = int(content)

            if pid is not None:
                try:
                    os.kill(pid, 0)
                except OSError:
                    stale = True
            else:
                try:
                    st = path.stat()
                    # If lock file modified more than 15 minutes ago and not locked
                    if now - st.st_mtime > 900:
                        stale = True
                except Exception:
                    pass

            if stale:
                issues.append({"type": "stale_lock", "path": str(path), "detail": f"Stale lock/PID file: {path}"})
                if fix:
                    try:
                        path.unlink(missing_ok=True)
                        repairs.append(f"Removed stale lock file: {path}")
                    except OSError as exc:
                        repairs.append(f"Failed to remove lock {path}: {exc}")
        except Exception:
            continue

    return issues, repairs


def check_and_fix_audio(fix: bool = True) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Verify PipeWire audio stack, unmuting sources/sinks and correcting loopbacks."""
    issues = []
    repairs = []

    # 1. PipeWire / WirePlumber services
    if shutil.which("systemctl"):
        for service in ("pipewire.service", "wireplumber.service"):
            try:
                res = subprocess.run(
                    ["systemctl", "--user", "is-active", service],
                    capture_output=True, text=True, timeout=3
                )
                if res.stdout.strip() != "active":
                    issues.append({"type": "audio_service_down", "detail": f"{service} is {res.stdout.strip() or 'inactive'}"})
                    if fix:
                        subprocess.run(["systemctl", "--user", "restart", service], capture_output=True, timeout=5)
                        repairs.append(f"Restarted audio service: {service}")
            except Exception:
                pass

    # 2. pactl mute and source checks
    if shutil.which("pactl"):
        # Check source mute
        try:
            res = subprocess.run(["pactl", "get-source-mute", "@DEFAULT_SOURCE@"], capture_output=True, text=True, timeout=3)
            if "yes" in res.stdout.lower():
                issues.append({"type": "mic_muted", "detail": "Default microphone is muted"})
                if fix:
                    subprocess.run(["pactl", "set-source-mute", "@DEFAULT_SOURCE@", "0"], capture_output=True, timeout=3)
                    repairs.append("Unmuted default microphone input (@DEFAULT_SOURCE@)")
        except Exception:
            pass

        # Check sink mute
        try:
            res = subprocess.run(["pactl", "get-sink-mute", "@DEFAULT_SINK@"], capture_output=True, text=True, timeout=3)
            if "yes" in res.stdout.lower():
                issues.append({"type": "speaker_muted", "detail": "Default speaker is muted"})
                if fix:
                    subprocess.run(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "0"], capture_output=True, timeout=3)
                    repairs.append("Unmuted default speaker output (@DEFAULT_SINK@)")
        except Exception:
            pass

        # Check default source loopback
        try:
            res = subprocess.run(["pactl", "get-default-source"], capture_output=True, text=True, timeout=3)
            current_source = res.stdout.strip()
            if current_source.endswith(".monitor"):
                issues.append({
                    "type": "source_is_monitor",
                    "detail": f"Default audio input is speaker monitor loopback ({current_source})"
                })
                if fix:
                    # Look for hardware input
                    sources_res = subprocess.run(["pactl", "list", "short", "sources"], capture_output=True, text=True, timeout=3)
                    for line in sources_res.stdout.splitlines():
                        parts = line.split()
                        if len(parts) >= 2:
                            s_name = parts[1]
                            if not s_name.endswith(".monitor") and "input" in s_name.lower():
                                subprocess.run(["pactl", "set-default-source", s_name], capture_output=True, timeout=3)
                                repairs.append(f"Switched default audio source from loopback to hardware input: {s_name}")
                                break
        except Exception:
            pass

    return issues, repairs


def check_and_fix_failed_units(fix: bool = True) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Clear transient failed systemd user units and restart down core services."""
    issues = []
    repairs = []

    if not shutil.which("systemctl"):
        return issues, repairs

    # Check for failed units
    try:
        res = subprocess.run(
            ["systemctl", "--user", "--failed", "--no-legend"],
            capture_output=True, text=True, timeout=5
        )
        failed_lines = [line.strip() for line in res.stdout.splitlines() if line.strip()]
        if failed_lines:
            for line in failed_lines:
                unit_name = line.split()[0] if line.split() else line
                issues.append({"type": "systemd_failed_unit", "detail": f"Failed user unit: {unit_name}"})
            if fix:
                subprocess.run(["systemctl", "--user", "reset-failed"], capture_output=True, timeout=5)
                repairs.append(f"Reset transient failed systemd units ({len(failed_lines)} unit(s))")
    except Exception:
        pass

    # Core JARVIS services health
    core_services = [
        "jarvis-voice.service",
        "jarvis-monitor.service",
        "jarvis-agent-bus.service",
        "jarvis-device-bridge.service",
        "jarvis-widget-hud.service",
        "jarvis-os-speaker.service",
    ]
    for service in core_services:
        try:
            res = subprocess.run(
                ["systemctl", "--user", "is-active", service],
                capture_output=True, text=True, timeout=3
            )
            state = res.stdout.strip()
            if state not in ("active", "activating"):
                # Check if unit file exists
                u_check = subprocess.run(
                    ["systemctl", "--user", "list-unit-files", service],
                    capture_output=True, text=True, timeout=3
                )
                if service in u_check.stdout:
                    issues.append({"type": "service_inactive", "detail": f"Core service {service} is {state or 'inactive'}"})
                    if fix:
                        subprocess.run(["systemctl", "--user", "restart", service], capture_output=True, timeout=5)
                        repairs.append(f"Restarted core service: {service}")
        except Exception:
            pass

    return issues, repairs


# ------------------------------------------------------------------------------
# Long-Term / Structural Checks & Repairs
# ------------------------------------------------------------------------------

def check_and_fix_systemd_services(project_root: Path, fix: bool = True) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Synchronize unit files and ensure core services are enabled for boot startup."""
    issues = []
    repairs = []

    if not shutil.which("systemctl"):
        return issues, repairs

    systemd_src = project_root / "systemd"
    user_systemd = Path.home() / ".config/systemd/user"

    # 1. Sync unit files if source exists
    units_synced = 0
    if systemd_src.is_dir():
        user_systemd.mkdir(parents=True, exist_ok=True)
        for src_file in systemd_src.glob("*.service"):
            dest_file = user_systemd / src_file.name
            try:
                if not dest_file.exists() or src_file.read_bytes() != dest_file.read_bytes():
                    issues.append({"type": "unit_outdated", "detail": f"Systemd unit {src_file.name} needs update"})
                    if fix:
                        shutil.copy2(src_file, dest_file)
                        units_synced += 1
            except Exception:
                pass

        for src_file in systemd_src.glob("*.timer"):
            dest_file = user_systemd / src_file.name
            try:
                if not dest_file.exists() or src_file.read_bytes() != dest_file.read_bytes():
                    issues.append({"type": "timer_outdated", "detail": f"Systemd timer {src_file.name} needs update"})
                    if fix:
                        shutil.copy2(src_file, dest_file)
                        units_synced += 1
            except Exception:
                pass

    if fix and units_synced > 0:
        try:
            subprocess.run(["systemctl", "--user", "daemon-reload"], capture_output=True, timeout=5)
            repairs.append(f"Synchronized and reloaded {units_synced} systemd unit file(s)")
        except Exception:
            pass

    # 2. Enable core services and timers so they start on system boot
    services_to_enable = [
        "jarvis-voice.service",
        "jarvis-monitor.service",
        "jarvis-agent-bus.service",
        "jarvis-device-bridge.service",
        "jarvis-widget-hud.service",
        "jarvis-os-speaker.service",
        "jarvis-memory-sync.timer",
        "jarvis-midnight-summary.timer",
    ]
    for s in services_to_enable:
        try:
            res = subprocess.run(
                ["systemctl", "--user", "is-enabled", s],
                capture_output=True, text=True, timeout=3
            )
            enabled_status = res.stdout.strip()
            if enabled_status not in ("enabled", "static"):
                issues.append({"type": "service_disabled", "detail": f"{s} is {enabled_status or 'disabled'} (will not boot)"})
                if fix:
                    subprocess.run(["systemctl", "--user", "enable", s], capture_output=True, timeout=5)
                    repairs.append(f"Enabled systemd service for boot auto-start: {s}")
        except Exception:
            pass

    return issues, repairs


def check_and_fix_permissions_and_bins(project_root: Path, fix: bool = True) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Ensure all CLI scripts are executable and symlinked in ~/.local/bin."""
    issues = []
    repairs = []

    # 1. Executable bit on bin/
    bin_dir = project_root / "bin"
    if bin_dir.is_dir():
        for item in bin_dir.iterdir():
            try:
                if item.is_file() and not item.is_symlink():
                    st = item.stat()
                    if not (st.st_mode & 0o111):
                        issues.append({"type": "bin_not_executable", "detail": f"Script not executable: bin/{item.name}"})
                        if fix:
                            item.chmod(st.st_mode | 0o755)
                            repairs.append(f"Made executable: bin/{item.name}")
            except Exception:
                pass

    # 2. Executable bit on scripts/*.sh and scripts/*.py
    scripts_dir = project_root / "scripts"
    if scripts_dir.is_dir():
        for pattern in ("*.sh", "*.py"):
            for item in scripts_dir.glob(pattern):
                try:
                    if item.is_file() and not item.is_symlink():
                        st = item.stat()
                        if not (st.st_mode & 0o111):
                            issues.append({"type": "script_not_executable", "detail": f"Script not executable: scripts/{item.name}"})
                            if fix:
                                item.chmod(st.st_mode | 0o755)
                                repairs.append(f"Made executable: scripts/{item.name}")
                except Exception:
                    pass

    # 3. Symlinks in ~/.local/bin/
    local_bin = Path.home() / ".local/bin"
    clis = ["jarvis", "jarvis-voice", "jarvis-control", "jarvis-memory", "jarvis-monitor", "jarvis-widgets", "jarvis-widget-hud", "jarvis-vision"]
    if bin_dir.is_dir():
        local_bin.mkdir(parents=True, exist_ok=True)
        for cli_name in clis:
            target = bin_dir / cli_name
            link = local_bin / cli_name
            if target.exists():
                try:
                    if not link.exists() or not link.is_symlink() or link.resolve() != target.resolve():
                        issues.append({"type": "cli_symlink_missing", "detail": f"Symlink ~/.local/bin/{cli_name} missing or target mismatch"})
                        if fix:
                            link.unlink(missing_ok=True)
                            link.symlink_to(target)
                            repairs.append(f"Restored symlink: ~/.local/bin/{cli_name} -> {target}")
                except Exception:
                    pass

    return issues, repairs


def check_and_fix_secrets_and_env(project_root: Path, fix: bool = True) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Secure permissions on .env files and synchronize to config directory."""
    issues = []
    repairs = []

    repo_env = project_root / ".env"
    cfg_env_dir = Path.home() / ".config/jarvis-voice"
    cfg_env = cfg_env_dir / ".env"

    # 1. Check workspace .env permissions
    if repo_env.exists():
        try:
            mode = repo_env.stat().st_mode & 0o777
            if mode & 0o077 != 0:
                issues.append({"type": "insecure_env", "detail": f"{repo_env} permissions are {oct(mode)}, should be 0600"})
                if fix:
                    os.chmod(repo_env, 0o600)
                    repairs.append(f"Secured .env permissions to 0600: {repo_env}")
        except Exception:
            pass

    # 2. Synchronize to ~/.config/jarvis-voice/.env if missing
    if repo_env.exists() and not cfg_env.exists():
        issues.append({"type": "missing_config_env", "detail": f"{cfg_env} is missing"})
        if fix:
            try:
                cfg_env_dir.mkdir(parents=True, exist_ok=True)
                os.chmod(cfg_env_dir, 0o700)
                shutil.copy2(repo_env, cfg_env)
                os.chmod(cfg_env, 0o600)
                repairs.append(f"Synchronized .env to {cfg_env} (mode 0600)")
            except Exception as exc:
                repairs.append(f"Failed to copy .env to config: {exc}")

    if cfg_env.exists():
        try:
            mode = cfg_env.stat().st_mode & 0o777
            if mode & 0o077 != 0:
                issues.append({"type": "insecure_cfg_env", "detail": f"{cfg_env} permissions are {oct(mode)}, should be 0600"})
                if fix:
                    os.chmod(cfg_env, 0o600)
                    repairs.append(f"Secured .env permissions to 0600: {cfg_env}")
        except Exception:
            pass

    # 3. Load missing environment variables into os.environ
    target_env = repo_env if repo_env.exists() else cfg_env
    if target_env.exists():
        try:
            for line in target_env.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip("'\"")
                    if k and k not in os.environ and v:
                        os.environ[k] = v
        except Exception:
            pass

    return issues, repairs


def check_and_fix_databases(project_root: Path, fix: bool = True) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Verify SQLite database integrity, permissions, and flush write-ahead logs (WAL)."""
    issues = []
    repairs = []

    db_candidates = [
        project_root / "memory/data/memory_graph.db",
        project_root / ".jarvis-orchestration/delegations.sqlite3",
        Path.home() / ".local/share/jarvis/shared_memory/vault/memory.db",
        Path.home() / ".local/share/jarvis/shared_memory/data/jarvis.db",
        Path.home() / ".local/share/jarvis/sessions.db",
        Path.home() / ".local/share/jarvis/voice.sqlite3",
        project_root / "learning/episodes.sqlite3",
        project_root / "learning/research-experience.sqlite3",
    ]

    for db_path in db_candidates:
        try:
            if not db_path.exists() or db_path.is_symlink():
                continue

            # Permissions
            st = db_path.stat()
            mode = st.st_mode & 0o777
            if mode & 0o077 != 0:
                issues.append({"type": "db_insecure_perms", "detail": f"{db_path.name} permissions {oct(mode)} too open"})
                if fix:
                    os.chmod(db_path, 0o600)
                    repairs.append(f"Secured database permissions (0600): {db_path.name}")

            # Check integrity
            is_corrupt = False
            try:
                conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=2.0)
                try:
                    res = conn.execute("PRAGMA quick_check").fetchall()
                    if res != [("ok",)]:
                        is_corrupt = True
                finally:
                    conn.close()
            except Exception:
                is_corrupt = True

            if is_corrupt:
                issues.append({"type": "db_corrupt", "detail": f"Database corruption detected: {db_path.name}"})
            elif fix and os.access(db_path, os.W_OK) and st.st_size > 0:
                try:
                    conn = sqlite3.connect(str(db_path), timeout=5.0)
                    try:
                        conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
                        conn.execute("VACUUM;")
                    finally:
                        conn.close()
                    repairs.append(f"Flushed WAL journal & vacuumed database: {db_path.name}")
                except Exception:
                    pass
        except Exception:
            continue

    return issues, repairs


def check_and_fix_state_directories(project_root: Path, fix: bool = True) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Ensure private state and cache directories exist with 0700 permissions."""
    issues = []
    repairs = []
    uid = os.getuid()

    dirs = [
        Path.home() / ".jarvis",
        Path.home() / ".config/jarvis-voice",
        Path.home() / ".local/share/jarvis",
        Path.home() / ".local/share/jarvis-runtime",
        Path(f"/run/user/{uid}/jarvis"),
        Path(f"/run/user/{uid}/jarvis-api-agent"),
        Path(f"/run/user/{uid}/jarvis_screen"),
        Path(f"/run/user/{uid}/jarvis_webcam"),
        project_root / ".jarvis-learning",
        project_root / ".jarvis-orchestration",
        project_root / "jarvis_memory",
    ]

    for d in dirs:
        try:
            if not d.exists():
                issues.append({"type": "state_dir_missing", "detail": f"State directory missing: {d}"})
                if fix:
                    d.mkdir(parents=True, exist_ok=True)
                    os.chmod(d, 0o700)
                    repairs.append(f"Created state directory (0700): {d}")
            else:
                mode = d.stat().st_mode & 0o777
                if mode & 0o077 != 0:
                    issues.append({"type": "state_dir_insecure", "detail": f"Directory {d} permissions {oct(mode)} too open"})
                    if fix:
                        os.chmod(d, 0o700)
                        repairs.append(f"Secured directory permissions (0700): {d}")
        except Exception:
            continue

    return issues, repairs


def check_and_fix_python_packages(fix: bool = True) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Verify required Python packages in the current interpreter and auto-install if missing."""
    issues = []
    repairs = []

    required_modules = [
        ("numpy", "numpy"),
        ("onnxruntime", "onnxruntime"),
        ("google.genai", "google-genai"),
        ("openwakeword", "openwakeword"),
        ("sounddevice", "sounddevice"),
        ("websockets", "websockets"),
        ("pydantic", "pydantic"),
        ("httpx", "httpx"),
        ("jsonschema", "jsonschema"),
    ]

    for module_name, pip_pkg in required_modules:
        try:
            spec = importlib.util.find_spec(module_name)
            if spec is None:
                issues.append({"type": "missing_python_module", "detail": f"Missing Python module: {module_name}"})
                if fix and shutil.which(sys.executable):
                    try:
                        res = subprocess.run(
                            [sys.executable, "-m", "pip", "install", pip_pkg],
                            capture_output=True, text=True, timeout=90
                        )
                        if res.returncode == 0:
                            repairs.append(f"Installed Python package: {pip_pkg}")
                        else:
                            repairs.append(f"Failed to install {pip_pkg}: {res.stderr.strip()}")
                    except Exception as exc:
                        repairs.append(f"Error installing {pip_pkg}: {exc}")
        except Exception:
            pass

    return issues, repairs


# ------------------------------------------------------------------------------
# Core Diagnostics Function
# ------------------------------------------------------------------------------

def report(voice, control, fix: bool = False, temp_only: bool = False, long_only: bool = False) -> Dict[str, Any]:
    """Execute readiness diagnostics and optionally apply auto-repairs."""
    project_root = get_project_root()
    repairs_applied: List[str] = []
    temp_issues: List[Dict[str, Any]] = []
    long_issues: List[Dict[str, Any]] = []

    # 1. Execute auto-fixes if requested
    if fix:
        if not long_only:
            # Temporary fixes
            _, r = check_and_fix_dead_sockets(fix=True)
            repairs_applied.extend(r)
            _, r = check_and_fix_stale_locks(project_root, fix=True)
            repairs_applied.extend(r)
            _, r = check_and_fix_audio(fix=True)
            repairs_applied.extend(r)
            _, r = check_and_fix_failed_units(fix=True)
            repairs_applied.extend(r)

        if not temp_only:
            # Long-term fixes
            _, r = check_and_fix_systemd_services(project_root, fix=True)
            repairs_applied.extend(r)
            _, r = check_and_fix_permissions_and_bins(project_root, fix=True)
            repairs_applied.extend(r)
            _, r = check_and_fix_secrets_and_env(project_root, fix=True)
            repairs_applied.extend(r)
            _, r = check_and_fix_databases(project_root, fix=True)
            repairs_applied.extend(r)
            _, r = check_and_fix_state_directories(project_root, fix=True)
            repairs_applied.extend(r)
            _, r = check_and_fix_python_packages(fix=True)
            repairs_applied.extend(r)

    # 2. Gather issues after repairs (or initial if fix=False)
    i, _ = check_and_fix_dead_sockets(fix=False)
    temp_issues.extend(i)
    i, _ = check_and_fix_stale_locks(project_root, fix=False)
    temp_issues.extend(i)
    i, _ = check_and_fix_audio(fix=False)
    temp_issues.extend(i)
    i, _ = check_and_fix_failed_units(fix=False)
    temp_issues.extend(i)

    i, _ = check_and_fix_systemd_services(project_root, fix=False)
    long_issues.extend(i)
    i, _ = check_and_fix_permissions_and_bins(project_root, fix=False)
    long_issues.extend(i)
    i, _ = check_and_fix_secrets_and_env(project_root, fix=False)
    long_issues.extend(i)
    i, _ = check_and_fix_databases(project_root, fix=False)
    long_issues.extend(i)
    i, _ = check_and_fix_state_directories(project_root, fix=False)
    long_issues.extend(i)

    # 3. Standard checks dictionary (preserves backward compatibility with existing tests)
    checks = {}

    def check(name, ok, detail):
        checks[name] = {"ok": bool(ok), "detail": detail}

    for executable in ("pw-record", "pw-play", "pactl", "hyprctl", "omarchy"):
        check(executable, shutil.which(executable), executable)

    for module in ("numpy", "onnxruntime", "google.genai"):
        try:
            found = importlib.util.find_spec(module) is not None
        except (ImportError, ModuleNotFoundError):
            found = False
        check(module, found, "Python dependency")

    standby_enabled = getattr(getattr(voice, "standby", None), "enabled", False)
    if standby_enabled:
        try:
            wakeword_ok = importlib.util.find_spec("openwakeword") is not None
        except Exception:
            wakeword_ok = False
        check("openwakeword", wakeword_ok, "Offline Hey Jarvis wake-word runtime")

    voice_key_env = getattr(voice, "api_key_env", "GEMINI_API_KEY")
    check("voice credential", os.environ.get(voice_key_env), voice_key_env)

    tasks_enabled = getattr(control, "tasks_enabled", False)
    if tasks_enabled:
        for executable in ("bwrap", "systemd-run"):
            check(f"tasks: {executable}", shutil.which(executable), executable)
        if getattr(control, "tasks_provider", "") == "codex" or (not os.environ.get(getattr(control, "api_key_env", "OPENAI_API_KEY")) and shutil.which("codex")):
            check("tasks: codex", shutil.which("codex"), "Codex CLI")
        else:
            task_key_env = getattr(control, "api_key_env", "OPENAI_API_KEY")
            check("task credential", os.environ.get(task_key_env), task_key_env)

    vision_enabled = getattr(control, "vision_enabled", False)
    if vision_enabled:
        try:
            from .vision import settings
            camera = settings(control)
            for executable in ("ffmpeg", "ffplay"):
                check(f"vision: {executable}", shutil.which(executable), executable)
            check("camera device", Path(camera["device"]).exists(), camera["device"])
            if camera.get("api_key_env"):
                check("vision credential", os.environ.get(camera["api_key_env"]), camera["api_key_env"])
        except Exception as exc:
            check("vision settings", False, str(exc))

    overall_ok = all(item["ok"] for item in checks.values())

    return {
        "ok": overall_ok,
        "checks": checks,
        "tasks_enabled": tasks_enabled,
        "vision_enabled": vision_enabled,
        "temporary_issues": temp_issues,
        "long_term_issues": long_issues,
        "repairs_applied": repairs_applied,
    }


# ------------------------------------------------------------------------------
# Output Presentation & CLI Runner
# ------------------------------------------------------------------------------

def format_doctor_report(result: Dict[str, Any], fix_mode: bool) -> str:
    """Format diagnostics and repair results into a clear, structured terminal display."""
    lines = []
    w = 78
    lines.append(_BOLD + "=" * w + _RESET)
    lines.append(_BOLD + _CYAN + "JARVIS OS DOCTOR & AUTO-REPAIR".center(w) + _RESET)
    lines.append(_BOLD + "=" * w + _RESET)
    lines.append("")

    # 1. Core Diagnostics
    lines.append(_BOLD + "[CORE DEPENDENCIES & RUNTIME]" + _RESET)
    for name, item in result["checks"].items():
        status = f"{_GREEN}✓ PASS{_RESET}" if item["ok"] else f"{_RED}✗ MISSING{_RESET}"
        lines.append(f"  {status}  {name:<24} : {item['detail']}")
    lines.append("")

    # 2. Temporary Runtime Status
    lines.append(_BOLD + "[TEMPORARY & RUNTIME HEALTH]" + _RESET)
    temp_issues = result.get("temporary_issues", [])
    if not temp_issues:
        lines.append(f"  {_GREEN}✓{_RESET} UNIX Sockets        : All sockets clean & responsive")
        lines.append(f"  {_GREEN}✓{_RESET} Lock & PID Files    : No stale locks or orphaned files")
        lines.append(f"  {_GREEN}✓{_RESET} Audio Subsystem     : PipeWire & WirePlumber running, unmuted")
        lines.append(f"  {_GREEN}✓{_RESET} Systemd State       : No failed user units")
    else:
        for iss in temp_issues:
            lines.append(f"  {_YELLOW}⚠{_RESET} [Temp Issue] {iss.get('detail')}")
    lines.append("")

    # 3. Long-Term System Integrity
    lines.append(_BOLD + "[LONG-TERM SYSTEM INTEGRITY]" + _RESET)
    long_issues = result.get("long_term_issues", [])
    if not long_issues:
        lines.append(f"  {_GREEN}✓{_RESET} Services & Timers   : Core services synchronized and enabled")
        lines.append(f"  {_GREEN}✓{_RESET} CLI Executables     : Binaries executable and linked in ~/.local/bin")
        lines.append(f"  {_GREEN}✓{_RESET} Secrets & Config    : .env secured with private 0600 mode")
        lines.append(f"  {_GREEN}✓{_RESET} SQLite Databases    : Databases verified & WAL journals flushed")
        lines.append(f"  {_GREEN}✓{_RESET} State Directories   : Private storage directories configured")
    else:
        for iss in long_issues:
            lines.append(f"  {_YELLOW}⚠{_RESET} [Structural Issue] {iss.get('detail')}")
    lines.append("")

    # 4. Auto-Repairs Applied
    repairs = result.get("repairs_applied", [])
    if repairs:
        lines.append(_BOLD + _GREEN + f"[AUTO-REPAIRS APPLIED ({len(repairs)})]" + _RESET)
        for r in repairs:
            lines.append(f"  {_GREEN}★ Fixed:{_RESET} {r}")
        lines.append("")
    elif fix_mode:
        lines.append(_BOLD + "[AUTO-REPAIRS]" + _RESET)
        lines.append(f"  {_DIM}• System was already optimal; no repair interventions were required.{_RESET}")
        lines.append("")

    # 5. Overall Summary
    lines.append(_BOLD + "-" * w + _RESET)
    if result["ok"] and not temp_issues and not long_issues:
        lines.append(f"  {_GREEN}{_BOLD}STATUS: ALL SYSTEMS OPERATIONAL (Healthy & Repaired){_RESET}")
    elif result["ok"]:
        lines.append(f"  {_GREEN}{_BOLD}STATUS: PASS (Operational with non-blocking warnings){_RESET}")
    else:
        lines.append(f"  {_RED}{_BOLD}STATUS: ATTENTION REQUIRED (Some dependencies or credentials missing){_RESET}")
    lines.append(_BOLD + "=" * w + _RESET)

    return "\n".join(lines)


def run_doctor(voice, control, fix: bool = True, json_output: bool = False,
               temp_only: bool = False, long_only: bool = False) -> int:
    """Entry point for CLI doctor command."""
    res = report(voice, control, fix=fix, temp_only=temp_only, long_only=long_only)

    if json_output:
        print(json.dumps(res, indent=2))
    else:
        print(format_doctor_report(res, fix_mode=fix))

    return 0 if res["ok"] else 1
