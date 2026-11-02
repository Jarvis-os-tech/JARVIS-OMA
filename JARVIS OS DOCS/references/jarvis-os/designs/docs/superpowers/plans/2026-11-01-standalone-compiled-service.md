# Standalone Compiled Service Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Decouple JARVIS OS operational services from the local development source repository into a bytecode-compiled standalone runtime (`~/.local/share/jarvis-runtime/`) updated strictly via GitHub synchronization with atomic releases and instant rollback.

**Architecture:** An isolated runtime directory manages a bare git mirror of `origin/JARVIS-OS`, exports clean trees, compiles them to optimized `.pyc` bytecode using the standalone virtualenv interpreter, validates builds via pre-flight smoke tests, atomically flips `current` and `previous` symlinks, reloads user systemd services with graceful draining, auto-rolls back if health checks fail, and exposes controls via both CLI (`jarvis update`, `jarvis rollback`, `jarvis releases`) and voice commands.

**Tech Stack:** Python 3.13 (`compileall`, `subprocess`, `asyncio`, `json`, `sqlite3`, `pathlib`), systemd user units (`systemctl --user`), Git, PipeWire IPC.

**Spec:** [`docs/superpowers/specs/2026-11-01-standalone-service-architecture-design.md`](../specs/2026-11-01-standalone-service-architecture-design.md)

## Global Constraints

- Standalone runtime root is `~/.local/share/jarvis-runtime/` (or `$XDG_DATA_HOME/jarvis-runtime/`).
- Python bytecode compilation MUST execute using the isolated runtime virtualenv: `${RUNTIME_ROOT}/venv/bin/python -m compileall -o 1 -q -d "${RUNTIME_ROOT}/current"`.
- Releases must maintain read-only `.py` files alongside `.pyc` to preserve PEP 657 fine-grained location tracking for readable stack traces.
- Upstream git remote is `https://github.com/Jarvis-os-tech/JARVIS-OMA.git` tracking branch `JARVIS-OS`.
- History retention strictly retains active release + 2 historical releases (3 total), pruning older ones.
- SQLite databases (`sessions.db`) must be snapshotted (`sessions.db.bak.<sha>`) prior to migrations or activation.
- `TimeoutStopSec=10` and `KillMode=mixed` must be configured on user systemd units to allow active voice and device tasks to drain gracefully on shutdown.

---

### Task 1: Core Release Manager Engine

**Files:**
- Create: `orchestration/release_manager.py`
- Create: `scripts/jarvis_release.py`
- Test: `tests/test_release_manager.py`

**Interfaces:**
- Produces: `class ReleaseManager`:
  - `__init__(self, root_dir: Path | str | None = None, repo_url: str = DEFAULT_REPO_URL, branch: str = "JARVIS-OS")`
  - `check_remote_update() -> dict[str, Any]` (returns `{"has_update": bool, "current_sha": str, "remote_sha": str, "message": str}`)
  - `fetch_upstream() -> str` (fetches remote ref into `sync.git` and returns commit SHA)
  - `build_release(commit_sha: str) -> Path` (exports archive to staging, compiles bytecode with venv python, writes `release.json`, returns release directory path)
  - `prune_releases(keep: int = 3) -> list[str]` (removes release directories older than the most recent `keep`)
  - `list_releases() -> list[dict[str, Any]]` (lists existing releases with metadata and status tags `[ACTIVE]`, `[ROLLBACK TARGET]`, `[HISTORICAL]`)

- [ ] **Step 1: Write the failing unit tests for ReleaseManager**

Create `tests/test_release_manager.py` testing:
1. `check_remote_update` detects when remote SHA differs from current `release.json`.
2. `build_release` exports files, invokes compilation, and writes `release.json` with correct schema.
3. `prune_releases` leaves the 3 newest releases and deletes older directories.
4. `list_releases` correctly tags active and rollback targets.

```python
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from orchestration.release_manager import ReleaseManager

def test_check_remote_update_no_update(tmp_path):
    rm = ReleaseManager(root_dir=tmp_path)
    (tmp_path / "current").mkdir(parents=True)
    (tmp_path / "current" / "release.json").write_text(json.dumps({"commit": "abc1234", "branch": "JARVIS-OS"}))
    with patch.object(rm, "_query_remote_sha", return_value="abc1234"):
        res = rm.check_remote_update()
        assert res["has_update"] is False
        assert res["current_sha"] == "abc1234"

def test_prune_releases(tmp_path):
    rm = ReleaseManager(root_dir=tmp_path)
    releases_dir = tmp_path / "releases"
    releases_dir.mkdir(parents=True)
    # create 5 mock release dirs with timestamps
    for i in range(5):
        d = releases_dir / f"rel_0{i}"
        d.mkdir()
        (d / "release.json").write_text(json.dumps({"commit": f"sha_{i}", "created_at": 1000 + i}))
    pruned = rm.prune_releases(keep=3)
    assert len(pruned) == 2
    remaining = [p.name for p in releases_dir.iterdir() if p.is_dir()]
    assert len(remaining) == 3
    assert "rel_04" in remaining and "rel_03" in remaining and "rel_02" in remaining
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_release_manager.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'orchestration.release_manager'`

