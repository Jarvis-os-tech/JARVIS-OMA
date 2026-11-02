# Connectors

All JARVIS connector implementations are collected here with their existing adapters, manifests, setup/diagnostic scripts and related tests. These 32 files are unchanged convenience copies of files already present under integrations/ and gui_control/. Existing copies remain in place; this duplication is intentional and recorded in the addition manifest.

This is a source collection, not a reconstructed Python package. Imports, credential path calculations, launch paths and runtime dependencies remain unchanged. Credential-handling implementation is included; actual credentials and tokens are not.

| Feature | Folder |
| --- | --- |
| Browser | [browser](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/connectors/browser) |
| Google Workspace and calendar/time zones | [google_workspace](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/connectors/google_workspace) |
| GitHub | [github](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/connectors/github) |
| Internet search | [search](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/connectors/search) |
| Phone | [phone](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/connectors/phone) |
| Credential-store implementation | [credential_store](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/connectors/credential_store) |
| Diagnostics | [diagnostics](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/connectors/diagnostics) |
| Original package marker | [package_markers](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/connectors/package_markers) |

## Source map

| Original source | Copy | Earlier copy |
| --- | --- | --- |
| `connectors/__init__.py` | [package_markers/connectors/__init__.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/connectors/package_markers/connectors/__init__.py) | `integrations/package_markers/connectors/__init__.py` |
| `connectors/browser.py` | [browser/browser.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/connectors/browser/browser.py) | `gui_control/browser/browser.py` |
| `connectors/calendar_time.py` | [google_workspace/calendar_time/calendar_time.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/connectors/google_workspace/calendar_time/calendar_time.py) | `integrations/google_workspace/calendar_time/calendar_time.py` |
| `connectors/credentials.py` | [credential_store/credentials.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/connectors/credential_store/credentials.py) | `integrations/credential_store/credentials.py` |
| `connectors/github.py` | [github/github.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/connectors/github/github.py) | `integrations/github/github.py` |
| `connectors/google_workspace.py` | [google_workspace/google_workspace.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/connectors/google_workspace/google_workspace.py) | `integrations/google_workspace/google_workspace.py` |
| `connectors/internet_search.py` | [search/internet_search.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/connectors/search/internet_search.py) | `integrations/search/internet_search.py` |
| `connectors/phone.py` | [phone/phone.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/connectors/phone/phone.py) | `integrations/phone/phone.py` |
| `scripts/check_connectors.py` | [diagnostics/check_connectors.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/connectors/diagnostics/check_connectors.py) | `integrations/diagnostics/check_connectors.py` |
| `scripts/connect_github.py` | [github/tools/connect_github.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/connectors/github/tools/connect_github.py) | `integrations/github/tools/connect_github.py` |
| `scripts/connect_google.py` | [google_workspace/tools/connect_google.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/connectors/google_workspace/tools/connect_google.py) | `integrations/google_workspace/tools/connect_google.py` |
| `scripts/import_connector_credentials.py` | [credential_store/tools/import_connector_credentials.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/connectors/credential_store/tools/import_connector_credentials.py) | `integrations/credential_store/tools/import_connector_credentials.py` |
| `skill_manifests/github.json` | [github/manifests/canonical/github.json](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/connectors/github/manifests/canonical/github.json) | `integrations/github/manifests/canonical/github.json` |
| `skill_manifests/google-workspace.json` | [google_workspace/manifests/canonical/google-workspace.json](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/connectors/google_workspace/manifests/canonical/google-workspace.json) | `integrations/google_workspace/manifests/canonical/google-workspace.json` |
| `skill_manifests/internet-search.json` | [search/manifests/canonical/internet-search.json](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/connectors/search/manifests/canonical/internet-search.json) | `integrations/search/manifests/canonical/internet-search.json` |
| `skill_manifests/phone.json` | [phone/manifests/canonical/phone.json](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/connectors/phone/manifests/canonical/phone.json) | `integrations/phone/manifests/canonical/phone.json` |
| `skills/domains/github.py` | [github/adapters/github.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/connectors/github/adapters/github.py) | `integrations/github/adapters/github.py` |
| `skills/domains/workspace.py` | [google_workspace/adapters/workspace.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/connectors/google_workspace/adapters/workspace.py) | `integrations/google_workspace/adapters/workspace.py` |
| `skills/manifests/github.json` | [github/manifests/legacy_mirror/github.json](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/connectors/github/manifests/legacy_mirror/github.json) | `integrations/github/manifests/legacy_mirror/github.json` |
| `skills/manifests/google-workspace.json` | [google_workspace/manifests/legacy_mirror/google-workspace.json](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/connectors/google_workspace/manifests/legacy_mirror/google-workspace.json) | `integrations/google_workspace/manifests/legacy_mirror/google-workspace.json` |
| `skills/manifests/internet-search.json` | [search/manifests/legacy_mirror/internet-search.json](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/connectors/search/manifests/legacy_mirror/internet-search.json) | `integrations/search/manifests/legacy_mirror/internet-search.json` |
| `skills/manifests/phone.json` | [phone/manifests/legacy_mirror/phone.json](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/connectors/phone/manifests/legacy_mirror/phone.json) | `integrations/phone/manifests/legacy_mirror/phone.json` |
| `tests/test_connectors/test_browser.py` | [browser/tests/test_connectors/test_browser.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/connectors/browser/tests/test_connectors/test_browser.py) | `gui_control/browser/tests/test_connectors/test_browser.py` |
| `tests/test_core/test_phone_monitor.py` | [phone/tests/test_core/test_phone_monitor.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/connectors/phone/tests/test_core/test_phone_monitor.py) | `integrations/phone/tests/test_core/test_phone_monitor.py` |
| `tests/test_scripts/test_connect_github.py` | [github/tools/tests/test_scripts/test_connect_github.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/connectors/github/tools/tests/test_scripts/test_connect_github.py) | `integrations/github/tools/tests/test_scripts/test_connect_github.py` |
| `tests/test_skills/test_calendar_management.py` | [google_workspace/tests/test_skills/test_calendar_management.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/connectors/google_workspace/tests/test_skills/test_calendar_management.py) | `integrations/google_workspace/tests/test_skills/test_calendar_management.py` |
| `tests/test_skills/test_calendar_timezones.py` | [google_workspace/calendar_time/tests/test_skills/test_calendar_timezones.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/connectors/google_workspace/calendar_time/tests/test_skills/test_calendar_timezones.py) | `integrations/google_workspace/calendar_time/tests/test_skills/test_calendar_timezones.py` |
| `tests/test_skills/test_connectors.py` | [diagnostics/tests/test_skills/test_connectors.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/connectors/diagnostics/tests/test_skills/test_connectors.py) | `integrations/diagnostics/tests/test_skills/test_connectors.py` |
| `tests/test_skills/test_github_connector.py` | [github/tests/test_skills/test_github_connector.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/connectors/github/tests/test_skills/test_github_connector.py) | `integrations/github/tests/test_skills/test_github_connector.py` |
| `tests/test_skills/test_google_connector.py` | [google_workspace/tests/test_skills/test_google_connector.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/connectors/google_workspace/tests/test_skills/test_google_connector.py) | `integrations/google_workspace/tests/test_skills/test_google_connector.py` |
| `tests/test_skills/test_phone.py` | [phone/tests/test_skills/test_phone.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/connectors/phone/tests/test_skills/test_phone.py) | `integrations/phone/tests/test_skills/test_phone.py` |
| `tests/test_skills/test_search_result_urls.py` | [search/tests/test_skills/test_search_result_urls.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/connectors/search/tests/test_skills/test_search_result_urls.py) | `integrations/search/tests/test_skills/test_search_result_urls.py` |

[Complete coverage report](../../../evidence/Oma%20Jarvis/_analysis/COPY_COVERAGE_2026-10-30.md)

[Connector dependency notes](DEPENDENCIES.md)
