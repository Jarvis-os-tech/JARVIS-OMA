# PMA voice source copy

Source: `/home/g0pi/Projects/pma/omarchy-voice`.

30 complete files copied byte-for-byte, plus 47 exact labelled excerpts. Original sources, running JARVIS and existing organized copies were not edited. Current working-tree contents were copied, including the existing uncommitted Gemini voice module.

This folder contains voice implementation, voice-specific tests, controls, indicators, configuration excerpts, diagnostics and the original MIT license. It is an organized source collection; imports and installation paths were not rewritten. It cannot run independently as arranged.

## Voice features

| Folder | Contents |
| --- | --- |
| [engines/](engines/README.md) | Complete voice engines, including their existing tool-call and recovery orchestration. They still depend on excluded application modules. |
| [capture/](capture/README.md) | Exact microphone-loop excerpts; full owning files are in engines/. |
| [interruptions/](interruptions/README.md) | Exact cancellation, playback interruption and queue cleanup excerpts. Gemini interruption handling is in the incoming-message excerpt under first_token_processing/code_extracts/. |
| [first_token_processing/](first_token_processing/README.md) | Incoming transcript/audio event handlers. No separate generalized first-LLM-token engine was found. These handlers also contain associated orchestration. |
| [first_speech_output/](first_speech_output/README.md) | Audio delivery and device-write code. Device latency is estimated; actual sound onset is not measured. |
| [fast_response/](fast_response/README.md) | Existing jitter-buffer priming and late-frame waiting logic. No speed optimization or new latency claim is introduced. |
| [turn_detection/](turn_detection/README.md) | Server VAD configuration and manual audio-buffer commit excerpts. |
| [recovery/](recovery/README.md) | Exact voice connection/retry and lifecycle excerpts. Complete implementations remain in engines/. |
| [configuration/](configuration/README.md) | Only exact voice-related fields and template sections from mixed configuration files. These excerpts cannot replace the full Config class. |
| [playback/](playback/README.md) | Unchanged Live PCM speaker module and tests; exact Realtime Speaker class excerpt for the shared Gemini/Realtime player. |
| [spoken_feedback/](spoken_feedback/README.md) | Unchanged local speech, notification and level/state feedback module. |
| [controls/](controls/README.md) | Unchanged voice control socket, shell commands and keybinding template; exact selected CLI and phrase-test excerpts. |
| [voice_indicators/](voice_indicators/README.md) | Voice-only orb and indicator code plus level computation excerpt. No general desktop-control implementation was copied. |
| [connection_diagnostics/](connection_diagnostics/README.md) | Unchanged voice websocket monitoring module and tests. Ping/Pong measures transport RTT, not inference latency. |
| [echo_cancellation/](echo_cancellation/README.md) | Unchanged PipeWire echo-cancel template plus source/sink risk-check excerpt. Nothing installed. |
| [response_latency/](response_latency/README.md) | Voice-session trace summary and exact timing excerpts. first_output_audio starts at the latest received input transcript fragment and ends at incoming non-silent PCM; it is not microphone-end-to-audible-speech latency. |
| [service/](service/README.md) | Original daemon service template, with original installation paths. Not installed or enabled. |
| [diagnostics/](diagnostics/README.md) | Original opt-in protocol probe and exact voice-log CLI excerpt. Probe was not run. |

## Scope and provenance

- Each complete module is stored once. Feature excerpts intentionally repeat the relevant original lines and are labelled `.py.txt` / `.txt`; no function was rewritten or extracted into a new runnable module.
- Voice engines retain their original desktop/tool orchestration because stripping it would change code. Separate browser, desktop tools, task workers, planner, camera/vision, workspace-file and discovery implementations were excluded.
- Full mixed `config.py`, `cli.py`, generic security/logging and persona modules were excluded. The dependency map lists required shared modules; voice-specific CLI/config sections are exact excerpts only.
- Installers, general application launchers, hooks, credentials, environments, private data, generated caches, actual audio and traces were not copied. Service/keybinding/echo templates are inactive copies.
- No code was removed, repaired, integrated, installed or launched. Source documentation is treated as reference material, not instructions to execute.

## Analysis

- [Source map](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/pma/_analysis/SOURCE_MAP.csv)
- [Dependency map](../../../../evidence/Oma%20Jarvis/voice/pma/_analysis/DEPENDENCY_MAP.md)
- [Copy manifest, excerpt ranges and exclusions](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/pma/_analysis/copy_manifest.json)
- [Python import inventory](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/pma/_analysis/import_dependencies.json)
- [Verification](../../../../evidence/Oma%20Jarvis/voice/pma/_analysis/VERIFICATION.md)
- [Original MIT license](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/pma/LICENSE)