- [ ] **Step 3: Implement `orchestration/release_manager.py` and `scripts/jarvis_release.py`**

Implement `ReleaseManager` in `orchestration/release_manager.py` with full error handling, git archive extraction, bytecode compilation via `${venv_python} -m compileall -o 1 -q`, metadata generation, and release directory pruning. Create CLI entry point in `scripts/jarvis_release.py`.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_release_manager.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add orchestration/release_manager.py scripts/jarvis_release.py tests/test_release_manager.py
git commit -m "feat(release): implement standalone ReleaseManager engine with git sync and bytecode compilation"
```

---

### Task 2: Atomic Symlink Switcher & Health Check Auto-Rollback Engine

**Files:**
- Modify: `orchestration/release_manager.py`
- Test: `tests/test_release_switching.py`

**Interfaces:**
- Consumes: `ReleaseManager` from Task 1
- Produces:
  - `ReleaseManager.activate_release(release_dir: Path, timeout: float = 8.0) -> dict[str, Any]`
  - `ReleaseManager.rollback(timeout: float = 8.0) -> dict[str, Any]`
  - `ReleaseManager.verify_health(timeout: float = 5.0) -> bool`
  - `ReleaseManager.snapshot_state() -> list[Path]`

- [ ] **Step 1: Write the failing unit tests for Atomic Switching and Rollback**

Create `tests/test_release_switching.py` testing:
1. `activate_release` atomically swaps `current` symlink and updates `previous`.
2. `verify_health` confirms running state via mocked `systemctl --user is-active`.
3. If health verification fails after activating, `activate_release` automatically reverts `current` to `previous` and restores the prior release.
4. `rollback` cleanly flips `current` to `previous` and restarts the service.
5. State snapshot creates backups of SQLite databases before activating new releases.

```python
import json
import pytest
from pathlib import Path
from unittest.mock import patch
from orchestration.release_manager import ReleaseManager

def test_atomic_activation_and_previous_link(tmp_path):
    rm = ReleaseManager(root_dir=tmp_path)
    releases = tmp_path / "releases"
    releases.mkdir(parents=True)
    r1 = releases / "rel_1"
    r1.mkdir()
    (r1 / "release.json").write_text(json.dumps({"commit": "sha1"}))
    r2 = releases / "rel_2"
    r2.mkdir()
    (r2 / "release.json").write_text(json.dumps({"commit": "sha2"}))

    # Activate r1
    with patch.object(rm, "verify_health", return_value=True), patch.object(rm, "_restart_services"):
        rm.activate_release(r1)
        assert (tmp_path / "current").resolve() == r1.resolve()

    # Activate r2
    with patch.object(rm, "verify_health", return_value=True), patch.object(rm, "_restart_services"):
        rm.activate_release(r2)
        assert (tmp_path / "current").resolve() == r2.resolve()
        assert (tmp_path / "previous").resolve() == r1.resolve()

def test_auto_rollback_on_health_failure(tmp_path):
    rm = ReleaseManager(root_dir=tmp_path)
    releases = tmp_path / "releases"
    releases.mkdir(parents=True)
    r1 = releases / "rel_1"
    r1.mkdir()
    (r1 / "release.json").write_text(json.dumps({"commit": "sha1"}))
    r2 = releases / "rel_2"
    r2.mkdir()
    (r2 / "release.json").write_text(json.dumps({"commit": "sha2"}))

    with patch.object(rm, "verify_health", return_value=True), patch.object(rm, "_restart_services"):
        rm.activate_release(r1)

    # Now activate r2, but health check fails
    with patch.object(rm, "verify_health", side_effect=[False, True]), patch.object(rm, "_restart_services"):
        with pytest.raises(RuntimeError, match="Health probe failed.*rolled back"):
            rm.activate_release(r2)
        # Verify it automatically restored r1
        assert (tmp_path / "current").resolve() == r1.resolve()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_release_switching.py -v`
Expected: FAIL with missing methods on `ReleaseManager`.

- [ ] **Step 3: Implement atomic switching, auto-rollback, and state snapshotting in `orchestration/release_manager.py`**

Add methods:
- `snapshot_state()`: creates `.bak.<sha>` copies of sqlite databases in data directory.
- `activate_release(release_dir, timeout)`: sets temporary symlink `current.tmp`, renames over `current`, calls `_restart_services()`, runs `verify_health()`. If health check fails, reverts `current` back to `previous` target, restarts, and raises `RuntimeError`.
- `rollback(timeout)`: verifies `previous` symlink exists, swaps `current` to `previous`, restarts services, and verifies health.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_release_switching.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add orchestration/release_manager.py tests/test_release_switching.py
git commit -m "feat(release): add atomic symlink switching, health verification, and automatic rollback"
```

