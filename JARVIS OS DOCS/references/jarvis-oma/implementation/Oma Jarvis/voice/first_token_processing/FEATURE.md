# voice/first_token_processing

Provider event reception and dispatch live in shared LiveVoice.handle/receive methods. These are streaming events and PCM chunks, not necessarily text tokens. Extracts preserve the stable and legacy paths separately; each still depends on the enclosing class state, session and playback object.


## Exact code extracts

These `.py.txt` files are verbatim source slices, not standalone implementations. Full module imports and enclosing class state remain required.

- [LiveVoice.handle](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/first_token_processing/code_extracts/core__agent__LiveVoice__handle.py.txt) — [core/agent.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/session/agent.py:1496); original lines 1496–1689.
- [LiveVoice.receive](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/first_token_processing/code_extracts/core__agent__LiveVoice__receive.py.txt) — [core/agent.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/session/agent.py:1691); original lines 1691–1706.
- [LiveVoice.handle](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/first_token_processing/code_extracts/core__stable_voice__LiveVoice__handle.py.txt) — [core/stable_voice.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/session/stable_voice.py:540); original lines 540–663.
- [LiveVoice.receive](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/first_token_processing/code_extracts/core__stable_voice__LiveVoice__receive.py.txt) — [core/stable_voice.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/session/stable_voice.py:665); original lines 665–676.

## Local dependencies of the containing modules

Conservative module-level list, including optional/lazy imports; not a function-level call graph.

- [audio/downstream.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/first_speech_output/downstream.py) (voice)
- [audio/engine.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/backends/native/engine.py) (voice)
- [audio/extension.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/extensions/extension.py) (voice)
- [audio/plugins/native_backend.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/backends/native/native_backend.py) (voice)
- [audio/plugins/pipewire_backend.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/backends/pipewire/pipewire_backend.py) (voice)
- [audio/plugins/spoken_interrupt.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/interruptions/spoken_interrupt.py) (voice)
- [audio/plugins/standby.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/standby/standby.py) (voice)
- [core/audio_scheduler.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/fast_response/audio_scheduler.py) (voice)
- [core/config.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/configuration/settings/config.py) (configuration)
- [core/connection.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/recovery/connection.py) (voice)
- [core/greeting.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/greetings/greeting.py) (voice)
- [core/harness_config.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/configuration/prompts/harness_config.py) (configuration)
- [core/ipc.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/runtime/ipc/ipc.py) (runtime)
- [core/monitor_echo.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/echo_cancellation/monitor_echo.py) (voice)
- [core/response_metrics.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/response_latency/response_metrics.py) (voice)
- [core/secret_env.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/configuration/security/secret_env.py) (configuration)
- [core/speech_turn.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/turn_detection/speech_turn.py) (voice)
- [core/stable_capabilities.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/runtime/capability_services/stable_capabilities.py) (runtime)
- [core/stable_recovery.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/recovery/stable_recovery.py) (voice)
- [core/tool_dispatch.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/skill_registry/dispatch/tool_dispatch.py) (skill_registry)
- [core/vision_stream.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/vision/streaming/vision_stream.py) (vision)
- [echo_cancel.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/echo_cancellation/compatibility/echo_cancel.py) (voice)
- [orchestration/groq_tool_router.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/agents/model_routing/groq_tool_router.py) (agents)
- [proactive/attention.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/automation/policy/attention.py) (automation)
- [proactive/system_watch.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/automation/monitoring/system_watch.py) (automation)
- [skills/__init__.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/skill_registry/package_markers/skills/__init__.py) (skill_registry)
