# agents

Delegation, execution backends, model routing, development jobs and harness integrations.

**Source snapshot:** imports and original behavior are preserved; this folder is not yet an independent package.

## Features

Feature folders contain complete original files, related tests/manifests and exact code extracts.

- [adapters](adapters/FEATURE.md)
- [compatibility](compatibility/FEATURE.md)
- [delegation](delegation/FEATURE.md)
- [delegation/tools](delegation/tools/FEATURE.md)
- [development](development/FEATURE.md)
- [development/tools](development/tools/FEATURE.md)
- [execution](execution/FEATURE.md)
- [harness](harness/FEATURE.md)
- [model_routing](model_routing/FEATURE.md)
- [model_routing/tools](model_routing/tools/FEATURE.md)
- [personas](personas/FEATURE.md)

## File index

| Original path | Organized copy |
|---|---|
| `agent_orchestrator.py` | [compatibility/agent_orchestrator.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/agents/compatibility/agent_orchestrator.py) |
| `docs/autonomous-orchestration.md` | [docs/docs/autonomous-orchestration.md](../../docs/autonomous-orchestration.md) |
| `docs/capability-development.md` | [docs/docs/capability-development.md](../../docs/capability-development.md) |
| `docs/desktop-execution.md` | [docs/docs/desktop-execution.md](../../docs/desktop-execution.md) |
| `docs/model-routing.md` | [docs/docs/model-routing.md](../../docs/model-routing.md) |
| `orchestration/README.md` | [package_markers/orchestration/README.md](../../../../jarvis-os/implementation/orchestration/README.md) |
| `orchestration/__init__.py` | [package_markers/orchestration/__init__.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/agents/package_markers/orchestration/__init__.py) |
| `orchestration/agent_orchestrator.py` | [delegation/agent_orchestrator.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/agents/delegation/agent_orchestrator.py) |
| `orchestration/desktop_execution.py` | [execution/desktop_execution.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/agents/execution/desktop_execution.py) |
| `orchestration/evolution.py` | [development/evolution.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/agents/development/evolution.py) |
| `orchestration/execution_backend.py` | [execution/execution_backend.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/agents/execution/execution_backend.py) |
| `orchestration/groq_tool_router.py` | [model_routing/groq_tool_router.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/agents/model_routing/groq_tool_router.py) |
| `orchestration/harness2_adapter.py` | [harness/harness2_adapter.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/agents/harness/harness2_adapter.py) |
| `orchestration/model_policy.py` | [model_routing/model_policy.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/agents/model_routing/model_policy.py) |
| `orchestration/model_routes.py` | [model_routing/model_routes.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/agents/model_routing/model_routes.py) |
| `orchestration/personas.py` | [personas/personas.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/agents/personas/personas.py) |
| `scripts/check_model_access.py` | [model_routing/tools/check_model_access.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/agents/model_routing/tools/check_model_access.py) |
| `scripts/develop.py` | [development/tools/develop.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/agents/development/tools/develop.py) |
| `scripts/test_agent_delegation.py` | [delegation/tools/test_agent_delegation.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/agents/delegation/tools/test_agent_delegation.py) |
| `skill_manifests/agent-orchestration.json` | [delegation/manifests/canonical/agent-orchestration.json](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/agents/delegation/manifests/canonical/agent-orchestration.json) |
| `skill_manifests/development.json` | [development/manifests/canonical/development.json](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/agents/development/manifests/canonical/development.json) |
| `skill_manifests/model-processing.json` | [model_routing/manifests/canonical/model-processing.json](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/agents/model_routing/manifests/canonical/model-processing.json) |
| `skills/domains/orchestration.py` | [adapters/orchestration.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/agents/adapters/orchestration.py) |
| `skills/manifests/agent-orchestration.json` | [delegation/manifests/legacy_mirror/agent-orchestration.json](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/agents/delegation/manifests/legacy_mirror/agent-orchestration.json) |
| `skills/manifests/development.json` | [development/manifests/legacy_mirror/development.json](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/agents/development/manifests/legacy_mirror/development.json) |
| `skills/manifests/model-processing.json` | [model_routing/manifests/legacy_mirror/model-processing.json](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/agents/model_routing/manifests/legacy_mirror/model-processing.json) |
| `tests/test_orchestration/test_agent_orchestrator.py` | [delegation/tests/test_orchestration/test_agent_orchestrator.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/agents/delegation/tests/test_orchestration/test_agent_orchestrator.py) |
| `tests/test_orchestration/test_autonomous_goals.py` | [validation/tests/test_orchestration/test_autonomous_goals.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/agents/validation/tests/test_orchestration/test_autonomous_goals.py) |
| `tests/test_orchestration/test_desktop_execution.py` | [execution/tests/test_orchestration/test_desktop_execution.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/agents/execution/tests/test_orchestration/test_desktop_execution.py) |
| `tests/test_orchestration/test_evolution.py` | [development/tests/test_orchestration/test_evolution.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/agents/development/tests/test_orchestration/test_evolution.py) |
| `tests/test_orchestration/test_execution_backend.py` | [execution/tests/test_orchestration/test_execution_backend.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/agents/execution/tests/test_orchestration/test_execution_backend.py) |
| `tests/test_orchestration/test_groq_tool_router.py` | [model_routing/tests/test_orchestration/test_groq_tool_router.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/agents/model_routing/tests/test_orchestration/test_groq_tool_router.py) |
| `tests/test_orchestration/test_harness2_adapter.py` | [harness/tests/test_orchestration/test_harness2_adapter.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/agents/harness/tests/test_orchestration/test_harness2_adapter.py) |
| `tests/test_orchestration/test_model_commands.py` | [validation/tests/test_orchestration/test_model_commands.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/agents/validation/tests/test_orchestration/test_model_commands.py) |
| `tests/test_orchestration/test_model_policy.py` | [model_routing/tests/test_orchestration/test_model_policy.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/agents/model_routing/tests/test_orchestration/test_model_policy.py) |
| `tests/test_orchestration/test_model_routes.py` | [model_routing/tests/test_orchestration/test_model_routes.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/agents/model_routing/tests/test_orchestration/test_model_routes.py) |
| `tests/test_orchestration/test_stop_all.py` | [validation/tests/test_orchestration/test_stop_all.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/agents/validation/tests/test_orchestration/test_stop_all.py) |
| `tests/test_orchestration/test_visible_batch.py` | [validation/tests/test_orchestration/test_visible_batch.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/agents/validation/tests/test_orchestration/test_visible_batch.py) |
| `tests/test_skills/test_agent_cost_policy.py` | [model_routing/tests/test_skills/test_agent_cost_policy.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/agents/model_routing/tests/test_skills/test_agent_cost_policy.py) |
| `tests/test_skills/test_development.py` | [development/tests/test_skills/test_development.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/agents/development/tests/test_skills/test_development.py) |
