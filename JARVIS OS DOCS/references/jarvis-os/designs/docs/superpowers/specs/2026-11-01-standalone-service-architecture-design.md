# JARVIS OS: Standalone Compiled Service Architecture & Release Synchronization Specification

- **Date:** 2026-11-01
- **Status:** Proposed / Draft
- **Target Systems:** JARVIS Voice Core (`jarvis-voice.service`), Shared Device Bridge (`jarvis-device-bridge.service`), System Control CLI (`bin/jarvis`), Sovereign NLU & Tools.

---

## 1. Executive Summary & Objective

Currently, the operational user services (`jarvis-voice.service`, `jarvis-device-bridge.service`) execute directly from `/home/g0pi/.local/share/jarvis-voice`, which is a symlink pointing directly to `/home/g0pi/JARVIS OS`. This coupling exposes the live ambient voice assistant to broken states, syntax errors, and in-flight changes whenever developers or autonomous agents edit, test, or switch branches in the development workspace.

This specification details the architecture to:
1. **Decouple** the operational service into an isolated standalone runtime at `~/.local/share/jarvis-runtime/`.
2. **Compile** Python modules using the exact runtime virtual environment interpreter into optimized bytecode releases.
3. **Synchronize** operational updates strictly from the GitHub remote branch `origin/JARVIS-OS` (via `https://github.com/Jarvis-os-tech/JARVIS-OMA.git`), preventing local uncommitted changes from ever impacting the live service.
4. **Provide Atomic Switching and Deterministic Rollbacks** via atomic symlink flips (`current` and `previous`), automated health probe gates, and history retention.
5. **Expose Controls** through both manual CLI (`jarvis update`, `jarvis rollback`, `jarvis releases`) and natural voice commands via the Sovereign Voice engine.

---

## 2. System Architecture & Filesystem Layout

All operational runtime files, compiled releases, and virtual environments are contained under `~/.local/share/jarvis-runtime/`:

```
~/.local/share/jarvis-runtime/
├── current -> releases/20261101-9a3428c/      # Atomic symlink to the active release
├── previous -> releases/20261031-fff599c/     # Symlink to the previous working release
├── venv/                                      # Standalone Python 3.13 virtual environment
├── sync.git/                                  # Bare/shallow git mirror for upstream sync
├── releases/                                  # Historical immutable releases (retains 3)
│   ├── 20261101-9a3428c/                      # Immutable release root
│   │   ├── bin/                               # Standalone executable scripts
│   │   │   ├── jarvis
│   │   │   ├── jarvis-voice
│   │   │   └── jarvis-control
│   │   ├── jarvis_voice/                      # Compiled bytecode & modules
│   │   ├── jarvis_control/
│   │   ├── jarvis_memory/
│   │   ├── core/
│   │   ├── connectors/
│   │   ├── skills/
│   │   ├── release.json                       # Manifest: commit SHA, branch, date, schema
│   │   └── migrations/                        # Database migration scripts (if any)
│   └── 20261031-fff599c/
├── data/                                      # Runtime state shared across versions
│   ├── sessions.db
│   ├── memory/
│   └── mobile-updates/
└── logs/
    └── update.log                             # Detailed build and update history
```

### Decoupling Guarantees
- The git working tree at `/home/g0pi/JARVIS OS` is completely isolated from the runtime.
- Global user CLI shims in `~/.local/bin/` (`jarvis`, `jarvis-voice`, `jarvis-control`, `jarvis-memory`) resolve through `~/.local/share/jarvis-runtime/current/bin/`.
- User configuration persists independently in standard XDG paths (`~/.config/jarvis-voice/config.toml` and `~/.config/jarvis-voice/env`), ensuring updates never overwrite user settings.

---

## 3. Bytecode Compilation & Interpreter Binding

### 3.1 Magic Word & Minor Version Consistency
Python `.pyc` bytecode files include a 4-byte magic number that is strictly bound to the exact Python version and compilation flags. To prevent bytecode corruption:
- The release builder **strictly invokes the standalone virtual environment python binary**:
  `${RUNTIME_ROOT}/venv/bin/python -m compileall -o 1 -q -d "${RUNTIME_ROOT}/current" "${BUILD_DIR}"`