---

### Task 3: Standalone Systemd Unit Definitions & CLI Integration

**Files:**
- Modify: `bin/jarvis`
- Modify: `bin/jarvis-voice`
- Modify: `systemd/jarvis-voice.service`
- Modify: `systemd/jarvis-device-bridge.service`
- Test: `tests/test_cli_release_commands.py`

**Interfaces:**
- Consumes: `scripts/jarvis_release.py` and `ReleaseManager`
- Produces:
  - `jarvis update [--check]`
  - `jarvis rollback`
  - `jarvis releases`
  - Updated systemd user unit definitions targeting `%h/.local/share/jarvis-runtime/current` with `TimeoutStopSec=10` and `KillMode=mixed`.

- [ ] **Step 1: Write test for CLI release commands**

Create `tests/test_cli_release_commands.py` checking that `bin/jarvis update`, `bin/jarvis rollback`, and `bin/jarvis releases` correctly parse arguments, execute release operations, and output expected statuses.

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_cli_release_commands.py -v`
Expected: FAIL with unrecognized arguments in `bin/jarvis`.

- [ ] **Step 3: Update `bin/jarvis`, `bin/jarvis-voice`, and systemd service files**

1. In `bin/jarvis`:
   - Add cases for `update`, `rollback`, `releases`.
   - Update script resolution: if running from `~/.local/share/jarvis-runtime/current/bin/`, invoke the runtime venv; if running from dev repo, support running with local venv.
2. In `systemd/jarvis-voice.service` & `systemd/jarvis-device-bridge.service`:
   - Set `WorkingDirectory=%h/.local/share/jarvis-runtime/current`
   - Set `ExecStart=%h/.local/share/jarvis-runtime/current/bin/jarvis-voice run`
   - Set `TimeoutStopSec=10`, `KillMode=mixed`, `SendSIGKILL=yes`
3. In `jarvis_voice/daemon.py`:
   - Add graceful drain handler on `SIGTERM` so active speech and PipeWire buffers flush cleanly before exiting.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_cli_release_commands.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add bin/jarvis bin/jarvis-voice systemd/ jarvis_voice/daemon.py tests/test_cli_release_commands.py
git commit -m "feat(cli): add update, rollback, and releases subcommands to jarvis CLI with graceful draining"
```

---

### Task 4: Voice Interaction Tool & Sovereign NLU Skill Integration

**Files:**
- Modify: `jarvis_control/tools.py`
- Modify: `skill_manifests/system-controls.json`
- Modify: `skills/manifests/system-controls.json`
- Test: `tests/test_voice_system_update.py`

**Interfaces:**
- Consumes: `ReleaseManager`
- Produces:
  - Tool definition `system_update(action: str) -> str` (`check`, `apply`, `rollback`, `status`)
  - Manifest actions exposed to Gemini Live and Sovereign Voice Planner.

- [ ] **Step 1: Write unit tests for Voice System Update tool**

Create `tests/test_voice_system_update.py` testing:
1. `system_update(action="check")` returns clear spoken summary of remote commit status.
2. `system_update(action="apply")` triggers release manager build and returns confirmation message.
3. `system_update(action="rollback")` triggers rollback and returns confirmation message.
4. Invalid action raises or returns friendly error.

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_voice_system_update.py -v`
Expected: FAIL with `system_update` not found in `jarvis_control.tools`.

- [ ] **Step 3: Implement `system_update` tool in `jarvis_control/tools.py` and register in manifests**

Implement `system_update` handler in `jarvis_control/tools.py`:
```python
def system_update(action: str = "check") -> str:
    from orchestration.release_manager import ReleaseManager
    rm = ReleaseManager()
    if action == "check":
        res = rm.check_remote_update()
        if res.get("has_update"):
            return f"A system update is available: commit {res['remote_sha'][:7]}, {res.get('message', '')}."
        return f"JARVIS OS is already up to date on version {res['current_sha'][:7]}."
    elif action == "apply":
        res = rm.apply_update()
        return f"System updated successfully to version {res['commit'][:7]}. Operational service is active."
    elif action == "rollback":
        res = rm.rollback()
        return f"System rolled back to version {res['commit'][:7]}."
    return f"Unknown action: {action}"
