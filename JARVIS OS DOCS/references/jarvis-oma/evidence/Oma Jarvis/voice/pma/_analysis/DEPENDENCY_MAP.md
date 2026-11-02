# PMA voice dependency map

This is an organized source collection, not an independently runnable application. Original imports, paths, names and behavior are preserved.

## Internal imports

| Copied module | Local dependencies |
| --- | --- |
| realtime.py | `capabilities.py` (not copied), `config.py` (not copied), `feedback.py` (copied), `network.py` (copied), `persona.py` (not copied), `session.py` (copied), `tasks.py` (not copied), `tools.py` (not copied), `vision.py` (not copied) |
| live.py | `browser.py` (not copied), `capabilities.py` (not copied), `config.py` (not copied), `feedback.py` (copied), `network.py` (copied), `playback.py` (copied), `realtime.py` (copied), `security.py` (not copied), `session.py` (copied), `tasks.py` (not copied), `tools.py` (not copied), `trace.py` (not copied), `vision.py` (not copied) |
| gemini_live.py | `capabilities.py` (not copied), `config.py` (not copied), `feedback.py` (copied), `persona.py` (not copied), `realtime.py` (copied), `session.py` (copied), `tasks.py` (not copied), `tools.py` (not copied), `vision.py` (not copied) |
| playback.py | `realtime.py` (copied) |
| feedback.py | `config.py` (not copied), `security.py` (not copied) |
| session.py | `config.py` (not copied) |
| network.py | `config.py` (not copied), `trace.py` (not copied) |

## Intentionally omitted dependencies

These modules contain shared configuration, desktop/browser actions, task/vision routing, persona or general logging/security utilities. Keeping their imports does not copy their implementations.

- `src/omarchy_voice/browser.py`
- `src/omarchy_voice/capabilities.py`
- `src/omarchy_voice/cli.py`
- `src/omarchy_voice/config.py`
- `src/omarchy_voice/persona.py`
- `src/omarchy_voice/security.py`
- `src/omarchy_voice/tasks.py`
- `src/omarchy_voice/tools.py`
- `src/omarchy_voice/trace.py`
- `src/omarchy_voice/vision.py`

The original `omarchy_voice` package initialization and CLI package structure are also absent. Selected CLI/configuration sections are `.txt` excerpts, not replacement modules.

## External requirements found in the source

- Python >=3.11 and `websockets>=14,<17` are declared in the original pyproject.toml; that mixed application packaging file was not copied.
- PipeWire `pw-record` / `pw-cat` and diagnostic `pactl` calls serve microphone and playback paths.
- Optional local feedback uses `piper` + `aplay`, `espeak-ng`, or a configured TTS command; notifications use `notify-send`.
- Voice indicators require QtQuick, Quickshell and Omarchy `qs.Ui` / `qs.Commons` components. The toggle template targets Omarchy/Hyprland; the service template targets systemd.
- Provider sessions still require the source application configuration and credentials. No credentials, personal configurations, recorded audio, or runtime traces were copied.

No application modules were imported or executed during the copy. No API compatibility, device behavior or end-to-end operation is certified by byte/syntax verification.
