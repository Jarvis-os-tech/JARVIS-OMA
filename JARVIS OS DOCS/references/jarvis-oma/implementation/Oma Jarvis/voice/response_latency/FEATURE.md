# voice/response_latency

ResponseMetrics measures recognized-input-update to first received PCM/tool dispatch. The stable runtime also exposes first speech upload and first chunk-to-write times. See the exact status/send_audio extracts. These different clocks must not be combined into a claimed end-to-end TTFT/TTFS measurement.

## Complete original files

- [response_metrics.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/response_latency/response_metrics.py) ← `core/response_metrics.py`

## Exact code extracts

These `.py.txt` files are verbatim source slices, not standalone implementations. Full module imports and enclosing class state remain required.

- [LiveVoice.send_audio](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/response_latency/code_extracts/core__stable_voice__LiveVoice__send_audio.py.txt) — [core/stable_voice.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/session/stable_voice.py:418); original lines 418–459.
- [LiveVoice.status](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/response_latency/code_extracts/core__stable_voice__LiveVoice__status.py.txt) — [core/stable_voice.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/session/stable_voice.py:266); original lines 266–303.

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
