# Universal Linux Voice

A standalone copy of the frozen JARVIS PC voice engine. Only voice source, audio assets, voice tests, packaging and documentation are included. No memory engine, student tools, desktop control, Android, UI, personal configuration, API keys or user recordings are included.

The original JARVIS source, configuration and running service are untouched. This package uses `universal_voice`, `~/.config/universal-voice` and a separate private `universal-voice/control.sock`. Do not run both voice assistants simultaneously against the same microphone: they can hear each other's speakers.

## Compatibility

Designed for Linux desktop distributions with Python 3.11+, PipeWire, its PulseAudio compatibility server, WirePlumber, a microphone and speakers. Ubuntu 24.04+, current Mint, Debian, Arch and Fedora can supply these components. GNOME/KDE/Xfce/Cinnamon and X11/Wayland are not coupled to the engine. Foreground operation does not need systemd. Other Linux distributions can work when the same commands and Python dependencies are available.

This is source portability, not a claim of tested support on every distribution or CPU. Python/ONNX/Vosk wheel availability depends on architecture and Python version; x86_64 with Python 3.11–3.13 is the intended initial target. Prefer Python 3.11/3.12 if a newer interpreter cannot resolve native wheels. Alpine/musl, headless servers, WSL, Windows and macOS are not validated. PulseAudio-only systems need a working PipeWire desktop session first; this installer does not replace an audio server.

## Install system dependencies

Install only the command matching your distribution. Review your package manager's proposed changes: enabling PipeWire may replace PulseAudio. Log out/in after an intentional audio-server change. Existing PipeWire desktops may already have everything.

Ubuntu / Mint / Debian:

```bash
sudo apt update
sudo apt install python3 python3-venv pipewire pipewire-bin pipewire-pulse wireplumber pulseaudio-utils libportaudio2
```

Arch / EndeavourOS / Manjaro (use a fully updated system):

```bash
sudo pacman -Syu python pipewire pipewire-audio pipewire-pulse wireplumber libpulse portaudio
```

Fedora:

```bash
sudo dnf install python3 python3-pip pipewire pipewire-utils pipewire-pulseaudio wireplumber pulseaudio-utils portaudio
```

Package references: [Ubuntu tools](https://packages.ubuntu.com/pulseaudio-utils), [Arch PipeWire](https://archlinux.org/packages/extra/x86_64/pipewire-audio/), [Arch pactl provider](https://wiki.archlinux.org/title/PipeWire), [Fedora tools](https://packages.fedoraproject.org/pkgs/pipewire/pipewire-utils/).

## Install and run

Extract this directory anywhere writable, then open a terminal in it:

```bash
./install.sh
./run.sh --check
```

The installer creates a local virtual environment and installs this package. It does not install system packages, enable services, change microphone mute, or access the original JARVIS environment. Internet is needed to download Python dependencies.

Choose a Gemini Live model available to your account; provider/model availability can change. The copied model name in the sample is inherited from the source installation and is not an availability guarantee. Set the key for this terminal without placing it in shell history:

```bash
read -rsp 'Gemini API key: ' GEMINI_API_KEY; echo
export GEMINI_API_KEY
./run.sh --model YOUR_LIVE_MODEL
```

Microphone audio is sent to Gemini while connected and listening. Ctrl+C stops the program. Config is optional; to adjust voice, microphone, speaker or pause duration:

```bash
mkdir -p ~/.config/universal-voice
cp -n config.example.toml ~/.config/universal-voice/config.toml
```

Never copy your original JARVIS configuration wholesale: memory/control settings are intentionally unsupported. For a different Python, use `PYTHON=python3.12 ./install.sh`.

In another terminal:

```bash
./run.sh status --json
./run.sh listen stop
./run.sh listen start
./run.sh standby
./run.sh wake
./run.sh send 'Hello, explain what you can do.'
```

Standby suspends cloud speech and uses the local wake listener. The bundled openWakeWord dependency supplies Hey Jarvis; Hello Jarvis additionally requires a separately obtained compatible Vosk English model at `JARVIS_WAKE_MODEL`. No speech-model download is hidden in startup. If local wake models are unavailable, use the explicit `wake` command. Ordinary conversation uses native Live audio, not offline transcription.

## Included behavior

Streaming PCM input/output; local Silero speech gating; 1.2-second pause tolerance; evidence-gated barge-in and playback cancellation; echo cancellation where the installed PipeWire supports it; sparse listening cues; cached acknowledgements; native expressive audio; reconnect/recovery; private local control socket; optional standby. Listening cues require active AEC and a sufficiently long narrative with a safe pause.

The voice engine's acknowledgement selector and event-grounded progress renderer are included for integrations. No task executor is bundled, so this standalone instance does not announce research/coding progress or pretend to open applications. Unexpected provider tool calls are rejected. The external Needle/Whistle command worker source is retained as voice reference but disabled; configuration cannot enable the unbundled desktop integration.

## Verification

Build verification on the development Linux host: 68 copied/adapted voice and portability tests passed both from source and against an independently installed wheel; local dependency/VAD preflight passed; shell syntax passed; original voice-lock verifier passed before and after extraction. No live microphone/cloud session, clean dependency installation, or Ubuntu/Mint/Fedora VM run was performed. One executor-specific regression was replaced by voice-only tool rejection coverage because the task executor is deliberately absent.

```bash
.venv/bin/python -m pip install pytest pytest-asyncio
.venv/bin/python -m pytest -q
```

Tests cover turn timing, backchannels, interruption, playback cancellation, cache integrity, independent configuration, absence of parent application imports, provider startup and rejection of unconnected tools. `--check` imports dependencies and loads the local VAD without capture or network. It does not prove that the audio server, microphone, speakers, API key or model works.

Manual acceptance on each target distro: check microphone mute; run a short conversation; pause mid-sentence; interrupt a spoken answer; narrate for 10+ seconds with pauses; enter standby and wake; disconnect/reconnect networking; stop with Ctrl+C. If AEC is unavailable use headphones. Confirm output is audible and microphone routing stays correct after reconnect.

## Optional autostart

Run in the foreground first. A systemd user unit template is provided in `universal-voice.service.example`; set its absolute install path before installing it under `~/.config/systemd/user/universal-voice.service`. No service is installed or enabled automatically. Non-systemd desktops can autostart `run.sh` using their normal session mechanism. Never use the original `jarvis-voice.service` for this copy.

See LICENSE, ATTRIBUTION.md and ORIGIN.json for source provenance.
