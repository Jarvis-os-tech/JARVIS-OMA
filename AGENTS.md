# AGENTS.md — JARVIS-OMA Multi-Agent Operating Invariants

This repository is cooperatively developed and operated by multiple autonomous and interactive AI agents (`claude`, `codex`, `gemini`, `opencode`, `hermes`, `omp`, `pi`, `crush`, `antigravity`).

All agents operating in this repository MUST adhere to the following hard invariants.

---

## 🔒 1. VOICE CORE IMMUTABILITY LOCK (STRICT RULE)

The following core voice and audio subsystem files are cryptographically locked:

- `audio/engine.py` (NativeAudioEngine PortAudio C-thread stream engine, AEC, VAD, barge-in)
- `audio/downstream.py` (DownstreamRouter frame accumulator and turn flush)
- `audio/echo_cancel.py` (EchoCancellation PipeWire WebRTC AEC virtual nodes and volume controls)
- `audio/__init__.py` (Audio package declarations)
- `echo_cancel.py` (Root compatibility forwarder)
- `tests/test_audio/test_engine.py` (Engine unit tests)
- `tests/test_audio/test_echo_cancel.py` (Echo cancellation unit tests)

### Rules for All Agents:
1. **DO NOT MODIFY, DELETE, OR RENAME ANY LOCKED VOICE FILE.** Any attempt to edit these files violates project invariants and will be automatically rejected by pre-commit hooks and evolution gates.
2. **DO NOT MONKEYPATCH OR OVERRIDE CORE VOICE FUNCTIONS AT RUNTIME.**
3. **EXTENSIONS ONLY (Open-Closed Principle):**
   - New audio capabilities (such as DSP filters, audio recorders, speech analyzers, hotword detectors, level meters, sound effects, external STT/TTS bridges) must be implemented **without modifying existing voice code**.
   - Use `audio/extension.py`:
     - Implement `AudioFrameProcessor` for upstream (16 kHz) or downstream (24 kHz) PCM processing.
     - Implement `AudioHook` for state change, barge-in, and turn event listeners.
     - Register extensions via `AudioExtensionRegistry` or wrap `NativeAudioEngine` using `ExtendedAudioEngine`.
     - Or create new isolated modules under `skills/`, `connectors/`, or `audio/plugins/`.

---

## 2. VERIFICATION BEFORE CLAIMS
- Never claim a task, bugfix, or feature is complete without running real automated tests.
- Run tests using `.venv/bin/pytest`.
- Run `python3 scripts/verify_voice_lock.py` to confirm voice lock integrity.
- If you touched file references or module maps, synchronize documentation using `python3 scripts/update_codebase_reference.py`.

---

## 3. REPOSITORY BOUNDARIES & SAFETY
- Do not commit secrets, tokens, or private credentials (`.env` is gitignored; use `.env.example` as template).
- Do not run unconfined destructive commands outside the workspace.
- Autonomy and evolution stages must operate within their isolated worktrees.