- The `-d` parameter sets the leading directory path in error tracebacks to the stable symlink path (`~/.local/share/jarvis-runtime/current`), ensuring tracebacks are normalized regardless of internal build directories.

### 3.2 Traceback & Debuggability Support
Python 3.11+ incorporates PEP 657 fine-grained location tracking into code objects.
- In addition to optimized `.pyc` files, release builds maintain read-only `.py` sources alongside compiled bytecode in immutable release folders (with permissions `0444` / `ro`).
- This allows full, clear tracebacks with exact source line code in `journalctl -u jarvis-voice` without exposing write access or runtime modification risks.

---

## 4. Upstream Synchronization Pipeline

The release manager (`jarvis-release` engine) executes the update pipeline:

```mermaid
sequenceDiagram
    participant User as User (CLI / Voice)
    participant Engine as Jarvis Release Engine
    participant GitHub as GitHub (origin/JARVIS-OS)
    participant Staging as Staging Builder
    participant Systemd as systemd user daemon

    User->>Engine: update request (check / apply)
    Engine->>GitHub: git ls-remote refs/heads/JARVIS-OS
    alt No new commits
        Engine-->>User: Already running latest version (SHA)
    else New commit available
        Engine->>GitHub: fetch target commit into sync.git
        Engine->>Staging: git archive export to staging directory
        Engine->>Staging: compileall using venv python
        Engine->>Staging: generate release.json metadata
        Engine->>Staging: pre-flight smoke test (dry-run probe)
        alt Smoke test fails
            Engine-->>User: Build rejected: smoke test failed
        else Smoke test passes
            Engine->>Engine: backup database schemas (if migrations present)
            Engine->>Engine: atomic symlink flip (current -> new, previous -> old)
            Engine->>Systemd: systemctl --user restart jarvis-voice jarvis-device-bridge
            Engine->>Systemd: health probe check (is-active within 5s)
            alt Health check failed
                Engine->>Engine: auto-rollback symlink (current -> previous)
                Engine->>Systemd: restart previous release
                Engine-->>User: Update failed; automatically rolled back
            else Health check passed
                Engine->>Engine: prune releases (keep last 3)
                Engine-->>User: Update succeeded: active on new SHA
            end
        end
    end
```

### Steps in Detail:
1. **Fetch & Verify**:
   - Queries `https://github.com/Jarvis-os-tech/JARVIS-OMA.git` for `refs/heads/JARVIS-OS`.
   - Downloads the git tree into `~/.local/share/jarvis-runtime/sync.git`.
2. **Export & Compile**:
   - Clean export via `git archive` to an isolated staging directory `staging-<sha>`.
   - Compiles `.py` to `.pyc` using `${RUNTIME_ROOT}/venv/bin/python`.
   - Writes `release.json` with commit SHA, commit author, commit message, build timestamp, and schema version.
3. **Pre-flight Smoke Test**:
   - Executes an isolated check: `${RUNTIME_ROOT}/venv/bin/python -m jarvis_voice --check` within the staging directory.
   - Verifies that imports (`google-genai`, `onnxruntime`, `sounddevice`, PipeWire IPC) resolve without errors.

---

## 5. Rollback Engine & State Migration Safeguards

### 5.1 Deterministic Rollback
The rollback mechanism is instant and deterministic:
1. When `jarvis rollback` is invoked (via CLI or Voice):
2. Validates that `~/.local/share/jarvis-runtime/previous` exists and points to a valid release directory with a valid `release.json`.
3. Swaps the `current` symlink to point to the `previous` target.
4. Executes graceful service restart via systemd.
5. Verifies service health probe.
6. Reports the rollback status and active commit SHA to the user.

