# configuration

Settings, shared prompts, environment filtering, dependency lists and configuration templates.

**Source snapshot:** imports and original behavior are preserved; this folder is not yet an independent package.

## Features

Feature folders contain complete original files, related tests/manifests and exact code extracts.

- [compatibility](compatibility/FEATURE.md)
- [dependencies](dependencies/FEATURE.md)
- [project](project/FEATURE.md)
- [prompts](prompts/FEATURE.md)
- [security](security/FEATURE.md)
- [settings](settings/FEATURE.md)
- [templates](templates/FEATURE.md)

## File index

| Original path | Organized copy |
|---|---|
| `.env.example` | [templates/.env.example](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/configuration/templates/.env.example) |
| `config.py` | [compatibility/config.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/configuration/compatibility/config.py) |
| `config.toml.example` | [templates/config.toml.example](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/configuration/templates/config.toml.example) |
| `core/config.py` | [settings/config.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/configuration/settings/config.py) |
| `core/harness_config.py` | [prompts/harness_config.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/configuration/prompts/harness_config.py) |
| `core/secret_env.py` | [security/secret_env.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/configuration/security/secret_env.py) |
| `pyproject.toml` | [project/pyproject.toml](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/configuration/project/pyproject.toml) |
| `requirements-dev.txt` | [dependencies/requirements-dev.txt](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/configuration/dependencies/requirements-dev.txt) |
| `requirements.txt` | [dependencies/requirements.txt](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/configuration/dependencies/requirements.txt) |
| `tests/test_core/test_config.py` | [settings/tests/test_core/test_config.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/configuration/settings/tests/test_core/test_config.py) |
| `tests/test_core/test_secret_env.py` | [security/tests/test_core/test_secret_env.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/configuration/security/tests/test_core/test_secret_env.py) |
| `tests/test_skills/test_subprocess_environment.py` | [security/tests/test_skills/test_subprocess_environment.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/configuration/security/tests/test_skills/test_subprocess_environment.py) |
