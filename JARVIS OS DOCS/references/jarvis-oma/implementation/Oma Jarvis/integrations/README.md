# integrations

Google Workspace, GitHub, telephony, search and credential-store implementation (no credentials).

**Source snapshot:** imports and original behavior are preserved; this folder is not yet an independent package.

## Features

Feature folders contain complete original files, related tests/manifests and exact code extracts.

- [credential_store](credential_store/FEATURE.md)
- [credential_store/tools](credential_store/tools/FEATURE.md)
- [diagnostics](diagnostics/FEATURE.md)
- [github](github/FEATURE.md)
- [github/adapters](github/adapters/FEATURE.md)
- [github/tools](github/tools/FEATURE.md)
- [google_workspace](google_workspace/FEATURE.md)
- [google_workspace/adapters](google_workspace/adapters/FEATURE.md)
- [google_workspace/calendar_time](google_workspace/calendar_time/FEATURE.md)
- [google_workspace/tools](google_workspace/tools/FEATURE.md)
- [phone](phone/FEATURE.md)
- [search](search/FEATURE.md)

## File index

| Original path | Organized copy |
|---|---|
| `connectors/__init__.py` | [package_markers/connectors/__init__.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/integrations/package_markers/connectors/__init__.py) |
| `connectors/calendar_time.py` | [google_workspace/calendar_time/calendar_time.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/integrations/google_workspace/calendar_time/calendar_time.py) |
| `connectors/credentials.py` | [credential_store/credentials.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/integrations/credential_store/credentials.py) |
| `connectors/github.py` | [github/github.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/integrations/github/github.py) |
| `connectors/google_workspace.py` | [google_workspace/google_workspace.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/integrations/google_workspace/google_workspace.py) |
| `connectors/internet_search.py` | [search/internet_search.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/integrations/search/internet_search.py) |
| `connectors/phone.py` | [phone/phone.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/integrations/phone/phone.py) |
| `scripts/check_connectors.py` | [diagnostics/check_connectors.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/integrations/diagnostics/check_connectors.py) |
| `scripts/connect_github.py` | [github/tools/connect_github.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/integrations/github/tools/connect_github.py) |
| `scripts/connect_google.py` | [google_workspace/tools/connect_google.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/integrations/google_workspace/tools/connect_google.py) |
| `scripts/import_connector_credentials.py` | [credential_store/tools/import_connector_credentials.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/integrations/credential_store/tools/import_connector_credentials.py) |
| `skill_manifests/github.json` | [github/manifests/canonical/github.json](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/integrations/github/manifests/canonical/github.json) |
| `skill_manifests/google-workspace.json` | [google_workspace/manifests/canonical/google-workspace.json](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/integrations/google_workspace/manifests/canonical/google-workspace.json) |
| `skill_manifests/internet-search.json` | [search/manifests/canonical/internet-search.json](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/integrations/search/manifests/canonical/internet-search.json) |
| `skill_manifests/phone.json` | [phone/manifests/canonical/phone.json](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/integrations/phone/manifests/canonical/phone.json) |
| `skills/domains/github.py` | [github/adapters/github.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/integrations/github/adapters/github.py) |
| `skills/domains/workspace.py` | [google_workspace/adapters/workspace.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/integrations/google_workspace/adapters/workspace.py) |
| `skills/manifests/github.json` | [github/manifests/legacy_mirror/github.json](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/integrations/github/manifests/legacy_mirror/github.json) |
| `skills/manifests/google-workspace.json` | [google_workspace/manifests/legacy_mirror/google-workspace.json](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/integrations/google_workspace/manifests/legacy_mirror/google-workspace.json) |
| `skills/manifests/internet-search.json` | [search/manifests/legacy_mirror/internet-search.json](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/integrations/search/manifests/legacy_mirror/internet-search.json) |
| `skills/manifests/phone.json` | [phone/manifests/legacy_mirror/phone.json](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/integrations/phone/manifests/legacy_mirror/phone.json) |
| `tests/test_core/test_phone_monitor.py` | [phone/tests/test_core/test_phone_monitor.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/integrations/phone/tests/test_core/test_phone_monitor.py) |
| `tests/test_scripts/test_connect_github.py` | [github/tools/tests/test_scripts/test_connect_github.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/integrations/github/tools/tests/test_scripts/test_connect_github.py) |
| `tests/test_skills/test_calendar_management.py` | [google_workspace/tests/test_skills/test_calendar_management.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/integrations/google_workspace/tests/test_skills/test_calendar_management.py) |
| `tests/test_skills/test_calendar_timezones.py` | [google_workspace/calendar_time/tests/test_skills/test_calendar_timezones.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/integrations/google_workspace/calendar_time/tests/test_skills/test_calendar_timezones.py) |
| `tests/test_skills/test_connectors.py` | [diagnostics/tests/test_skills/test_connectors.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/integrations/diagnostics/tests/test_skills/test_connectors.py) |
| `tests/test_skills/test_github_connector.py` | [github/tests/test_skills/test_github_connector.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/integrations/github/tests/test_skills/test_github_connector.py) |
| `tests/test_skills/test_google_connector.py` | [google_workspace/tests/test_skills/test_google_connector.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/integrations/google_workspace/tests/test_skills/test_google_connector.py) |
| `tests/test_skills/test_phone.py` | [phone/tests/test_skills/test_phone.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/integrations/phone/tests/test_skills/test_phone.py) |
| `tests/test_skills/test_search_result_urls.py` | [search/tests/test_skills/test_search_result_urls.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/integrations/search/tests/test_skills/test_search_result_urls.py) |

All connectors, including the browser connector, are also available together in [connectors](../connectors/README.md). These are intentional unchanged convenience copies.
