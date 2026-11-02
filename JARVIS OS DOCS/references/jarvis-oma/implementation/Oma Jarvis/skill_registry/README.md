# skill_registry

Skill registration, validation, dispatch, tool tiering and compatibility package markers.

**Source snapshot:** imports and original behavior are preserved; this folder is not yet an independent package.

## Features

Feature folders contain complete original files, related tests/manifests and exact code extracts.

- [catalog](catalog/FEATURE.md)
- [dispatch](dispatch/FEATURE.md)
- [errors](errors/FEATURE.md)
- [registry](registry/FEATURE.md)
- [tiering](tiering/FEATURE.md)

## File index

| Original path | Organized copy |
|---|---|
| `core/tool_dispatch.py` | [dispatch/tool_dispatch.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/skill_registry/dispatch/tool_dispatch.py) |
| `orchestration/tool_tiers.py` | [tiering/tool_tiers.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/skill_registry/tiering/tool_tiers.py) |
| `skill_manifests/capabilities.json` | [catalog/manifests/canonical/capabilities.json](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/skill_registry/catalog/manifests/canonical/capabilities.json) |
| `skills/README.md` | [package_markers/skills/README.md](../../../../jarvis-os/implementation/skills/README.md) |
| `skills/__init__.py` | [package_markers/skills/__init__.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/skill_registry/package_markers/skills/__init__.py) |
| `skills/domains/__init__.py` | [package_markers/domains/__init__.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/skill_registry/package_markers/domains/__init__.py) |
| `skills/errors.py` | [errors/errors.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/skill_registry/errors/errors.py) |
| `skills/manifests/capabilities.json` | [catalog/manifests/legacy_mirror/capabilities.json](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/skill_registry/catalog/manifests/legacy_mirror/capabilities.json) |
| `skills/skills.py` | [registry/skills.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/skill_registry/registry/skills.py) |
| `tests/test_skills/test_capabilities.py` | [registry/tests/test_skills/test_capabilities.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/skill_registry/registry/tests/test_skills/test_capabilities.py) |
| `tests/test_skills/test_capability_startup_recovery.py` | [registry/tests/test_skills/test_capability_startup_recovery.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/skill_registry/registry/tests/test_skills/test_capability_startup_recovery.py) |
| `tests/test_skills/test_skills.py` | [registry/tests/test_skills/test_skills.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/skill_registry/registry/tests/test_skills/test_skills.py) |
