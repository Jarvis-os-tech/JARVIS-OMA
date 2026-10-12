# Jarvis — full-duplex voice agent for Omarchy

[![CI](https://github.com/Jarvis-os-tech/JARVIS-OMA/actions/workflows/ci.yml/badge.svg)](https://github.com/Jarvis-os-tech/JARVIS-OMA/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Gemini Live API](https://img.shields.io/badge/Gemini-Live%20API-4285F4.svg)](https://ai.google.dev/)
[![Platform](https://img.shields.io/badge/platform-Omarchy%20%2F%20Arch%20Linux-1793d1.svg)](https://archlinux.org/)

**Everything for this agent is in this folder.** Copy it anywhere on an
Omarchy/Arch Linux desktop. It has no imports from the original Omarchy AI app.

`agent.py` is the conversation agent. `echo_cancel.py` provides the audio routing,
and `skills.py` connects Gemini function calls to a dynamically discovered set of
safe Omarchy desktop controls. There are no coding workers, arbitrary shell tools,
other speech providers, wake models, mobile, or casting components.

## Run

Requirements: Python 3.12+, a Gemini API key with Live access, and working PipeWire
with `pw-record`, `pw-play`, and `pactl`. On Omarchy these audio utilities may
already be installed. No system service installation or restart is required.

Open a terminal **inside this folder**, then:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env  # optional: set your GEMINI_API_KEY
./run.sh --check
./run.sh --list-skills
./run.sh
```

Enter your Gemini API key at the hidden prompt. It is held in process memory and
not saved. An existing `GEMINI_API_KEY` environment variable also works. The agent
does not read the old project's credentials or `.env` files.

Speak when the terminal says **LIVE**. No wake word or button is needed. You can
speak while Gemini is speaking. Press **Ctrl+C** to stop microphone capture, close
the connection, stop playback and release the private audio routes. This version
uses stop/restart rather than a separate mute interface.

Optional settings and dynamic configuration:

```sh
./run.sh --voice Aoede --transcripts
./run.sh --model gemini-3.8-live
./run.sh --agent-name "Friday"
./run.sh --config ./config.toml
./run.sh --system-instruction "Custom prompt..."
pactl list short sources
./run.sh --microphone YOUR_PHYSICAL_SOURCE_NAME
./run.sh --no-skills
```

Settings can also be loaded automatically from a configuration file (`~/.config/jarvis-oma/config.toml`,
`./config.toml`, or `./config.json`; see `config.toml.example` for all options), or via environment
variables (`JARVIS_AGENT_NAME`, `JARVIS_VOICE`, `JARVIS_MODEL`, `JARVIS_CONFIG`, `GEMINI_LIVE_MODEL`).

## Dynamic Omarchy skills

Skills are enabled by default. At startup Jarvis reads JSON manifests from
`skill_manifests/`, validates their names and strict argument schemas, and gives
the discovered declarations to Gemini Live. The bundled manifests enable:

- **Application discovery & launch**: `list_applications`, `open_application` (XDG-compliant)
- **Web browsing**: `open_website` (safe public HTTP/HTTPS URLs)
- **Audio & display controls**: `adjust_volume`, `adjust_brightness`
- **Window & workspace management**: `switch_workspace`, `manage_window` (fullscreen, close, minimize, float, center, maximize via `hyprctl`)
- **System controls**: `lock_screen` (`loginctl`), `take_screenshot` (`grim`), `system_power` (safe sleep/hibernate via `systemctl`)
- **Network controls**: `toggle_wifi` (`nmcli`), `toggle_bluetooth` (`rfkill`)
- **Clipboard**: `read_clipboard` (`wl-paste`), `write_clipboard` (`wl-copy`)
- **Notifications**: `show_notification` with dynamic application name (`notify-send`)
- **Native reminders**: `create_reminder`, `list_reminders`, `cancel_reminder`, and `clear_reminders` through Omarchy's own reminder system
- **Todo List plugin**: create, search, edit, move, complete, reopen, delete, and clear completed tasks in the installed Omarchy Todo List widget

The manifests are dynamic configuration rather than executable plugins. Adapters self-declare
their required system commands (`ADAPTER_COMMANDS`). When a command is not installed on the system,
skills that depend on it are excluded gracefully at startup with a warning instead of failing during a call.

To replace the bundled set with manifests from another directory:

```sh
./run.sh --skill-dir /absolute/path/to/skill-manifests --check
./run.sh --skill-dir /absolute/path/to/skill-manifests
```

Manifests fail closed: an invalid file, duplicate name, unknown adapter,
unsupported schema, or empty directory prevents startup. `--no-skills` restores
conversation-only mode. Application names must exactly match an installed desktop
entry. Websites are limited to HTTP(S), reject embedded credentials, and block
localhost and private IP literals.

## Full-duplex flow

Reminders created by voice use Omarchy's native `omarchy reminder` system, so
JARVIS and the Omarchy reminder UI share the same reminders. You can say, for
example, “remind me in 30 minutes to check the oven” or “list my reminders”.

```text
Physical microphone → private PipeWire AEC source → 16 kHz PCM → Gemini Live
Physical speaker    ← private PipeWire AEC sink   ← 24 kHz PCM ← Gemini Live
```

Three concurrent workers send microphone audio, receive Gemini events, and play
speech. Capture stays active while playback runs; there is no silence gate that
turns the microphone off during Gemini's reply. Google Live uses a WebSocket
connection through the GenAI SDK; full-duplex does not imply WebRTC transport.

Gemini's activity detection interrupts a response when you speak. On the server's
interruption event the agent terminates its playback process, empties the queued
PCM, and advances a generation counter so pending old-turn audio cannot restart
playback. A fresh player handles the next response. Interruption latency includes
server detection and network latency; there is no measured sub-100 ms guarantee.

The PipeWire echo-cancellation module uses software WebRTC AEC. Audio playback is
routed through its reference sink and capture through its clean microphone source.
These are private routes; system defaults are unchanged. The agent fails to start
if AEC setup fails instead of silently using a raw microphone with speakers.
Actual echo rejection depends on the microphone/speaker setup and needs testing.

Playback uses small chunks and a short lead buffer. The PCM queue is bounded to
ten seconds. If the consumer cannot keep up, the connection is torn down and
retried rather than blocking reception of interruption events or growing memory
without a bound. This can cause an audible gap under sustained playback overload.

## Reconnection and state

Server resumption handles remain in RAM and are offered on subsequent connections.
Context-window compression is enabled. Server connection-renewal events trigger
a reconnect. Other errors have exponential backoff capped at 30 seconds and a
configurable retry budget (`--retries 5` by default). Authentication/configuration
failures stop the process. An invalid resume handle is discarded with a warning;
that retry starts a fresh conversation. Reconnects are not gapless.

Microphone capture and playback are closed between attempts. Successful resumption
depends on the server; stopping the program discards the handle. No local audio
recordings or conversation history are written. Audio is sent to Google while
LIVE. Transcript fragments are printed only with `--transcripts`; your terminal
may retain scrollback. A cloud connection and its usage costs are required.

## Files and extension points

- `agent.py`: settings, capture, provider connection, Gemini tool-call routing,
  event processing, playback, interruption, retry and cleanup.
- `skills.py`: manifest validation, runtime argument validation, safe Omarchy
  adapters, application discovery, bounded command execution and URL policy.
- `skill_manifests/omarchy-defaults.json`: bundled dynamic skill declarations.
- `echo_cancel.py`: session-owned PipeWire routing adapted from the existing
  Omarchy voice code. Includes optional gain management, unused by the default CLI.
- `config.py`: dynamic configuration loader supporting TOML, JSON, and `JARVIS_*` environment variables.
- `requirements.txt`: the tested Google GenAI SDK version.
- `run.sh`: starts this folder's virtual environment when present.
- `test_agent.py`, `test_echo_cancel.py`, `test_skills.py`, `test_config.py`: offline unit and regression tests.
- `LICENSE`: original MIT notice retained for reused audio code.

## Verification

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s . -p 'test_*.py' -v
./run.sh --check
```

The tests simulate external processes and cloud events. They cover simultaneous
input/output, all audio parts in an event, old-audio cancellation including a
process-creation race, queue bounds, multi-turn reception, worker cleanup,
resumption state, dynamic manifest validation, strict tool arguments, safe adapter
routing, URL policy and echo route cleanup. `--check` validates commands and SDK
configuration without capturing audio or opening a network connection.

See `TEST_RESULTS.txt` for the actual test run. A real Gemini conversation,
echo rejection, end-to-end interruption timing, connection expiry and sustained
CPU/RAM usage have **not** been tested on live hardware for this new agent.

## Source references

Extracted from the desktop audio design of Omarchy AI; unrelated app integrations
were removed. The new transport loop follows Google's current
[Live API capabilities](https://ai.google.dev/gemini-api/docs/live-api/capabilities)
and [session management](https://ai.google.dev/gemini-api/docs/live-api/session-management)
documentation, checked on 2026-10-12. The local Gemini skill describes an older
model generation; current official documentation supplies the default used here.
