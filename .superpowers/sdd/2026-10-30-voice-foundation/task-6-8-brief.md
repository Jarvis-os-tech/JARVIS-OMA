# Task Brief: Tasks 6-8 Implementation (Service, CLI, Daemon Integration, & E2E Verification)

## Goal
Complete the remaining tasks from `docs/superpowers/plans/2026-10-30-voice-foundation.md`:
- **Task 6**: Systemd Service, CLI Entry Point, and Installation Scripts
  - `systemd/jarvis-voice.service`
  - `bin/jarvis-voice` (chmod +x)
  - `scripts/install.sh` (chmod +x)
  - `scripts/uninstall.sh` (chmod +x)
  - `jarvis_voice/__main__.py` (CLI command parser: `run`, `status`, `listen`, `--check`, `--json`)
  - `tests/test_cli.py`
- **Task 7**: Full Voice Daemon Integration (`run` command)
  - `jarvis_voice/daemon.py` implementing `LiveVoice`, `live_config()`, and `async run()` integrating `Playback`, `SpeechTurnGate`, `SpokenInterruption`, `ConnectionRecovery`, `ControlServer`, and Gemini Live WebSocket connection.
  - Wire `run` command in `jarvis_voice/__main__.py` to `daemon.main(args)`
  - `tests/test_daemon.py`
- **Task 8**: End-to-End Verification & Documentation
  - `tests/test_integration.py`
  - Update `README.md` to document JARVIS Voice Core

## Requirements
- Follow Ponytail principles: clean, minimal, zero unnecessary abstractions.
- All tests must pass: `.venv/bin/pytest tests/ -v`
- Test `python3 -m jarvis_voice --check` must pass.
- Write report to `.superpowers/sdd/2026-10-30-voice-foundation/task-6-8-report.md`.
