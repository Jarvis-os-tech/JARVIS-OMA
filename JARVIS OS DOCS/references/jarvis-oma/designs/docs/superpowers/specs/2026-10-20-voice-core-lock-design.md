# Voice Core Immutability Lock & Non-Invasive Extension Architecture

**Date:** 2026-10-20  
**Status:** Approved  

## 1. Goal & Context

The JARVIS-OMA audio subsystem (`audio/engine.py`, `audio/downstream.py`, `audio/echo_cancel.py`, `echo_cancel.py`) implements low-latency isochronous PortAudio streaming, PipeWire WebRTC Acoustic Echo Cancellation (AEC), and generation-fenced barge-in flushes. These components are critical to full-duplex conversational voice and must not be altered, degraded, or overridden by autonomous or delegated agents.

This specification locks existing voice core features while providing a clean extension architecture (`audio/extension.py`) allowing new capabilities (filters, telemetry, custom hooks, audio processors) to be attached without modifying the core files.

## 2. Protected Files (Voice Core Manifest)

The following files are designated as **Locked Voice Core**:
- `audio/engine.py` (SHA-256: `02f2860c73f42c35a90f4f136c70878d65599c3aeccccc23177cd44c027c43bc`)
- `audio/downstream.py` (SHA-256: `2dc40b51e69109cf36adf53cd687223db98a973f8597d1a0b12feff549abdaf3`)
- `audio/echo_cancel.py` (SHA-256: `779b7ac39e6d2cc5b1e8ba0b4881edca6134ff3165a4341020946cb385b5a658`)
- `audio/__init__.py` (SHA-256: `1df085dce9c32aad4fa40515ee0c315033d74581468cbd86d05d41e436b227df`)
- `echo_cancel.py` (SHA-256: `93203b16c167b5669252824e978074796d55d6fc6fff0857d38ac2b2e38e930d`)
- `tests/test_audio/test_engine.py` (SHA-256: `aca308865ad1447c98f7c5dade76941b1286270e2f2b9dca4e4fb94254d96d1f`)
- `tests/test_audio/test_echo_cancel.py` (SHA-256: `6ccb6c4618f7bb4cb3ccadecbabe06003a4c4a7dec60b025754b19e4a5d77307`)

The manifest is maintained in `audio/.voice_lock.json`.

## 3. Defense-in-Depth Enforcement Mechanisms

### 3.1 Evolution Engine Mutation Gate (`orchestration/evolution.py`)
- Define `LOCKED_VOICE_PATHS` containing all locked voice core file paths.
- In `EvolutionManager._run`, after the implementer stage runs and git diff is calculated, inspect the set of changed files (`git diff --name-only`).
- If any file in `LOCKED_VOICE_PATHS` is modified, deleted, or renamed, immediately abort the evolution job and raise `EvolutionError("Mutation of locked voice core file rejected: <path>")`.
- Include the explicit constraint in `_stage(job, 'implementer')` prompt: *"Do not modify, override, or delete locked voice core files under audio/ or echo_cancel.py."*

### 3.2 Multi-Agent Governance (`AGENTS.md`, `CLAUDE.md`, `orchestration/personas.py`, `orchestration/harness2_adapter.py`)
- Create `AGENTS.md` and `CLAUDE.md` in repository root declaring the Voice Immutability Invariant for Codex, Claude Code, OpenCode, Hermes, and OMP.
- In `orchestration/personas.py` (`software_assignments`), inject the requirement that agents must never edit or override core voice files.
- In `orchestration/harness2_adapter.py` (`prepare_prompt`), include the voice lock invariant in the injected prompt context.

### 3.3 Integrity Verifier & Git Pre-Commit Hook (`scripts/verify_voice_lock.py`)
- Python script that checks:
  1. Cryptographic hashes of all locked files match `audio/.voice_lock.json`.
  2. Working tree / staged files (`git diff --name-only` / `git diff --cached --name-only`) contain zero modifications to locked files.
- Exit code 0 if intact; nonzero if violated.
- Can be invoked directly or symlinked/copied to `.git/hooks/pre-commit`.

### 3.4 Non-Invasive Extension Architecture (`audio/extension.py`)
To allow adding new features without editing current voice code (Open-Closed Principle):
- `AudioFrameProcessor`: Protocol/interface for inspecting or transforming PCM chunks (e.g. noise gates, level meters, wake-word detection, stream recording).
- `AudioHook`: Event listener interface for state changes (`listening`, `speaking`, `ducked`, `barged_in`) and turn boundaries.
- `AudioExtensionRegistry`: Registry for registering frame processors and event hooks.
- `ExtendedAudioEngine`: Composition wrapper around `NativeAudioEngine` that hooks into input/output queues and callbacks to dispatch to registered processors, leaving `NativeAudioEngine` unmodified.

## 4. Verification Plan

1. **Automated Unit Tests (`tests/test_audio/test_voice_lock.py`)**:
   - `test_voice_lock_manifest_matches_disk`: Verifies SHA-256 hashes of all locked files match the manifest.
   - `test_verify_voice_lock_script_succeeds`: Verifies `scripts/verify_voice_lock.py` exits with 0.
   - `test_evolution_rejects_voice_mutations`: Tests `EvolutionManager` rejects changes touching locked voice files.
   - `test_extension_architecture_without_modifying_core`: Tests `ExtendedAudioEngine` and `AudioExtensionRegistry` function properly without modifying core voice files.
2. **Full Regression Check**:
   - Run `pytest tests/` to confirm all existing audio and orchestration tests continue to pass.
