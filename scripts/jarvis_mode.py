#!/usr/bin/env python3
"""Switch the live JARVIS service between production (main) and test (dev) worktrees."""
from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any

log = logging.getLogger("jarvis_mode")

PRODUCTION_ROOT = Path.home() / "Projects" / "JARVIS-OMA"
TEST_ROOT = Path.home() / "Projects" / "JARVIS-OMA-dev"
DROPIN_DIR = Path.home() / ".config" / "systemd" / "user" / "jarvis-oma.service.d"
DROPIN = DROPIN_DIR / "mode.conf"

MODES = {
    "production": ("main", PRODUCTION_ROOT),
    "test": ("dev", TEST_ROOT),
}


def _git(root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        check=check,
        capture_output=True,
        text=True,
    )


def _branch(root: Path) -> str:
    try:
        result = _git(root, "branch", "--show-current", check=False)
        return result.stdout.strip()
    except Exception:
        return ""


def ensure_test_worktree() -> Path:
    """Create the dev branch and detached test worktree at TEST_ROOT if not present."""
    if not (PRODUCTION_ROOT / ".git").exists():
        raise RuntimeError(f"Production repository not found at {PRODUCTION_ROOT}")

    # Ensure local dev branch exists in the repository
    branches = _git(PRODUCTION_ROOT, "branch", "--list", "dev", check=False).stdout.strip()
    if not branches:
        _git(PRODUCTION_ROOT, "branch", "dev", "main")

    if TEST_ROOT.exists():
        branch = _branch(TEST_ROOT)
        if branch and branch != "dev":
            raise RuntimeError(f"{TEST_ROOT} exists but is on branch '{branch}', expected 'dev'")
        return TEST_ROOT

    # Add worktree for dev branch
    _git(PRODUCTION_ROOT, "worktree", "add", str(TEST_ROOT), "dev")

    # Share configuration and credentials safely
    for name in (".env", "config.toml"):
        source = PRODUCTION_ROOT / name
        target = TEST_ROOT / name
        if source.exists() and not target.exists():
            target.write_bytes(source.read_bytes())
            target.chmod(0o600)

    # Share virtual environment via symlink
    source_venv = PRODUCTION_ROOT / ".venv"
    target_venv = TEST_ROOT / ".venv"
    if source_venv.exists() and not target_venv.exists():
        target_venv.symlink_to(source_venv)

    return TEST_ROOT


def sync_branch(root: Path, branch: str) -> dict[str, Any]:
    """Fetch and fast-forward the given branch in its worktree."""
    if not (root / ".git").exists() and not (root / ".git").is_file():
        return {"status": "skipped", "message": f"Not a git worktree: {root}"}

    fetch_res = _git(root, "fetch", "origin", branch, check=False)
    if fetch_res.returncode == 0:
        pull_res = _git(root, "merge", "--ff-only", f"origin/{branch}", check=False)
        if pull_res.returncode == 0:
            return {"status": "synced", "branch": branch, "output": pull_res.stdout.strip()}
    return {"status": "local_only", "branch": branch, "message": "Using local branch state"}


def current_mode() -> dict[str, Any]:
    """Inspect systemd drop-in and running process to determine active mode."""
    mode = "production"
    branch = "main"
    root = PRODUCTION_ROOT

    if DROPIN.exists():
        try:
            text = DROPIN.read_text(encoding="utf-8")
            if str(TEST_ROOT) in text:
                mode = "test"
                branch = "dev"
                root = TEST_ROOT
        except OSError:
            pass

    service_active = False
    pid = None
    try:
        proc = subprocess.run(
            ["systemctl", "--user", "is-active", "jarvis-oma.service"],
            capture_output=True,
            text=True,
            check=False,
        )
        service_active = (proc.stdout.strip() == "active")
        if service_active:
            pid_proc = subprocess.run(
                ["systemctl", "--user", "show", "jarvis-oma.service", "--property=MainPID"],
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
        "mode": mode,
        "branch": branch,
        "root": str(root),
        "service_active": service_active,
        "pid": pid,
    }


def restart_service() -> bool:
    """Execute systemctl daemon-reload and restart for jarvis-oma.service."""
    try:
        subprocess.run(["systemctl", "--user", "daemon-reload"], check=True, capture_output=True)
        subprocess.run(["systemctl", "--user", "restart", "jarvis-oma.service"], check=True, capture_output=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError) as error:
        log.warning("Failed to restart jarvis-oma.service via systemctl: %s", error)
        return False


