# Voice Layer Consolidation Design

**Date:** 2026-11-02  
**Status:** Approved by User  
**Target:** Create unified `voice_layer/` package and remove duplicate/dead voice codes across the codebase.

---

## 1. Problem Statement & Motivation

Voice functionality across the JARVIS OS repository is currently fragmented across multiple overlapping directories:
- `jarvis_voice/`: The active production voice daemon, turn detection, echo cancellation, and recovery logic.
- `audio/`: A secondary/alternative PortAudio and PipeWire audio engine, with redundant plugin implementations.
- `pma_voice_only/`: An outdated standalone extraction from upstream PMA/omarchy-voice.
- `omarchy_voice/`: A dead 21-line compatibility stub redirecting to `jarvis_control`.
- `core/`: Stale monolithic voice files (`stable_voice.py`, `stable_echo_cancel.py`, `stable_recovery.py`, `speech_turn.py`, `monitor_echo.py`) that lack recent audit fixes.
- `deployment_backup/`: 8 historical snapshot folders containing duplicate voice code.
- Root stubs: `echo_cancel.py` (redirects to `audio.echo_cancel`).

This fragmentation creates confusion, code drift, maintenance overhead, and risk of bugs when fixes are applied to one location but not another.

---

## 2. Target Architecture: `voice_layer/`

All voice and audio responsibilities are consolidated into a single authoritative package: **`voice_layer/`**.

```
voice_layer/
├── __init__.py           # Public API and top-level exports
├── daemon.py             # LiveVoice orchestrator, Gemini Live session & tool execution
├── echo.py               # PipeWire WebRTC Acoustic Echo Cancellation (EchoCancellation)
├── speech.py             # Silero VAD turn gating & spoken interruption detection
├── playback.py           # Output priming, pacing, and generation fences
├── microphone.py         # Hardware device health & volume monitor via pactl
├── recovery.py           # ConnectionRecovery with 30 Oct audit fixes (429 delay, setup timeouts)
├── standby.py            # Offline wake-word detection (Hey Jarvis via openWakeWord)
├── ipc.py                # Unix domain socket control server (ControlServer)
├── config.py             # Voice configuration, env loading, state directory setup
├── background.py         # Desktop notification dispatcher for background results
├── engine.py             # Hardware audio stream abstraction & downstream router
└── assets/               # Wake-word model binaries (e.g. hey_jarvis.onnx)
```

---

## 3. Pruning & Removal Plan

The following redundant, duplicated, and dead directories and files will be removed:

1. **Delete Dead/Duplicate Folders**:
   - `pma_voice_only/`
   - `omarchy_voice/`
   - Obsolete voice backup folders in `deployment_backup/`:
     - `deployment_backup/voice-foundation-*`
     - `deployment_backup/six-foundation-fixes-*`
     - `deployment_backup/playback-continuity-*`
     - `deployment_backup/response-latency-*`
     - `deployment_backup/omarchy-audit-*`
     - `deployment_backup/verified-system-control-*`
     - `deployment_backup/microphone-response-*`
2. **Delete Stale Duplicates in `core/`**:
   - `core/stable_voice.py`
   - `core/stable_echo_cancel.py`
   - `core/stable_recovery.py`
   - `core/speech_turn.py`
   - `core/monitor_echo.py`
3. **Delete Root Shim**:
   - `echo_cancel.py`
4. **Clean up `audio/plugins/`**:
   - Remove `audio/plugins/spoken_interrupt.py` and `audio/plugins/standby.py` (superseded by `voice_layer`).

---

## 4. Backward Compatibility Strategy

To ensure zero downtime, no broken systemd services, and seamless passage of all 1,144+ unit tests:
1. **`jarvis_voice` Compatibility Shims**:
   - `jarvis_voice/` will become a transparent re-export layer forwarding directly to `voice_layer.*`.
   - Any external caller or test importing `from jarvis_voice.daemon import LiveVoice` will transparently resolve to `voice_layer.daemon.LiveVoice`.
2. **`audio` Compatibility Shims**:
   - `audio/__init__.py`, `audio/echo_cancel.py`, etc., will forward to `voice_layer.echo` and `voice_layer.engine`.
3. **CLI & Systemd Adjustments**:
   - `bin/jarvis-voice`: Update to prefer `voice_layer` (with fallback to `jarvis_voice`).
   - `bin/omarchy-voice`: Forward directly to `voice_layer`.
   - `scripts/install.sh`: Ensure `voice_layer` is installed alongside other packages.

---

## 5. Verification Strategy

1. **Unit & Integration Test Suite**:
   Run `.venv/bin/pytest tests/ --ignore=tests/test_memory -q` to verify all 1,144 tests pass.
2. **Import Verification**:
   Verify clean imports directly from `voice_layer`:
   - `from voice_layer import LiveVoice, EchoCancellation, SpeechTurnGate, Playback`
3. **CLI Verification**:
   - Test `bin/jarvis-voice --help` or `--check`
   - Test `bin/omarchy-voice --help`
4. **Git Status Cleanliness**:
   Ensure all removed files are properly tracked and no orphan bytecode or dangling imports remain.
