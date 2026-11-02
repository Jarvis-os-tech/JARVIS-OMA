# desktop_control

Operating-system controls, system information, extensions and desktop environment discovery.

**Source snapshot:** imports and original behavior are preserved; this folder is not yet an independent package.

## Features

Feature folders contain complete original files, related tests/manifests and exact code extracts.

- [audio_controls](audio_controls/FEATURE.md)
- [compatibility](compatibility/FEATURE.md)
- [display](display/FEATURE.md)
- [extensions](extensions/FEATURE.md)
- [information](information/FEATURE.md)
- [network](network/FEATURE.md)
- [notifications](notifications/FEATURE.md)
- [power](power/FEATURE.md)
- [session](session/FEATURE.md)
- [system_controls](system_controls/FEATURE.md)
- [theme](theme/FEATURE.md)

## File index

| Original path | Organized copy |
|---|---|
| `core/desktop_session.py` | [session/desktop_session.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/desktop_control/session/desktop_session.py) |
| `docs/superpowers/specs/2026-10-21-cli-anything-integration-design.md` | [docs/docs/superpowers/specs/2026-10-21-cli-anything-integration-design.md](../../../designs/docs/superpowers/specs/2026-10-21-cli-anything-integration-design.md) |
| `docs/system-control-and-information.md` | [docs/docs/system-control-and-information.md](../../docs/system-control-and-information.md) |
| `skill_manifests/cli-anything.json` | [cli_hub/manifests/canonical/cli-anything.json](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/desktop_control/cli_hub/manifests/canonical/cli-anything.json) |
| `skill_manifests/omarchy-defaults.json` | [default_actions/manifests/canonical/omarchy-defaults.json](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/desktop_control/default_actions/manifests/canonical/omarchy-defaults.json) |
| `skill_manifests/system-controls.json` | [system_controls/manifests/canonical/system-controls.json](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/desktop_control/system_controls/manifests/canonical/system-controls.json) |
| `skill_manifests/system-extensions.json` | [extensions/manifests/canonical/system-extensions.json](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/desktop_control/extensions/manifests/canonical/system-extensions.json) |
| `skill_manifests/system-information.json` | [information/manifests/canonical/system-information.json](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/desktop_control/information/manifests/canonical/system-information.json) |
| `skills/manifests/cli-anything.json` | [cli_hub/manifests/legacy_mirror/cli-anything.json](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/desktop_control/cli_hub/manifests/legacy_mirror/cli-anything.json) |
| `skills/manifests/omarchy-defaults.json` | [default_actions/manifests/legacy_mirror/omarchy-defaults.json](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/desktop_control/default_actions/manifests/legacy_mirror/omarchy-defaults.json) |
| `skills/manifests/system-controls.json` | [system_controls/manifests/legacy_mirror/system-controls.json](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/desktop_control/system_controls/manifests/legacy_mirror/system-controls.json) |
| `skills/manifests/system-extensions.json` | [extensions/manifests/legacy_mirror/system-extensions.json](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/desktop_control/extensions/manifests/legacy_mirror/system-extensions.json) |
| `skills/manifests/system-information.json` | [information/manifests/legacy_mirror/system-information.json](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/desktop_control/information/manifests/legacy_mirror/system-information.json) |
| `skills/system_control.py` | [system_controls/system_control.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/desktop_control/system_controls/system_control.py) |
| `skills/system_extensions.py` | [extensions/system_extensions.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/desktop_control/extensions/system_extensions.py) |
| `skills/system_information.py` | [information/system_information.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/desktop_control/information/system_information.py) |
| `system_control.py` | [compatibility/system_control.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/desktop_control/compatibility/system_control.py) |
| `tests/test_core/test_desktop_session.py` | [session/tests/test_core/test_desktop_session.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/desktop_control/session/tests/test_core/test_desktop_session.py) |
| `tests/test_skills/test_adjustment_routing.py` | [system_controls/tests/test_skills/test_adjustment_routing.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/desktop_control/system_controls/tests/test_skills/test_adjustment_routing.py) |
| `tests/test_skills/test_cli_anything.py` | [cli_hub/tests/test_skills/test_cli_anything.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/desktop_control/cli_hub/tests/test_skills/test_cli_anything.py) |
| `tests/test_skills/test_plugin_control_reliability.py` | [extensions/tests/test_skills/test_plugin_control_reliability.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/desktop_control/extensions/tests/test_skills/test_plugin_control_reliability.py) |
| `tests/test_skills/test_system_control.py` | [system_controls/tests/test_skills/test_system_control.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/desktop_control/system_controls/tests/test_skills/test_system_control.py) |
| `tests/test_skills/test_system_extensions.py` | [extensions/tests/test_skills/test_system_extensions.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/desktop_control/extensions/tests/test_skills/test_system_extensions.py) |
| `tests/test_skills/test_system_information.py` | [information/tests/test_skills/test_system_information.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/desktop_control/information/tests/test_skills/test_system_information.py) |
| `tests/test_skills/test_system_information_wiring.py` | [information/tests/test_skills/test_system_information_wiring.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/desktop_control/information/tests/test_skills/test_system_information_wiring.py) |
