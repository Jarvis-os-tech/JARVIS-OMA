# runtime

Application entry points, IPC, workers and cross-domain service coordination.

**Source snapshot:** imports and original behavior are preserved; this folder is not yet an independent package.

## Features

Feature folders contain complete original files, related tests/manifests and exact code extracts.

- [capability_services](capability_services/FEATURE.md)
- [entrypoints](entrypoints/FEATURE.md)
- [ipc](ipc/FEATURE.md)
- [ipc/cli](ipc/cli/FEATURE.md)
- [legacy_core](legacy_core/FEATURE.md)
- [status](status/FEATURE.md)
- [workers](workers/FEATURE.md)

## File index

| Original path | Organized copy |
|---|---|
| `agent.py` | [entrypoints/agent.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/runtime/entrypoints/agent.py) |
| `core/README.md` | [legacy_core/README.md](../../core/README.md) |
| `core/__init__.py` | [legacy_core/__init__.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/runtime/legacy_core/__init__.py) |
| `core/ipc.py` | [ipc/ipc.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/runtime/ipc/ipc.py) |
| `core/stable_capabilities.py` | [capability_services/stable_capabilities.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/runtime/capability_services/stable_capabilities.py) |
| `core/workers.py` | [workers/workers.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/runtime/workers/workers.py) |
| `scripts/jarvisctl` | [ipc/cli/jarvisctl](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/runtime/ipc/cli/jarvisctl) |
| `scripts/jarvisctl.py` | [ipc/cli/jarvisctl.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/runtime/ipc/cli/jarvisctl.py) |
| `skill_manifests/assistant-status.json` | [status/manifests/canonical/assistant-status.json](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/runtime/status/manifests/canonical/assistant-status.json) |
| `skills/manifests/assistant-status.json` | [status/manifests/legacy_mirror/assistant-status.json](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/runtime/status/manifests/legacy_mirror/assistant-status.json) |
| `tests/test_core/test_ipc.py` | [ipc/tests/test_core/test_ipc.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/runtime/ipc/tests/test_core/test_ipc.py) |
| `tests/test_core/test_stable_capabilities.py` | [capability_services/tests/test_core/test_stable_capabilities.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/runtime/capability_services/tests/test_core/test_stable_capabilities.py) |
| `tests/test_core/test_startup.py` | [entrypoints/tests/test_core/test_startup.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/runtime/entrypoints/tests/test_core/test_startup.py) |
| `tests/test_core/test_workers.py` | [workers/tests/test_core/test_workers.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/runtime/workers/tests/test_core/test_workers.py) |
| `tests/test_scripts/test_jarvisctl.py` | [ipc/cli/tests/test_scripts/test_jarvisctl.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/runtime/ipc/cli/tests/test_scripts/test_jarvisctl.py) |
