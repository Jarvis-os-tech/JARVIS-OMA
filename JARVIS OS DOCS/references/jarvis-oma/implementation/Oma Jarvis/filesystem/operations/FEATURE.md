# filesystem/operations

Organized copies and related feature extracts. Original imports and shared dependencies are retained.

## Complete original files

- [README.md](../../../../../jarvis-os/implementation/filesystem/README.md) ← `filesystem/README.md`
- [__init__.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/filesystem/operations/__init__.py) ← `filesystem/__init__.py`
- [filesystem.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/filesystem/operations/filesystem.py) ← `filesystem/filesystem.py`

## Exact code extracts

These `.py.txt` files are verbatim source slices, not standalone implementations. Full module imports and enclosing class state remain required.

- [DesktopSkills._adapter_append_file](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/filesystem/operations/code_extracts/skills__skills__DesktopSkills___adapter_append_file.py.txt) — [skills/skills.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/skill_registry/registry/skills.py:1432); original lines 1432–1433.
- [DesktopSkills._adapter_copy_path](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/filesystem/operations/code_extracts/skills__skills__DesktopSkills___adapter_copy_path.py.txt) — [skills/skills.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/skill_registry/registry/skills.py:1441); original lines 1441–1442.
- [DesktopSkills._adapter_delete_path](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/filesystem/operations/code_extracts/skills__skills__DesktopSkills___adapter_delete_path.py.txt) — [skills/skills.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/skill_registry/registry/skills.py:1447); original lines 1447–1448.
- [DesktopSkills._adapter_edit_file](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/filesystem/operations/code_extracts/skills__skills__DesktopSkills___adapter_edit_file.py.txt) — [skills/skills.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/skill_registry/registry/skills.py:1453); original lines 1453–1454.
- [DesktopSkills._adapter_inspect_path](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/filesystem/operations/code_extracts/skills__skills__DesktopSkills___adapter_inspect_path.py.txt) — [skills/skills.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/skill_registry/registry/skills.py:1450); original lines 1450–1451.
- [DesktopSkills._adapter_list_files](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/filesystem/operations/code_extracts/skills__skills__DesktopSkills___adapter_list_files.py.txt) — [skills/skills.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/skill_registry/registry/skills.py:1414); original lines 1414–1416.
- [DesktopSkills._adapter_make_directory](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/filesystem/operations/code_extracts/skills__skills__DesktopSkills___adapter_make_directory.py.txt) — [skills/skills.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/skill_registry/registry/skills.py:1435); original lines 1435–1436.
- [DesktopSkills._adapter_move_path](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/filesystem/operations/code_extracts/skills__skills__DesktopSkills___adapter_move_path.py.txt) — [skills/skills.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/skill_registry/registry/skills.py:1438); original lines 1438–1439.
- [DesktopSkills._adapter_read_file](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/filesystem/operations/code_extracts/skills__skills__DesktopSkills___adapter_read_file.py.txt) — [skills/skills.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/skill_registry/registry/skills.py:1418); original lines 1418–1419.
- [DesktopSkills._adapter_search_file_content](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/filesystem/operations/code_extracts/skills__skills__DesktopSkills___adapter_search_file_content.py.txt) — [skills/skills.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/skill_registry/registry/skills.py:1425); original lines 1425–1427.
- [DesktopSkills._adapter_search_files](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/filesystem/operations/code_extracts/skills__skills__DesktopSkills___adapter_search_files.py.txt) — [skills/skills.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/skill_registry/registry/skills.py:1421); original lines 1421–1423.
- [DesktopSkills._adapter_trash_path](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/filesystem/operations/code_extracts/skills__skills__DesktopSkills___adapter_trash_path.py.txt) — [skills/skills.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/skill_registry/registry/skills.py:1444); original lines 1444–1445.
- [DesktopSkills._adapter_write_file](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/filesystem/operations/code_extracts/skills__skills__DesktopSkills___adapter_write_file.py.txt) — [skills/skills.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/skill_registry/registry/skills.py:1429); original lines 1429–1430.

## Local dependencies of the containing modules

Conservative module-level list, including optional/lazy imports; not a function-level call graph.

- [agent_orchestrator.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/agents/compatibility/agent_orchestrator.py) (agents)
- [config.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/configuration/compatibility/config.py) (configuration)
- [connectors/__init__.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/integrations/package_markers/connectors/__init__.py) (integrations)
- [connectors/github.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/integrations/github/github.py) (integrations)
- [connectors/google_workspace.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/integrations/google_workspace/google_workspace.py) (integrations)
- [connectors/internet_search.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/integrations/search/internet_search.py) (integrations)
- [connectors/phone.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/integrations/phone/phone.py) (integrations)
- [core/secret_env.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/configuration/security/secret_env.py) (configuration)
- [core/tool_dispatch.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/skill_registry/dispatch/tool_dispatch.py) (skill_registry)
- [core/workers.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/runtime/workers/workers.py) (runtime)
- [filesystem/__init__.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/filesystem/operations/__init__.py) (filesystem)
- [filesystem/filesystem.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/filesystem/operations/filesystem.py) (filesystem)
- [filesystem/task_runner.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/filesystem/task_runner/task_runner.py) (filesystem)
- [memory/codes-dev/jarvis_memory/bridge.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/memory/services/bridge.py) (memory)
- [memory/codes-dev/jarvis_memory/paths.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/memory/shared/paths.py) (memory)
- [orchestration/desktop_execution.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/agents/execution/desktop_execution.py) (agents)
- [orchestration/evolution.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/agents/development/evolution.py) (agents)
- [orchestration/tool_tiers.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/skill_registry/tiering/tool_tiers.py) (skill_registry)
- [proactive/runtime.py](../../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/automation/runtime/runtime.py) (automation)
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
