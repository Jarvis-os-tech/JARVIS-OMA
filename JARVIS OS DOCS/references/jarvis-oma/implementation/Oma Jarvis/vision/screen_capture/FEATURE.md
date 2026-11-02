# vision/screen_capture

Organized copies and related feature extracts. Original imports and shared dependencies are retained.


## Exact code extracts

These `.py.txt` files are verbatim source slices, not standalone implementations. Full module imports and enclosing class state remain required.

- [LiveVoice._capture_screen_frame](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/vision/screen_capture/code_extracts/core__agent__LiveVoice___capture_screen_frame.py.txt) — [core/agent.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/session/agent.py:526); original lines 526–572.
- [take_screenshot](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/vision/screen_capture/code_extracts/skills__system_control__take_screenshot.py.txt) — [skills/system_control.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/desktop_control/system_controls/system_control.py:1540); original lines 1540–1572.

## Local dependencies of the containing modules

Conservative module-level list, including optional/lazy imports; not a function-level call graph.

- [audio/downstream.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/first_speech_output/downstream.py) (voice)
- [audio/engine.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/backends/native/engine.py) (voice)
- [audio/extension.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/extensions/extension.py) (voice)
- [audio/plugins/native_backend.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/backends/native/native_backend.py) (voice)
- [audio/plugins/pipewire_backend.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/backends/pipewire/pipewire_backend.py) (voice)
- [audio/plugins/standby.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/standby/standby.py) (voice)
- [core/audio_scheduler.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/fast_response/audio_scheduler.py) (voice)
- [core/config.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/configuration/settings/config.py) (configuration)
- [core/connection.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/recovery/connection.py) (voice)
- [core/desktop_session.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/desktop_control/session/desktop_session.py) (desktop_control)
- [core/greeting.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/greetings/greeting.py) (voice)
- [core/harness_config.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/configuration/prompts/harness_config.py) (configuration)
- [core/ipc.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/runtime/ipc/ipc.py) (runtime)
- [core/response_metrics.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/response_latency/response_metrics.py) (voice)
- [core/secret_env.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/configuration/security/secret_env.py) (configuration)
- [core/tool_dispatch.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/skill_registry/dispatch/tool_dispatch.py) (skill_registry)
- [core/vision_stream.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/vision/streaming/vision_stream.py) (vision)
- [echo_cancel.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/echo_cancellation/compatibility/echo_cancel.py) (voice)
- [orchestration/groq_tool_router.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/agents/model_routing/groq_tool_router.py) (agents)
- [proactive/attention.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/automation/policy/attention.py) (automation)
- [proactive/system_watch.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/automation/monitoring/system_watch.py) (automation)
- [skills/__init__.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/skill_registry/package_markers/skills/__init__.py) (skill_registry)
- [skills/ground_truth.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/gui_control/action_verification/ground_truth.py) (gui_control)
- [skills/modal_healing.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/gui_control/window_recovery/modal_healing.py) (gui_control)
