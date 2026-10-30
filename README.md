# PMA Voice Only — Voice-First Linux Runtime for Omarchy

A dedicated, decoupled, ultra-fast streaming voice runtime positioned as a first-class root module in the `main` branch. It forms the foundational voice layer for transforming Omarchy into a **voice-first Linux operating system**.

## Vision & Architecture

Unlike heavy general-purpose assistant frameworks that load browser drivers, task planners, computer vision pipelines, and broad toolsets into the audio loop, **PMA Voice Only** is strictly focused on low-latency bidirectional voice conversation:

- **Zero-Tool Overhead**: Completely strips all tool declarations, browser automation, desktop shell executors, and vision streams from the voice session. Unsolicited tool calls from the model are rejected immediately without execution.
- **PipeWire Native Audio**: Uses direct PipeWire tools (`pw-record` for 16 kHz PCM microphone capture, `pw-cat` for 24 kHz low-latency playback).
- **Hard Process Interruption**: Playback runs in a dedicated `pw-cat` subprocess. When the user interrupts (or triggers `listen cancel`), the playback process is terminated instantly, dropping buffered audio on the floor without sluggish queue-draining delays.
- **Visual Loudness Metering**: Computes non-linear RMS speech level metering (`frame_level`), calibrated for responsive UI rendering (such as desktop orbs or top-bar indicators) without jittering on background room noise.
- **Local Control Socket**: Listens on a protected Unix domain socket (`~/.local/state/omarchy-voice/control.sock`, chmod `0600` inside a `0700` directory) to enable instant toggling, cancellation, and status queries from desktop shortcuts without network hops.
- **Privacy & Security by Design**: No local transcript logging, no raw audio archiving, strict environment credential loading, and automatic API key redaction in exception handling.

---

## Directory Structure

```
pma_voice_only/
├── pma_voice_only/              # Core Python package
│   ├── __init__.py              # Package init & module exports
│   ├── __main__.py              # CLI entry point (python3 -m pma_voice_only)
│   ├── audio.py                 # PipeWire audio sink (Speaker) & metering (frame_level)
│   ├── config.py                # Voice settings & credential loader
│   ├── session.py               # Local Unix control socket server & IPC client
│   └── voice.py                 # Gemini Live WebSocket streaming session
├── bin/
│   └── omarchy-voice            # Executable CLI wrapper
├── systemd/
│   └── omarchy-voice.service    # Systemd user service definition
├── desktop/
│   └── bindings.lua.example     # Hyprland hotkey configuration (Super+Shift+V)
├── configs/
│   └── config.toml.example      # Voice configuration template
├── scripts/
│   ├── install.sh               # One-click runtime installer
│   └── uninstall.sh             # Clean uninstaller
├── tests/
│   └── test_voice_only.py       # Full test suite (12 tests)
├── deployment_backup/           # Backup of pre-existing configs & manifests
├── LICENSE                      # MIT License
├── PROVENANCE.json              # Source symbol & line range provenance
├── live-checks.json             # Live hardware & network verification evidence
├── live-status.json             # Runtime state example
└── provider-probe.json          # Live provider socket handshake check
```

---

## Quick Start & Usage

### 1. In-Tree Execution
You can run and test the voice module directly from the repository root:

```bash
# Run test suite
.venv/bin/pytest pma_voice_only/tests

# Run CLI help
pma_voice_only/bin/omarchy-voice --help
# or
python3 -m pma_voice_only --help
```

### 2. System Installation
To install the runtime into `~/.local/share/pma-voice-only`, create the CLI symlink in `~/.local/bin`, and register the user service:

```bash
pma_voice_only/scripts/install.sh
```

### 3. Service Management
```bash
# Start and enable on login
systemctl --user enable --now omarchy-voice.service

# Check status
systemctl --user status omarchy-voice.service

# Stop / Disable service
systemctl --user disable --now omarchy-voice.service
```

### 4. Desktop CLI & Controls
When the service is active, control it via the Unix socket:

```bash
# Check runtime status
omarchy-voice status
omarchy-voice status --json

# Toggle listening state (mute/unmute microphone & session)
omarchy-voice listen toggle

# Stop / Start listening
omarchy-voice listen stop
omarchy-voice listen start

# Cancel active spoken response
omarchy-voice listen cancel
```

### 5. Desktop Keybinding
In Omarchy Linux (Hyprland), add the keybinding in `~/.config/hypr/bindings.lua`:

```lua
-- PMA Voice Only: Super+Shift+V to toggle listening
o.bind("SUPER + SHIFT + V", "PMA voice: toggle listening", os.getenv("HOME") .. "/.local/bin/omarchy-voice listen toggle")
```

---

## Configuration

Configuration is stored at `~/.config/pma-voice-only/config.toml` (copy from `configs/config.toml.example`):

```toml
model = "gemini-3.8-live"
voice = "Puck"
device = ""
barge_in = false
autostart_listening = true
api_key_env = "GEMINI_API_KEY"
```

Credentials are read from `~/.config/omarchy-voice/env` or the process environment (`GEMINI_API_KEY` or `GOOGLE_API_KEY`).

---

## Automated Verification

The test suite validates:
1. Pure audio modality configuration without tool schemas.
2. Strict isolation — no imports from heavy assistant packages or tool executors.
3. Unsolicited tool call rejection without execution.
4. Correct 24 kHz PCM audio chunk delivery and counting.
5. Muted session dropping of late audio frames.
6. Immediate interruption and cancellation on provider interruption signals.
7. Malformed/partial PCM frame rejection.
8. Clean teardown of capture, playback, and network sockets on stop.
9. Setup acknowledgement sequencing before microphone audio streaming.
10. API key redaction in error messages.
11. Non-voice commands disabled over the control socket.
12. Status reporting advertising only microphone, speech, playback, and interruption features.
