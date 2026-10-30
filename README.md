# JARVIS Voice Core — Sovereign Voice Foundation for JARVIS OS

A sovereign, low-latency, full-duplex streaming voice runtime forming the core foundation for transforming Omarchy into **JARVIS OS** (a voice-first personal AI operating system).

## Architecture & Principles

JARVIS Voice Core provides an ambient acoustic ear and real-time conversational voice loop directly integrated into Linux and PipeWire:

- **Ambient Acoustic Ear**: Continuous PipeWire audio capture (16 kHz PCM) with local Silero VAD speech detection.
- **Full-Duplex Gemini Live**: Low-latency bidirectional streaming session with natural turn taking and real-time audio replies.
- **Hard Barge-In (<25ms)**: Subprocess playback kill terminates speaking instantly when speech energy exceeds threshold, dropping buffered audio on the floor without queue-draining delay.
- **Hardened Error Recovery**: Exponential backoff with 60-second cooldown floor on HTTP 429, session resume retention across setup timeouts, and quiet-frame continuity across VAD windows.
- **Local Control Socket**: Listens on a protected Unix domain socket (`$XDG_RUNTIME_DIR/jarvis/control.sock`, chmod `0600`) for status queries, mute toggle, and cancel signals.
- **Inviolable Hotkey Law**: `SUPER + H` is preserved exclusively for system dictation (`linux-voice toggle`).

---

## Directory Structure

```
jarvis_voice/
├── __init__.py              # Package init & version
├── __main__.py              # CLI entry point (python3 -m jarvis_voice)
├── config.py                # XDG config, paths, and environment credential loader
├── daemon.py                # LiveVoice & Gemini Live duplex streaming loop
├── ipc.py                   # Protected Unix domain control socket server
├── playback.py              # PipeWire playback engine & generation-fenced buffer
├── recovery.py              # Hardened connection recovery logic
└── speech.py                # Silero VAD, SpeechTurnGate & SpokenInterruption
bin/
└── jarvis-voice             # Executable CLI wrapper
systemd/
└── jarvis-voice.service     # Systemd user service definition
scripts/
├── install.sh               # System installer
└── uninstall.sh             # Clean uninstaller
tests/
├── test_cli.py              # CLI test suite
├── test_config.py           # Configuration tests
├── test_daemon.py           # Voice daemon tests
├── test_integration.py      # Integration tests
├── test_ipc.py              # Control socket tests
├── test_playback.py         # Playback engine tests
├── test_recovery.py         # Recovery & backoff tests
└── test_speech.py           # Turn gate & VAD continuity tests
```

---

## Quick Start & Verification

### 1. Run Verification Suite
```bash
.venv/bin/pytest tests/ -v
```

### 2. Check System Readiness
```bash
bin/jarvis-voice --check
```

### 3. Install & Enable Service
```bash
scripts/install.sh
systemctl --user enable --now jarvis-voice.service
```

### 4. CLI Control
```bash
jarvis-voice status
jarvis-voice status --json
jarvis-voice listen toggle
jarvis-voice listen cancel
```