### 5.2 Database & Schema Migration Safeguards
To prevent schema divergence (e.g., changes to SQLite tables in `sessions.db` or memory vector stores):
- Before applying schema migrations, the release engine creates a snapshot:
  `cp "${DATA_DIR}/sessions.db" "${DATA_DIR}/sessions.db.bak.${OLD_SHA}"`
- If an automatic or manual rollback occurs, the release engine checks whether a schema rollback script or snapshot restoration is required, safeguarding existing conversational memory.

---

## 6. Service Management & Graceful Draining

To prevent cutting off active audio streams, mid-turn responses, or device bridge commands during an update restart, the systemd unit definitions and daemon shutdown handlers are updated:

### 6.1 Systemd Service Definitions
- **`jarvis-voice.service`**:
  ```ini
  [Unit]
  Description=JARVIS Voice Core — ambient voice assistant
  After=graphical-session.target pipewire.service wireplumber.service
  PartOf=graphical-session.target
  StartLimitIntervalSec=300
  StartLimitBurst=5

  [Service]
  Type=simple
  WorkingDirectory=%h/.local/share/jarvis-runtime/current
  ExecStart=%h/.local/share/jarvis-runtime/current/bin/jarvis-voice run
  Environment=PYTHONPATH=%h/.local/share/jarvis-runtime/current
  Environment=XDG_RUNTIME_DIR=%t
  Restart=always
  RestartSec=2
  KillMode=mixed
  TimeoutStopSec=10
  SendSIGKILL=yes
  UMask=0077
  StandardOutput=journal
  StandardError=journal

  [Install]
  WantedBy=default.target graphical-session.target
  ```

### 6.2 IPC Draining on SIGTERM
- `jarvis_voice` signal handler intercepts `SIGTERM`:
  1. Stops listening for new wake words / audio input frames.
  2. Completes playing the current active TTS audio buffer if in progress (or limits drain to 2 seconds).
  3. Unlinks IPC socket cleanly.
  4. Exits with code 0.

---

## 7. User Interfaces: CLI & Voice Interaction

### 7.1 CLI Commands (`bin/jarvis`)
- `jarvis update`: Check GitHub for updates, build, compile, and switch atomically.
- `jarvis update --check`: Query remote GitHub commit and display update availability without applying.
- `jarvis rollback`: Instantly roll back to the previous release.
- `jarvis releases`: List retained releases, indicating `[ACTIVE]` and `[ROLLBACK TARGET]`.
- `jarvis status`: Output service state, active release SHA, and PipeWire audio health.

### 7.2 Voice Interaction Integration
- Tool implementation: `jarvis_control/tools.py` (`system_lifecycle` skill).
- Voice triggers:
  - *"Jarvis, check for system updates"* → Queries GitHub and speaks: *"A new update is available from commit <sha>, '<commit message>'. Would you like me to install it?"*
  - *"Jarvis, update to the latest version"* → Executes update, announces: *"Updating system from GitHub. Restarting services in 3 seconds."*
  - *"Jarvis, rollback to the previous version"* → Swaps symlink and announces: *"Rolling back to version <sha>. Service restored."*

---

## 8. Verification & Acceptance Criteria

1. **Decoupling Verification**: Modify or corrupt files in `/home/g0pi/JARVIS OS` (e.g. introduce deliberate syntax errors). Confirm the active service in `systemd` continues running smoothly without interruption.
2. **Bytecode Compilation Verification**: Inspect the release directory to verify `.pyc` files are generated by the dedicated venv python and load correctly.
3. **Upstream Sync Verification**: Execute `jarvis update`. Verify it pulls strictly from `origin/JARVIS-OS` on GitHub, builds cleanly in staging, and flips `current`.
4. **Health Probe & Auto-Rollback**: Simulate a faulty release. Verify that the health probe detects service startup failure and automatically restores `previous` within 10 seconds.
5. **Manual & Voice Rollback**: Execute `jarvis rollback` via CLI and voice command. Verify the service restarts cleanly on the previous commit SHA.
6. **Graceful Draining**: Issue restart during speech turn. Confirm audio finishes gracefully before restart without socket corruption.
