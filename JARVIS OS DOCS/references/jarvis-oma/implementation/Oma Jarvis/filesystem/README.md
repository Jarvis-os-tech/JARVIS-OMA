# filesystem

File operations and multi-step file-task execution.

**Source snapshot:** imports and original behavior are preserved; this folder is not yet an independent package.

## Features

Feature folders contain complete original files, related tests/manifests and exact code extracts.

- [compatibility](compatibility/FEATURE.md)
- [operations](operations/FEATURE.md)
- [task_runner](task_runner/FEATURE.md)

## File index

| Original path | Organized copy |
|---|---|
| `filesystem/README.md` | [operations/README.md](../../../../jarvis-os/implementation/filesystem/README.md) |
| `filesystem/__init__.py` | [operations/__init__.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/filesystem/operations/__init__.py) |
| `filesystem/filesystem.py` | [operations/filesystem.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/filesystem/operations/filesystem.py) |
| `filesystem/task_runner.py` | [task_runner/task_runner.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/filesystem/task_runner/task_runner.py) |
| `skill_manifests/filesystem.json` | [operations/manifests/canonical/filesystem.json](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/filesystem/operations/manifests/canonical/filesystem.json) |
| `skill_manifests/task-runner.json` | [task_runner/manifests/canonical/task-runner.json](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/filesystem/task_runner/manifests/canonical/task-runner.json) |
| `skills/manifests/filesystem.json` | [operations/manifests/legacy_mirror/filesystem.json](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/filesystem/operations/manifests/legacy_mirror/filesystem.json) |
| `skills/manifests/task-runner.json` | [task_runner/manifests/legacy_mirror/task-runner.json](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/filesystem/task_runner/manifests/legacy_mirror/task-runner.json) |
| `task_runner.py` | [compatibility/task_runner.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/filesystem/compatibility/task_runner.py) |
| `tests/test_filesystem/test_filesystem.py` | [operations/tests/test_filesystem/test_filesystem.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/filesystem/operations/tests/test_filesystem/test_filesystem.py) |
| `tests/test_filesystem/test_task_runner.py` | [task_runner/tests/test_filesystem/test_task_runner.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/filesystem/task_runner/tests/test_filesystem/test_task_runner.py) |
