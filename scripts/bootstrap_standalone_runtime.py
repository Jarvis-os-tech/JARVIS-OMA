#!/usr/bin/env python3
"""Bootstrap and decouple the standalone compiled JARVIS OS service."""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

# Add project root to sys.path
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from orchestration.release_manager import ReleaseManager, DEFAULT_REPO_URL, DEFAULT_BRANCH

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
log = logging.getLogger("jarvis.bootstrap")


def setup_standalone_venv(venv_dir: Path, source_venv: Path) -> None:
    """Create an isolated standalone virtual environment."""
    if (venv_dir / "bin" / "python").is_file():
        log.info("Standalone venv already exists at %s", venv_dir)
        return

    log.info("Creating isolated virtualenv at %s...", venv_dir)
    venv_dir.parent.mkdir(parents=True, exist_ok=True)

    # Use the same python interpreter
    python_bin = sys.executable
    subprocess.run([python_bin, "-m", "venv", str(venv_dir)], check=True)

    # Copy installed site-packages from the dev venv to guarantee identical packages
    source_site = list(source_venv.glob("lib/python3.*/site-packages"))
    target_site = list(venv_dir.glob("lib/python3.*/site-packages"))

    if source_site and target_site:
        src = source_site[0]
        dst = target_site[0]
        log.info("Copying site-packages from %s to %s...", src, dst)
        subprocess.run(["cp", "-a", "--reflink=auto", f"{src}/.", str(dst)], check=True)

    log.info("Standalone virtualenv setup complete.")


def seed_sync_git(sync_git_dir: Path, repo_url: str, branch: str) -> None:
    """Seed the bare git mirror cache."""
    if sync_git_dir.is_dir():
        log.info("Fetching latest commits into %s...", sync_git_dir)
        subprocess.run(
            ["git", "--git-dir", str(sync_git_dir), "fetch", "origin", f"{branch}:{branch}"],
            check=False,
            timeout=60,
        )
        return

    log.info("Seeding bare git cache at %s...", sync_git_dir)
    sync_git_dir.parent.mkdir(parents=True, exist_ok=True)
    # Clone bare from current repo first for speed, then set origin to GitHub
    subprocess.run(["git", "clone", "--bare", str(REPO_ROOT), str(sync_git_dir)], check=True)
    subprocess.run(["git", "--git-dir", str(sync_git_dir), "remote", "set-url", "origin", repo_url], check=True)
    subprocess.run(["git", "--git-dir", str(sync_git_dir), "fetch", "origin", f"{branch}:{branch}"], check=False)


def main() -> int:
    home = Path.home()
    runtime_root = Path(os.environ.get("XDG_DATA_HOME", home / ".local/share")) / "jarvis-runtime"
    source_venv = REPO_ROOT / ".venv"
    if not source_venv.exists():
        source_venv = home / "Projects/JARVIS-OMA/.venv"

    log.info("Initializing standalone runtime at %s...", runtime_root)
    rm = ReleaseManager(root_dir=runtime_root)
    rm.init_directories()

    # 1. Setup isolated standalone venv
    setup_standalone_venv(rm.venv_dir, source_venv)

    # 2. Seed git mirror cache
    seed_sync_git(rm.sync_git_dir, DEFAULT_REPO_URL, DEFAULT_BRANCH)

    # 3. Build release from HEAD
    head_sha = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True
    ).strip()
    log.info("Building compiled release for commit %s...", head_sha[:7])
    release_dir = rm.build_release(head_sha)
    log.info("Release built at %s", release_dir)

    # 4. Activate release
    log.info("Activating release %s...", release_dir.name)
    # We do manual activation before restarting services so symlinks exist
    temp_curr = rm.root_dir / "current.tmp"
    if temp_curr.exists() or temp_curr.is_symlink():
        temp_curr.unlink()
    temp_curr.symlink_to(release_dir)
    temp_curr.rename(rm.current_link)

    # 5. Break dangerous old symlink ~/.local/share/jarvis-voice -> /home/g0pi/JARVIS OS
    voice_share = home / ".local/share/jarvis-voice"
    if voice_share.is_symlink() or voice_share.exists():
        log.info("Updating %s -> %s...", voice_share, rm.current_link)
        if voice_share.is_symlink():
            voice_share.unlink()
        elif voice_share.is_dir():
            shutil.rmtree(voice_share)
        voice_share.symlink_to(rm.current_link)

    # 6. Update user systemd service files
    service_dir = home / ".config/systemd/user"
    service_dir.mkdir(parents=True, exist_ok=True)
    for service_name in ("jarvis-voice.service", "jarvis-device-bridge.service"):
        src = REPO_ROOT / "systemd" / service_name
        dst = service_dir / service_name
        if src.is_file():
            log.info("Installing %s to %s...", src.name, dst)
            shutil.copy2(src, dst)

    # 7. Update ~/.local/bin/jarvis* symlinks to point to runtime current
    bin_dir = home / ".local/bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    for cli in ("jarvis", "jarvis-voice", "jarvis-control", "jarvis-memory"):
        cli_target = rm.current_link / "bin" / cli
        cli_symlink = bin_dir / cli
        if cli_target.is_file():
            if cli_symlink.is_symlink() or cli_symlink.exists():
                cli_symlink.unlink()
            cli_symlink.symlink_to(cli_target)
            log.info("Linked %s -> %s", cli_symlink, cli_target)

    # 8. Reload systemd and restart services
    log.info("Reloading systemd user daemon and restarting JARVIS services...")
    subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
    subprocess.run(["systemctl", "--user", "restart", "jarvis-voice.service", "jarvis-device-bridge.service"], check=False)

    time.sleep(2.0)
    health = rm.verify_health(timeout=8.0)
    if health:
        log.info("SUCCESS: JARVIS Voice Core is active and decoupled from local source!")
    else:
        log.warning("WARNING: jarvis-voice.service not reporting active yet. Check journalctl --user -u jarvis-voice.")

    return 0 if health else 1


if __name__ == "__main__":
    sys.exit(main())
