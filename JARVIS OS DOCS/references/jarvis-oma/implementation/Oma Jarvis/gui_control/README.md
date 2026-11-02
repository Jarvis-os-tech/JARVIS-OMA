# gui_control

Accessibility, browser interaction, keyboard/mouse control, window recovery and verified GUI outcomes.

**Source snapshot:** imports and original behavior are preserved; this folder is not yet an independent package.

## Features

Feature folders contain complete original files, related tests/manifests and exact code extracts.

- [accessibility](accessibility/FEATURE.md)
- [action_verification](../../../evidence/Oma%20Jarvis/gui_control/action_verification/FEATURE.md)
- [browser](browser/FEATURE.md)
- [clipboard](clipboard/FEATURE.md)
- [keyboard_and_mouse](keyboard_and_mouse/FEATURE.md)
- [mouse](mouse/FEATURE.md)
- [window_management](window_management/FEATURE.md)
- [window_recovery](window_recovery/FEATURE.md)

## File index

| Original path | Organized copy |
|---|---|
| `connectors/browser.py` | [browser/browser.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/gui_control/browser/browser.py) |
| `docs/GUI_CONTROL.md` | [docs/docs/GUI_CONTROL.md](../../docs/GUI_CONTROL.md) |
| `project-docs/DESKTOP_ACTION_VERIFICATION_2026-10-28.md` | [docs/project-docs/DESKTOP_ACTION_VERIFICATION_2026-10-28.md](../../../historical-plans/project-docs/DESKTOP_ACTION_VERIFICATION_2026-10-28.md) |
| `project-docs/VERIFIED_DESKTOP_WORKFLOWS_2026-10-28.md` | [docs/project-docs/VERIFIED_DESKTOP_WORKFLOWS_2026-10-28.md](../../../historical-plans/project-docs/VERIFIED_DESKTOP_WORKFLOWS_2026-10-28.md) |
| `skill_manifests/desktop-awareness.json` | [desktop_awareness/manifests/canonical/desktop-awareness.json](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/gui_control/desktop_awareness/manifests/canonical/desktop-awareness.json) |
| `skill_manifests/gui-control.json` | [accessibility/manifests/canonical/gui-control.json](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/gui_control/accessibility/manifests/canonical/gui-control.json) |
| `skills/action_verification.py` | [action_verification/action_verification.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/gui_control/action_verification/action_verification.py) |
| `skills/ground_truth.py` | [action_verification/ground_truth.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/gui_control/action_verification/ground_truth.py) |
| `skills/gui_control.py` | [accessibility/gui_control.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/gui_control/accessibility/gui_control.py) |
| `skills/manifests/desktop-awareness.json` | [desktop_awareness/manifests/legacy_mirror/desktop-awareness.json](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/gui_control/desktop_awareness/manifests/legacy_mirror/desktop-awareness.json) |
| `skills/manifests/gui-control.json` | [accessibility/manifests/legacy_mirror/gui-control.json](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/gui_control/accessibility/manifests/legacy_mirror/gui-control.json) |
| `skills/modal_healing.py` | [window_recovery/modal_healing.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/gui_control/window_recovery/modal_healing.py) |
| `tests/test_connectors/test_browser.py` | [browser/tests/test_connectors/test_browser.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/gui_control/browser/tests/test_connectors/test_browser.py) |
| `tests/test_skills/test_action_outcomes.py` | [action_verification/tests/test_skills/test_action_outcomes.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/gui_control/action_verification/tests/test_skills/test_action_outcomes.py) |
| `tests/test_skills/test_awareness.py` | [desktop_awareness/tests/test_skills/test_awareness.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/gui_control/desktop_awareness/tests/test_skills/test_awareness.py) |
| `tests/test_skills/test_ground_truth.py` | [action_verification/tests/test_skills/test_ground_truth.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/gui_control/action_verification/tests/test_skills/test_ground_truth.py) |
| `tests/test_skills/test_gui_control.py` | [accessibility/tests/test_skills/test_gui_control.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/gui_control/accessibility/tests/test_skills/test_gui_control.py) |
| `tests/test_skills/test_modal_healing.py` | [window_recovery/tests/test_skills/test_modal_healing.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/gui_control/window_recovery/tests/test_skills/test_modal_healing.py) |
| `tests/test_skills/test_verified_workflows.py` | [action_verification/tests/test_skills/test_verified_workflows.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/gui_control/action_verification/tests/test_skills/test_verified_workflows.py) |