def switch_mode(mode: str, *, sync: bool = True, restart: bool = True) -> dict[str, Any]:
    """Switch JARVIS between production and test modes."""
    if mode == "status":
        return current_mode()
    if mode not in MODES:
        raise ValueError(f"Invalid mode '{mode}'. Must be 'production', 'test', or 'status'.")

    branch, root = MODES[mode]

    if mode == "test":
        ensure_test_worktree()
        if sync:
            sync_branch(TEST_ROOT, "dev")
        DROPIN_DIR.mkdir(parents=True, exist_ok=True)
        DROPIN.write_text(
            "[Service]\n"
            f"WorkingDirectory={TEST_ROOT}\n"
            f"ExecStart=\n"
            f"ExecStart={TEST_ROOT}/run.sh\n"
            f"EnvironmentFile=\n"
            f"EnvironmentFile=-{TEST_ROOT}/.env\n",
            encoding="utf-8",
        )
    else:  # production
        if sync and (PRODUCTION_ROOT / ".git").exists():
            if _branch(PRODUCTION_ROOT) == "main":
                sync_branch(PRODUCTION_ROOT, "main")
        if DROPIN.exists():
            try:
                DROPIN.unlink()
            except OSError:
                pass

    try:
        subprocess.run(["systemctl", "--user", "daemon-reload"], check=False, capture_output=True)
    except Exception:
        pass

    restarted = False
    if restart:
        restarted = restart_service()

    return {
        "status": "success",
        "mode": mode,
        "branch": branch,
        "root": str(root),
        "restarted": restarted,
    }


def promote_to_main() -> dict[str, Any]:
    """Verify dev branch and merge it into main, returning the new production status."""
    ensure_test_worktree()

    # 1. Verify voice core lock
    verify_script = TEST_ROOT / "scripts" / "verify_voice_lock.py"
    if verify_script.exists():
        proc = subprocess.run([sys.executable, str(verify_script)], cwd=str(TEST_ROOT),
                              capture_output=True, text=True)
        if proc.returncode != 0:
            raise RuntimeError(f"Voice core lock verification failed on dev: {proc.stderr}")

    # 2. Run test suite on dev worktree
    pytest_bin = TEST_ROOT / ".venv" / "bin" / "pytest"
    if pytest_bin.exists():
        proc = subprocess.run([str(pytest_bin), "-q"], cwd=str(TEST_ROOT),
                              capture_output=True, text=True)
        if proc.returncode != 0:
            raise RuntimeError(f"Dev test suite failed before promotion: {proc.stdout}\n{proc.stderr}")

    # 3. Merge dev into main on PRODUCTION_ROOT
    cur_branch = _branch(PRODUCTION_ROOT)
    if cur_branch != "main":
        _git(PRODUCTION_ROOT, "checkout", "main")
    merge_res = _git(PRODUCTION_ROOT, "merge", "--ff-only", "dev", check=False)
    if merge_res.returncode != 0:
        raise RuntimeError(f"Cannot fast-forward main to dev: {merge_res.stderr}")

    # 4. Switch mode to production
    return switch_mode("production", restart=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", nargs="?", choices=(*MODES, "status", "promote", "sync"), default="status")
    parser.add_argument("--no-restart", action="store_true", help="Do not restart systemd service")
    parser.add_argument("--no-sync", action="store_true", help="Do not sync git branch")
    args = parser.parse_args(argv)

    try:
        if args.mode == "promote":
            result = promote_to_main()
            print(f"JARVIS promoted to production: branch {result['branch']}, root {result['root']}")
            return 0
        elif args.mode == "sync":
            cur = current_mode()
            root = Path(cur["root"])
            res = sync_branch(root, cur["branch"])
            print(f"JARVIS sync ({cur['mode']}): {res.get('status')} - {res.get('message', res.get('output', ''))}")
            return 0
        else:
            result = switch_mode(args.mode, sync=not args.no_sync, restart=not args.no_restart)
    except (RuntimeError, ValueError, subprocess.CalledProcessError) as exc:
        sys.stderr.write(f"Error: {exc}\n")
        return 1

    if args.mode == "status":
        active_str = "running (PID {})".format(result['pid']) if result.get('service_active') and result.get('pid') else (
            "active" if result.get('service_active') else "inactive"
        )
        print(f"JARVIS mode: {result['mode']} (branch {result['branch']})\n  Root:    {result['root']}\n  Service: {active_str}")
    else:
        print(f"JARVIS switched to: {result['mode']} (branch {result['branch']}, {result['root']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
