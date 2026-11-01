"""Standalone Release Manager for JARVIS OS.

Manages clean GitHub upstream synchronization, bytecode compilation,
atomic symlink switching, health verification, and rollback.
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

log = logging.getLogger("jarvis.release_manager")

DEFAULT_REPO_URL = "https://github.com/Jarvis-os-tech/JARVIS-OMA.git"
DEFAULT_BRANCH = "JARVIS-OS"
DEFAULT_RUNTIME_ROOT = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / "jarvis-runtime"


class ReleaseManager:
    """Orchestrates compiled standalone releases for JARVIS OS."""

    def __init__(
        self,
        root_dir: Path | str | None = None,
        repo_url: str = DEFAULT_REPO_URL,
        branch: str = DEFAULT_BRANCH,
    ) -> None:
        self.root_dir = Path(root_dir) if root_dir else DEFAULT_RUNTIME_ROOT
        self.repo_url = repo_url
        self.branch = branch

        self.releases_dir = self.root_dir / "releases"
        self.current_link = self.root_dir / "current"
        self.previous_link = self.root_dir / "previous"
        self.sync_git_dir = self.root_dir / "sync.git"
        self.venv_dir = self.root_dir / "venv"
        self.data_dir = self.root_dir / "data"
        self.logs_dir = self.root_dir / "logs"

    def init_directories(self) -> None:
        """Ensure all required runtime directories exist."""
        for path in (self.releases_dir, self.data_dir, self.logs_dir):
            path.mkdir(parents=True, exist_ok=True)

    def get_current_release_metadata(self) -> dict[str, Any]:
        """Read release.json from the currently active release."""
        manifest = self.current_link / "release.json"
        if manifest.is_file():
            try:
                return json.loads(manifest.read_text(encoding="utf-8"))
            except Exception as e:
                log.warning("Failed to parse %s: %s", manifest, e)
        return {}

    def _query_remote_sha(self) -> str:
        """Query remote HEAD SHA for configured branch via git ls-remote."""
        cmd = ["git", "ls-remote", self.repo_url, f"refs/heads/{self.branch}"]
        res = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=15)
        output = res.stdout.strip()
        if not output:
            raise RuntimeError(f"No remote ref found for refs/heads/{self.branch} at {self.repo_url}")
        return output.split()[0]

    def _query_remote_commit_message(self, sha: str) -> str:
        """Get commit summary message from sync.git if available."""
        if self.sync_git_dir.is_dir():
            try:
                res = subprocess.run(
                    ["git", "--git-dir", str(self.sync_git_dir), "log", "-1", "--format=%s (%an)", sha],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if res.returncode == 0 and res.stdout.strip():
                    return res.stdout.strip()
            except Exception:
                pass
        return ""

    def check_remote_update(self) -> dict[str, Any]:
        """Check if a newer commit is available on GitHub."""
        current_meta = self.get_current_release_metadata()
        current_sha = current_meta.get("commit", "")

        try:
            remote_sha = self._query_remote_sha()
        except Exception as e:
            return {
                "has_update": False,
                "current_sha": current_sha,
                "remote_sha": "",
                "error": str(e),
                "message": f"Failed to check GitHub: {e}",
            }

        has_update = bool(remote_sha and remote_sha != current_sha)
        msg = ""
        if has_update:
            summary = self._query_remote_commit_message(remote_sha)
            msg = f"New version available: {remote_sha[:7]} - {summary}" if summary else f"New version available: {remote_sha[:7]}"
        else:
            msg = f"System is up-to-date on {current_sha[:7]}." if current_sha else "No active release found."

        return {
            "has_update": has_update,
            "current_sha": current_sha,
            "remote_sha": remote_sha,
            "message": msg,
        }

    def fetch_upstream(self) -> str:
        """Fetch upstream git tree into bare mirror sync.git and return commit SHA."""
        self.init_directories()
        if not self.sync_git_dir.is_dir():
            subprocess.run(
                ["git", "clone", "--bare", "--filter=blob:none", self.repo_url, str(self.sync_git_dir)],
                check=True,
                capture_output=True,
                text=True,
                timeout=120,
            )
        else:
            subprocess.run(
                ["git", "--git-dir", str(self.sync_git_dir), "fetch", "origin", f"{self.branch}:{self.branch}"],
                check=True,
                capture_output=True,
                text=True,
                timeout=60,
            )

        res = subprocess.run(
            ["git", "--git-dir", str(self.sync_git_dir), "rev-parse", self.branch],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return res.stdout.strip()

    def build_release(self, commit_sha: str) -> Path:
        """Export clean tree, compile to bytecode, and write release directory."""
        self.init_directories()
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        release_name = f"{timestamp}-{commit_sha[:7]}"
        staging_dir = self.root_dir / f"staging-{release_name}"
        final_dir = self.releases_dir / release_name

        if staging_dir.exists():
            shutil.rmtree(staging_dir)
        staging_dir.mkdir(parents=True)

        try:
            # 1. Export clean git tree
            archive_proc = subprocess.Popen(
                ["git", "--git-dir", str(self.sync_git_dir), "archive", commit_sha],
                stdout=subprocess.PIPE,
            )
            tar_proc = subprocess.Popen(
                ["tar", "-x", "-C", str(staging_dir)],
                stdin=archive_proc.stdout,
            )
            if archive_proc.stdout:
                archive_proc.stdout.close()
            tar_proc.communicate()
            if archive_proc.wait() != 0 or tar_proc.returncode != 0:
                raise RuntimeError("Failed to export clean git archive to staging")

            # 2. Compile to bytecode using runtime venv Python
            venv_python = self.venv_dir / "bin" / "python"
            python_bin = str(venv_python) if venv_python.is_file() else "python3"

            compile_cmd = [
                python_bin,
                "-m",
                "compileall",
                "-o",
                "1",
                "-q",
                "-d",
                str(self.current_link),
                str(staging_dir),
            ]
            subprocess.run(compile_cmd, check=True, capture_output=True, text=True, timeout=60)

            # 3. Retain read-only permissions on source files for stack trace debugging
            for py_file in staging_dir.rglob("*.py"):
                try:
                    py_file.chmod(0o444)
                except Exception:
                    pass

            # 4. Strip development/test artifacts not needed in operational runtime
            for clean_target in ("tests", ".pytest_cache", ".github"):
                target_path = staging_dir / clean_target
                if target_path.exists():
                    if target_path.is_dir():
                        shutil.rmtree(target_path)
                    else:
                        target_path.unlink()

            # 5. Write release metadata
            commit_msg = self._query_remote_commit_message(commit_sha)
            manifest = {
                "commit": commit_sha,
                "branch": self.branch,
                "created_at": time.time(),
                "created_at_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "message": commit_msg,
                "schema_version": 1,
            }
            (staging_dir / "release.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

            # 6. Ensure bin wrappers are executable
            bin_dir = staging_dir / "bin"
            if bin_dir.is_dir():
                for script in bin_dir.iterdir():
                    if script.is_file():
                        script.chmod(script.stat().st_mode | 0o111)

            # 7. Move staging to releases
            staging_dir.rename(final_dir)
            return final_dir

        except Exception:
            if staging_dir.exists():
                shutil.rmtree(staging_dir)
            raise

    def prune_releases(self, keep: int = 3) -> list[str]:
        """Prune older releases, keeping the most recent 'keep' count."""
        if not self.releases_dir.is_dir():
            return []

        # Collect releases with creation timestamps
        releases: list[tuple[float, Path]] = []
        for path in self.releases_dir.iterdir():
            if not path.is_dir():
                continue
            manifest = path / "release.json"
            created_at = path.stat().st_mtime
            if manifest.is_file():
                try:
                    data = json.loads(manifest.read_text(encoding="utf-8"))
                    created_at = float(data.get("created_at", created_at))
                except Exception:
                    pass
            releases.append((created_at, path))

        # Sort descending (newest first)
        releases.sort(key=lambda x: x[0], reverse=True)

        # Do not prune current or previous targets
        current_target = self.current_link.resolve() if self.current_link.exists() else None
        previous_target = self.previous_link.resolve() if self.previous_link.exists() else None

        pruned: list[str] = []
        to_keep = releases[:keep]
        to_delete = releases[keep:]

        for _, path in to_delete:
            if path.resolve() in (current_target, previous_target):
                continue
            try:
                shutil.rmtree(path)
                pruned.append(path.name)
            except Exception as e:
                log.warning("Failed to remove release %s: %s", path, e)

        return pruned

    def list_releases(self) -> list[dict[str, Any]]:
        """List all available releases with metadata and status tags."""
        if not self.releases_dir.is_dir():
            return []

        current_target = self.current_link.resolve() if self.current_link.exists() else None
        previous_target = self.previous_link.resolve() if self.previous_link.exists() else None

        items: list[dict[str, Any]] = []
        for path in sorted(self.releases_dir.iterdir()):
            if not path.is_dir():
                continue
            manifest = path / "release.json"
            meta: dict[str, Any] = {"name": path.name, "path": str(path)}
            if manifest.is_file():
                try:
                    meta.update(json.loads(manifest.read_text(encoding="utf-8")))
                except Exception:
                    pass

            is_curr = bool(current_target and path.resolve() == current_target)
            is_prev = bool(previous_target and path.resolve() == previous_target)
            meta["is_current"] = is_curr
            meta["is_previous"] = is_prev
            items.append(meta)

        items.sort(key=lambda x: float(x.get("created_at", 0)), reverse=True)
        return items

    def _restart_services(self) -> None:
        """Fail explicitly if either service cannot be restarted."""
        subprocess.run(["systemctl", "--user", "daemon-reload"], check=True, timeout=10)
        subprocess.run(
            ["systemctl", "--user", "restart", "jarvis-voice.service", "jarvis-device-bridge.service"],
            check=True,
            timeout=30,
        )

    def verify_health(self, timeout: float = 5.0) -> bool:
        """Require both operational services to remain active for one second."""
        deadline = time.monotonic() + timeout
        healthy_since: float | None = None
        while time.monotonic() < deadline:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            try:
                res = subprocess.run(
                    ["systemctl", "--user", "is-active", "jarvis-voice.service",
                     "jarvis-device-bridge.service"],
                    capture_output=True, text=True, timeout=min(2.0, remaining),
                )
                healthy = res.returncode == 0 and res.stdout.split() == ["active", "active"]
            except (OSError, subprocess.TimeoutExpired):
                healthy = False
            now = time.monotonic()
            if healthy:
                if healthy_since is None:
                    healthy_since = now
                if now - healthy_since >= 1.0:
                    return True
            else:
                healthy_since = None
            time.sleep(min(0.25, max(0.0, deadline - now)))
        return False

    def snapshot_state(self) -> list[Path]:
        """Create timestamped snapshots of persistent SQLite databases before activation."""
        backed_up: list[Path] = []
        if not self.data_dir.is_dir():
            return backed_up

        for db in self.data_dir.glob("*.db"):
            if ".bak" in db.name:
                continue
            bak_path = db.with_name(f"{db.name}.bak.{int(time.time())}")
            try:
                shutil.copy2(db, bak_path)
                backed_up.append(bak_path)
            except Exception as e:
                log.warning("Failed to backup %s: %s", db, e)
        return backed_up

    def _set_link(self, link: Path, target: Path | None) -> None:
        """Replace a release pointer atomically, or restore an absent pointer."""
        if target is None:
            link.unlink(missing_ok=True)
            return
        temporary = link.with_name(link.name + ".tmp")
        temporary.unlink(missing_ok=True)
        temporary.symlink_to(target)
        temporary.replace(link)

    def _switch_release(self, target: Path, timeout: float) -> dict[str, Any]:
        if not target.is_dir() or not (target / "release.json").is_file():
            raise ValueError(f"Invalid release directory: {target}")
        # Validate metadata before touching the active pointers.
        metadata = json.loads((target / "release.json").read_text(encoding="utf-8"))
        old_current = self.current_link.resolve() if self.current_link.exists() else None
        old_previous = self.previous_link.resolve() if self.previous_link.exists() else None
        try:
            if old_current and old_current != target:
                self._set_link(self.previous_link, old_current)
            self._set_link(self.current_link, target)
            self._restart_services()
            if not self.verify_health(timeout=timeout):
                raise RuntimeError("Health probe failed for voice or device bridge")
        except Exception as activation_error:
            # Restore BOTH pointers, including the earlier rollback target.
            self._set_link(self.current_link, old_current)
            self._set_link(self.previous_link, old_previous)
            if old_current is None:
                raise RuntimeError(
                    f"Activation failed: {activation_error}; no previous active release to restore"
                ) from activation_error
            try:
                self._restart_services()
                if not self.verify_health(timeout=timeout):
                    raise RuntimeError("restored services failed health verification")
            except Exception as recovery_error:
                raise RuntimeError(
                    f"Activation failed: {activation_error}; release pointers restored, "
                    f"but recovery failed: {recovery_error}"
                ) from activation_error
            raise RuntimeError(
                f"Activation failed: {activation_error}; automatically rolled back to {old_current.name}"
            ) from activation_error
        return metadata

    def activate_release(self, release_dir: Path | str, timeout: float = 8.0) -> dict[str, Any]:
        """Activate a release, restoring the old state on restart or health failure."""
        self.init_directories()
        self.snapshot_state()
        metadata = self._switch_release(Path(release_dir).resolve(), timeout)
        self.prune_releases(keep=3)
        return metadata

    def rollback(self, timeout: float = 8.0) -> dict[str, Any]:
        """Switch to the previous release with the same recovery guarantees."""
        current = self.current_link.resolve() if self.current_link.exists() else None
        previous = self.previous_link.resolve() if self.previous_link.exists() else None
        if previous is None or previous == current:
            previous = next(
                (Path(r["path"]) for r in self.list_releases()
                 if not r.get("is_current") and Path(r["path"]).is_dir()), None,
            )
        if previous is None:
            raise RuntimeError("No previous release found for rollback")
        return self._switch_release(previous, timeout)

    def apply_update(self, timeout: float = 8.0) -> dict[str, Any]:
        """Fetch upstream, compile release, activate it, and prune old releases."""
        commit_sha = self.fetch_upstream()
        release_path = self.build_release(commit_sha)
        return self.activate_release(release_path, timeout=timeout)