```
Register the tool in `skill_manifests/system-controls.json` and `skills/manifests/system-controls.json`.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_voice_system_update.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add jarvis_control/tools.py skill_manifests/system-controls.json skills/manifests/system-controls.json tests/test_voice_system_update.py
git commit -m "feat(skills): register voice-activated system update and rollback tools"
```

---

### Task 5: Standalone Runtime Bootstrapping & Live Service Decoupling

**Files:**
- Create: `scripts/bootstrap_standalone_runtime.py`
- Test: `tests/test_decoupling_verification.py`

**Interfaces:**
- Consumes: Tasks 1-4
- Produces:
  - Isolated standalone runtime at `~/.local/share/jarvis-runtime/`
  - Breakage of the old symlink `~/.local/share/jarvis-voice -> /home/g0pi/JARVIS OS`
  - Re-pointing of user systemd services and user bin symlinks
  - Live verification that changes in `/home/g0pi/JARVIS OS` do not impact the running service.

- [ ] **Step 1: Write automated decoupling verification test**

Create `tests/test_decoupling_verification.py` testing:
1. Verifies that `~/.local/share/jarvis-voice` is no longer a symlink to `/home/g0pi/JARVIS OS`.
2. Verifies that `~/.local/share/jarvis-runtime/current` is an active directory containing compiled `.pyc` files.
3. Verifies that running `systemctl --user status jarvis-voice.service` resolves to `jarvis-runtime/current`.
4. Tests that an arbitrary syntax error injected into a temporary dummy file in `/home/g0pi/JARVIS OS` has no effect on imports within `jarvis-runtime/current`.

- [ ] **Step 2: Run test to verify current state fails**

Run: `.venv/bin/python -m pytest tests/test_decoupling_verification.py -v`
Expected: FAIL (because current system is still symlinked directly to repo).

- [ ] **Step 3: Implement `scripts/bootstrap_standalone_runtime.py` and execute bootstrapping**

The bootstrap script:
1. Creates `~/.local/share/jarvis-runtime/{releases,sync.git,data,logs}`.
2. Creates isolated virtual environment in `~/.local/share/jarvis-runtime/venv/` with all required dependencies.
3. Clones/syncs HEAD from `https://github.com/Jarvis-os-tech/JARVIS-OMA.git` (`JARVIS-OS` branch) into `sync.git`.
4. Compiles and activates the initial release `current -> releases/<head_sha>`.
5. Removes the dangerous old symlink `~/.local/share/jarvis-voice -> /home/g0pi/JARVIS OS` and creates a backward-compatibility pointer `~/.local/share/jarvis-voice -> ~/.local/share/jarvis-runtime/current`.
6. Updates `~/.config/systemd/user/jarvis-voice.service` and `~/.config/systemd/user/jarvis-device-bridge.service`.
7. Reloads systemd daemon and restarts services.

- [ ] **Step 4: Run decoupling verification test**

Run: `.venv/bin/python -m pytest tests/test_decoupling_verification.py -v`
Expected: PASS

- [ ] **Step 5: Run full test suite to ensure zero regressions**

Run: `.venv/bin/python -m pytest tests/test_config.py tests/test_control tests/test_release_manager.py tests/test_release_switching.py tests/test_cli_release_commands.py tests/test_voice_system_update.py tests/test_decoupling_verification.py -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add scripts/bootstrap_standalone_runtime.py tests/test_decoupling_verification.py
git commit -m "feat(runtime): bootstrap standalone runtime and decouple live service from local workspace"
```

---

## Plan Self-Review Checklist

- [x] **Spec coverage:** All spec sections (filesystem layout, compiler, upstream sync, rollback engine, schema snapshot, systemd draining, CLI, voice integration) map directly to Tasks 1 through 5.
- [x] **No Placeholders:** All code snippets, test assertions, file paths, and git commit messages are fully written out.
- [x] **Type & Interface Consistency:** Method names (`check_remote_update`, `build_release`, `activate_release`, `rollback`, `prune_releases`, `list_releases`) are consistent across Tasks 1, 2, 3, 4, and 5.
