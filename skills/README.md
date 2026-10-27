# Skills Feature Package (`skills/`)

The `skills/` package houses dynamic desktop automation tools, declarative JSON skill manifests, system adapters, and the multimodal input bar.

## Components

- **`skills.py` (`DesktopSkills`, `SkillError`)**:
  - Dynamically discovers and loads declarative JSON manifests from `skill_manifests/`.
  - Performs strict JSON schema validation for tool declarations and function arguments.
  - Implements graceful degradation: auto-excludes skills whose command dependencies (`ADAPTER_COMMANDS`) are absent.
  - Dispatches calls to native desktop adapters:
    - Window & workspace management (`hyprctl`)
    - Display brightness & audio volume (`brightnessctl`, `wpctl`, `pactl`)
    - Network toggling (`nmcli`, `rfkill`)
    - Notifications (`notify-send`)
    - Screen capture & OCR awareness (`grim`, `tesseract`)
    - Power controls (`systemctl suspend/hibernate`)
    - Omarchy reminders & Todo list plugin
- **`input_bar.py` (`TestBar` / `InputBar`)**:
  - Ephemeral zero-dependency loopback HTTP server with cryptographic bearer token.
  - Serves a sleek multimodal web interface allowing users to type, paste, or attach files (images, audio, PDFs, text) into the active Gemini Live voice session.
- **`system_control.py`**:
  - Direct Wayland/Hyprland input simulation (`wtype`), keyboard shortcuts, top-bar panel toggles, and shell control.
  - Window/workspace actions bind exact targets and require timestamped compositor readback for success. Ordinary skill adapters and supported voice aliases share this path; failed/missing readback is preserved as an error or unverified result.
- **`manifests/`**:
  - Declarative JSON manifests declaring tools, parameters, descriptions, and required adapter bindings.

## Directory Structure

```text
skills/
├── README.md
├── __init__.py
├── skills.py             # Manifest loader & execution dispatcher
├── input_bar.py          # Multimodal loopback input bar web server
├── system_control.py     # Wayland & Omarchy system control utilities
└── manifests/            # Bundled JSON tool declarations
    ├── agent-orchestration.json
    ├── desktop-awareness.json
    ├── filesystem.json
    ├── input-bar.json
    ├── memory.json
    ├── omarchy-defaults.json
    ├── proactive.json
    ├── system-controls.json
    └── task-runner.json
```
