# voice/first_speech_output

DownstreamRouter is preserved as a complete locked-source copy. Playback.prepare, _prime and run show process readiness, priming and first writes. NativeAudioEngine._output_callback owns the native callback path. A first write is not proof of acoustic output time.

## Complete original files

- [downstream.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/first_speech_output/downstream.py) ← `audio/downstream.py` — **locked voice source**

## Exact code extracts

These `.py.txt` files are verbatim source slices, not standalone implementations. Full module imports and enclosing class state remain required.

- [NativeAudioEngine._output_callback](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/first_speech_output/code_extracts/audio__engine__NativeAudioEngine___output_callback.py.txt) — [audio/engine.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/backends/native/engine.py:449); original lines 449–673.
- [Playback._prime](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/first_speech_output/code_extracts/core__stable_voice__Playback___prime.py.txt) — [core/stable_voice.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/session/stable_voice.py:145); original lines 145–158.
- [Playback.prepare](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/first_speech_output/code_extracts/core__stable_voice__Playback__prepare.py.txt) — [core/stable_voice.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/session/stable_voice.py:164); original lines 164–178.
- [Playback.run](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/first_speech_output/code_extracts/core__stable_voice__Playback__run.py.txt) — [core/stable_voice.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/session/stable_voice.py:180); original lines 180–216.

## Local dependencies of the containing modules

Conservative module-level list, including optional/lazy imports; not a function-level call graph.

- [audio/plugins/spoken_interrupt.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/interruptions/spoken_interrupt.py) (voice)
- [core/config.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/configuration/settings/config.py) (configuration)
- [core/connection.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/recovery/connection.py) (voice)
- [core/harness_config.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/configuration/prompts/harness_config.py) (configuration)
- [core/ipc.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/runtime/ipc/ipc.py) (runtime)
- [core/monitor_echo.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/echo_cancellation/monitor_echo.py) (voice)
- [core/secret_env.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/configuration/security/secret_env.py) (configuration)
- [core/speech_turn.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/turn_detection/speech_turn.py) (voice)
- [core/stable_capabilities.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/runtime/capability_services/stable_capabilities.py) (runtime)
- [core/stable_recovery.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/recovery/stable_recovery.py) (voice)
- [skills/__init__.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/skill_registry/package_markers/skills/__init__.py) (skill_registry)
