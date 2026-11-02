# vision/camera_capture

Organized copies and related feature extracts. Original imports and shared dependencies are retained.


## Exact code extracts

These `.py.txt` files are verbatim source slices, not standalone implementations. Full module imports and enclosing class state remain required.

- [LiveVoice._capture_camera_frame](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/vision/camera_capture/code_extracts/core__agent__LiveVoice___capture_camera_frame.py.txt) — [core/agent.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/session/agent.py:574); original lines 574–651.
- [DesktopSkills._adapter_capture_camera_frame](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/vision/camera_capture/code_extracts/skills__skills__DesktopSkills___adapter_capture_camera_frame.py.txt) — [skills/skills.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/skill_registry/registry/skills.py:2063); original lines 2063–2096.

## Local dependencies of the containing modules

Conservative module-level list, including optional/lazy imports; not a function-level call graph.

- [agent_orchestrator.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/agents/compatibility/agent_orchestrator.py) (agents)
- [audio/downstream.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/first_speech_output/downstream.py) (voice)
- [audio/engine.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/backends/native/engine.py) (voice)
- [audio/extension.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/extensions/extension.py) (voice)
- [audio/plugins/native_backend.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/backends/native/native_backend.py) (voice)
- [audio/plugins/pipewire_backend.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/backends/pipewire/pipewire_backend.py) (voice)
- [audio/plugins/standby.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/standby/standby.py) (voice)
- [config.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/configuration/compatibility/config.py) (configuration)
- [connectors/__init__.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/integrations/package_markers/connectors/__init__.py) (integrations)
- [connectors/github.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/integrations/github/github.py) (integrations)
- [connectors/google_workspace.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/integrations/google_workspace/google_workspace.py) (integrations)
- [connectors/internet_search.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/integrations/search/internet_search.py) (integrations)
- [connectors/phone.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/integrations/phone/phone.py) (integrations)
- [core/audio_scheduler.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/fast_response/audio_scheduler.py) (voice)
- [core/config.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/configuration/settings/config.py) (configuration)
- [core/connection.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/recovery/connection.py) (voice)
- [core/greeting.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/greetings/greeting.py) (voice)
- [core/harness_config.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/configuration/prompts/harness_config.py) (configuration)
- [core/ipc.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/runtime/ipc/ipc.py) (runtime)
- [core/response_metrics.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/response_latency/response_metrics.py) (voice)
- [core/secret_env.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/configuration/security/secret_env.py) (configuration)
- [core/tool_dispatch.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/skill_registry/dispatch/tool_dispatch.py) (skill_registry)
- [core/vision_stream.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/vision/streaming/vision_stream.py) (vision)
- [core/workers.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/runtime/workers/workers.py) (runtime)
- [echo_cancel.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/voice/echo_cancellation/compatibility/echo_cancel.py) (voice)
- [filesystem/__init__.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/filesystem/operations/__init__.py) (filesystem)
- [memory/codes-dev/jarvis_memory/bridge.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/memory/services/bridge.py) (memory)
- [memory/codes-dev/jarvis_memory/paths.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/memory/shared/paths.py) (memory)
- [orchestration/desktop_execution.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/agents/execution/desktop_execution.py) (agents)
- [orchestration/evolution.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/agents/development/evolution.py) (agents)
- [orchestration/groq_tool_router.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/agents/model_routing/groq_tool_router.py) (agents)
- [orchestration/tool_tiers.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/skill_registry/tiering/tool_tiers.py) (skill_registry)
- [proactive/attention.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/automation/policy/attention.py) (automation)
- [proactive/runtime.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/automation/runtime/runtime.py) (automation)
- [proactive/system_watch.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/automation/monitoring/system_watch.py) (automation)
- [scripts/jarvis_mode.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/deployment/modes/jarvis_mode.py) (deployment)
- [skills/__init__.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/skill_registry/package_markers/skills/__init__.py) (skill_registry)
- [skills/action_verification.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/gui_control/action_verification/action_verification.py) (gui_control)
- [skills/domains/github.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/integrations/github/adapters/github.py) (integrations)
- [skills/domains/orchestration.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/agents/adapters/orchestration.py) (agents)
- [skills/domains/workspace.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/integrations/google_workspace/adapters/workspace.py) (integrations)
- [skills/errors.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/skill_registry/errors/errors.py) (skill_registry)
- [skills/ground_truth.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/gui_control/action_verification/ground_truth.py) (gui_control)
- [skills/gui_control.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/gui_control/accessibility/gui_control.py) (gui_control)
- [skills/input_bar.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/interface/text_input/input_bar.py) (interface)
- [skills/system_control.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/desktop_control/system_controls/system_control.py) (desktop_control)
- [skills/system_extensions.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/desktop_control/extensions/system_extensions.py) (desktop_control)
- [skills/system_information.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/desktop_control/information/system_information.py) (desktop_control)
- [system_control.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/desktop_control/compatibility/system_control.py) (desktop_control)
- [task_runner.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/filesystem/compatibility/task_runner.py) (filesystem)
- [test_bar.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/interface/text_input/compatibility/test_bar.py) (interface)
