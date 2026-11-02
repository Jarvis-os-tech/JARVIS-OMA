# Voice Layer Consolidation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Consolidate all voice and audio code into a single authoritative `voice_layer/` package, delete duplicate/dead voice codes across the codebase, and ensure 100% test pass rate.

**Architecture:** Create `voice_layer/` housing the complete voice and audio engine (PipeWire WebRTC AEC, Silero VAD turn gating, bounded playback with generation fences, offline wake-word standby, session recovery, control server, and Gemini Live daemon). Provide transparent re-export compatibility in `jarvis_voice` and `audio` so that existing services, CLIs, and 1,144 tests continue without regression. Prune obsolete folders (`pma_voice_only/`, `omarchy_voice/`, `core/stable_*`, root shims, and stale `deployment_backup/` snapshots).

**Tech Stack:** Python 3.13, PipeWire, WebRTC AEC, sounddevice / PortAudio, openWakeWord / Silero VAD (ONNX runtime), websockets.

**Spec:** `docs/superpowers/specs/2026-11-02-voice-layer-consolidation-design.md`

## Global Constraints
- All 1,144 non-memory pytest tests must pass without regressions.
- No disruption to systemd services (`jarvis-voice.service`).
- CLI entry points (`bin/jarvis`, `bin/jarvis-voice`, `bin/omarchy-voice`) must operate correctly.
- All internal imports within `voice_layer` must be self-contained and relative or directly reference `voice_layer`.

---

### Task 1: Create `voice_layer/` Package & Authoritative Implementations

**Files:**
- Create:
  - `voice_layer/__init__.py`
  - `voice_layer/config.py`
  - `voice_layer/echo.py`
  - `voice_layer/speech.py`
  - `voice_layer/playback.py`
  - `voice_layer/microphone.py`
  - `voice_layer/recovery.py`
  - `voice_layer/standby.py`
  - `voice_layer/ipc.py`
  - `voice_layer/background.py`
  - `voice_layer/daemon.py`
  - `voice_layer/engine.py`
  - `voice_layer/assets/` (copy model files from `jarvis_voice/assets/`)
- Test: `tests/test_voice_layer_basic.py`

**Interfaces:**
- Produces: `voice_layer.LiveVoice`, `voice_layer.EchoCancellation`, `voice_layer.SpeechTurnGate`, `voice_layer.Playback`, `voice_layer.ControlServer`, `voice_layer.ConnectionRecovery`, `voice_layer.OpenWakeWordDetector`

- [ ] **Step 1: Write a unit test verifying `voice_layer` imports and key classes**
- [ ] **Step 2: Copy and adapt authoritative modules into `voice_layer/`**
- [ ] **Step 3: Update internal imports within `voice_layer/` to use relative imports (`.` / `voice_layer`)**
- [ ] **Step 4: Run test to verify `voice_layer` imports cleanly**
- [ ] **Step 5: Commit `voice_layer/` package**

---

### Task 2: Establish Compatibility Shims in `jarvis_voice` and `audio`

**Files:**
- Modify:
  - `jarvis_voice/__init__.py`
  - `jarvis_voice/daemon.py`
  - `jarvis_voice/echo.py`
  - `jarvis_voice/speech.py`
  - `jarvis_voice/playback.py`
  - `jarvis_voice/microphone.py`
  - `jarvis_voice/recovery.py`
  - `jarvis_voice/standby.py`
  - `jarvis_voice/ipc.py`
  - `jarvis_voice/config.py`
  - `jarvis_voice/background.py`
  - `audio/__init__.py`
  - `audio/echo_cancel.py`
- Test: Existing suites (`tests/test_daemon.py`, `tests/test_echo.py`, `tests/test_speech.py`, etc.)

**Interfaces:**
- Consumes: `voice_layer.*`
- Produces: 100% backward-compatible API signatures for `jarvis_voice.*` and `audio.echo_cancel`

- [ ] **Step 1: Convert `jarvis_voice` modules to re-export from `voice_layer`**
- [ ] **Step 2: Update `audio/echo_cancel.py` to re-export from `voice_layer.echo`**
- [ ] **Step 3: Run pytest on `tests/test_daemon.py` and `tests/test_echo.py` to verify compatibility**
- [ ] **Step 4: Commit compatibility layers**

---

### Task 3: Update System CLIs & Installer

**Files:**
- Modify:
  - `bin/jarvis-voice`
  - `bin/omarchy-voice`
  - `scripts/install.sh`
- Test: CLI invocations

- [ ] **Step 1: Update `bin/jarvis-voice` to prefer `voice_layer`**
- [ ] **Step 2: Update `bin/omarchy-voice` to execute via `voice_layer`**
- [ ] **Step 3: Update `scripts/install.sh` to package `voice_layer`**
- [ ] **Step 4: Test CLI invocations (`bin/jarvis-voice --help`, `bin/omarchy-voice --help`)**
- [ ] **Step 5: Commit CLI and installer updates**

---

### Task 4: Delete Duplicate & Dead Code

**Files:**
- Delete:
  - `pma_voice_only/`
  - `omarchy_voice/`
  - `echo_cancel.py` (root stub)
  - `core/stable_voice.py`
  - `core/stable_echo_cancel.py`
  - `core/stable_recovery.py`
  - `core/speech_turn.py`
  - `core/monitor_echo.py`
  - `audio/plugins/spoken_interrupt.py`
  - `audio/plugins/standby.py`
  - Obsolete `deployment_backup/voice-*` directories
- Modify:
  - Clean any dead imports pointing to deleted `core/stable_*` files (e.g. `core/agent.py`, `agent.py`)

- [ ] **Step 1: Remove `pma_voice_only/` and `omarchy_voice/`**
- [ ] **Step 2: Remove root `echo_cancel.py`**
- [ ] **Step 3: Remove duplicate voice files in `core/` and redirect root `agent.py` if needed**
- [ ] **Step 4: Remove redundant plugins in `audio/plugins/`**
- [ ] **Step 5: Remove stale voice snapshots in `deployment_backup/`**
- [ ] **Step 6: Commit deletions**

---

### Task 5: Comprehensive Verification & Test Suite Execution

**Files:**
- Test: `.venv/bin/pytest tests/ --ignore=tests/test_memory -q`

- [ ] **Step 1: Run the full test suite to ensure all 1,144+ tests pass**
- [ ] **Step 2: Verify git status is clean and well-organized**
- [ ] **Step 3: Update project documentation if applicable**
- [ ] **Step 4: Commit final verification changes**
