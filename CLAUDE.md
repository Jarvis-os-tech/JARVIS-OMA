# CLAUDE.md — Claude Code Project Guidelines for JARVIS-OMA

## Critical Invariant: Voice Core is Locked
The core audio subsystem in this repository (`audio/engine.py`, `audio/downstream.py`, `audio/echo_cancel.py`, `echo_cancel.py`, and `tests/test_audio/test_*.py`) is cryptographically locked and must NEVER be modified or overridden.

### Extension Policy:
- New voice features must be added **without editing existing voice code**.
- Use `audio/extension.py` (`AudioFrameProcessor`, `AudioHook`, `AudioExtensionRegistry`, `ExtendedAudioEngine`) to extend audio handling.
- Any modification to locked files will fail the pre-commit integrity verifier (`scripts/verify_voice_lock.py`).

## Common Development Commands
- Activate environment: `source .venv/bin/activate`
- Run all unit tests: `.venv/bin/pytest tests/ -q`
- Run audio tests: `.venv/bin/pytest tests/test_audio/ -v`
- Run orchestration tests: `.venv/bin/pytest tests/test_orchestration/ -v`
- Verify voice lock integrity: `python3 scripts/verify_voice_lock.py`
- Update codebase documentation: `python3 scripts/update_codebase_reference.py`
