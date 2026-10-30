# Task Brief: Tasks 1-5 Batch Implementation (Core Modules)

## Goal
Implement the core modules and tests for JARVIS Voice Core in `/home/g0pi/JARVIS OS`:
1. `jarvis_voice/__init__.py`
2. `jarvis_voice/config.py`
3. `jarvis_voice/ipc.py`
4. `jarvis_voice/recovery.py`
5. `jarvis_voice/speech.py`
6. `jarvis_voice/playback.py`
7. Corresponding unit tests in `tests/test_config.py`, `tests/test_ipc.py`, `tests/test_recovery.py`, `tests/test_speech.py`, `tests/test_playback.py`.

## Requirements
Follow the exact implementations and tests specified in `docs/superpowers/plans/2026-10-30-voice-foundation.md` for Tasks 1 through 5.
- Zero modifications to `/home/g0pi/Projects/JARVIS-OMA/audio/.voice_lock.json` or any locked files.
- Run tests via `.venv/bin/pytest tests/test_config.py tests/test_ipc.py tests/test_recovery.py tests/test_speech.py tests/test_playback.py -v` (or system `python3 -m pytest`).
- Ensure all tests pass.
- Write report to `.superpowers/sdd/2026-10-30-voice-foundation/task-1-5-report.md`.
