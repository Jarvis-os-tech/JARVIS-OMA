# Artemis Architecture & Roadmap: Adapting Mobile Agent Reliability for JARVIS (Linux Desktop First, Mobile Second)

## 1. Executive Summary

Google's [Artemis](https://github.com/google/artemis.git) achieved an industry-leading **99%+ task completion rate** on the Google DeepMind *AndroidWorld* benchmark across 20 real applications. It accomplished this not by relying on brute-force LLM inference, but through structural architectural patterns:

1. **Dual Execution Modes (Flash vs. Pro)**: Separating low-latency reactive steps from deliberate multi-step planned operations.
2. **Pre-Action Target Verification**: Verifying the UI hierarchy, bounding boxes, and interactivity state *before* issuing any click or touch gesture.
3. **Autonomous Self-Healing**: Detecting and dismissing pop-ups, modal dialogs, and ads without human intervention.
4. **Deterministic State Verification**: Validating real state changes against ground truth (database, files, process status) rather than model self-reporting.
5. **Backtracking & Trajectory Rollback**: Recovering from dead-ends by unwinding state to a known checkpoint.

This document defines how **J.A.R.V.I.S. OMA** adapts these exact principles:
- **Phase 1 (Linux Desktop First)**: Harden and upgrade JARVIS's desktop GUI and system control capabilities under Hyprland / Wayland.
- **Phase 2 (Mobile Second)**: Integrate Google Artemis as an external mobile execution engine via MCP/ADB, providing seamless voice-driven cross-device control between the Linux desktop and Android devices.

---

## 2. Phase 1: Linux Desktop Implementation (JARVIS-OMA)

### 2.1 Dual Execution Modes on Linux Desktop

```
                       [Voice / Task Goal]
                                |
                        [Mode Evaluator]
                               / \
                              /   \
                             /     \
             [Flash Mode (<100ms)]  [Pro Mode (Multi-Step)]
             - hyprctl dispatch     - Goal Decomposition
             - pactl audio volume   - Hybrid Perception (AT-SPI + Vision)
             - Direct wtype keys    - Pre-Action Verification
             - Window focus switch  - Self-Healing Modal Dismissal
                                    - Deterministic Ground-Truth Check
```

1. **Linux Flash Mode (`skills/system_control.py` & `skills/gui_control.py`)**:
   - Single-step actions executed deterministically with zero planning overhead.
   - Fast-path for window manipulation (`hyprctl dispatch focuswindow`), volume adjustment, media keys, and simple app launching.
   - Latency target: `< 100ms`.

2. **Linux Pro Mode (`orchestration/pro_desktop_agent.py`)**:
   - Multi-step, goal-directed desktop interaction (e.g., *"Open LibreOffice, convert the invoice to PDF, and attach it in Thunderbird"*).
   - Decomposes goals into verifiable subgoals with state tracking.
   - Manages an execution trajectory stack with rollback capability.

---

### 2.2 Hybrid Perception Layer (AT-SPI2 + Wayland Screencopy)

Artemis fuses Android Accessibility Node trees with visual video frames. On Linux, JARVIS combines:
- **Semantic Layer (AT-SPI2 / D-Bus)**:
  - Query application accessibility trees via AT-SPI2 for GTK, Qt, and browser components.
  - Expose element roles, labels, and bounding boxes without relying solely on pixel parsing.
- **Visual Grounding Layer (Grim + Wayland Screencopy)**:
  - For games, Electron applications, or degraded accessibility trees, fall back to high-resolution Wayland display capture.
  - Ground clicks using relative normalized coordinates `(x, y)` clamped to the active Hyprland window geometry.
- **Boundary Clamping**:
  - Prevent pointer actions from bleeding outside the target application's tiled window bounds (`hyprctl activewindow`).

---

### 2.3 Desktop Self-Healing & Modal Recovery

In Artemis, mobile dialogs and ads are autonomously detected and dismissed. On Linux desktop, JARVIS encounters equivalent interruptions:
- **Keyring & Polkit Prompts**: Detect authentication dialogs and prompt the user via voice rather than blindly clicking.
- **File Overwrite Prompts**: Detect *"File already exists. Replace?"* alerts, verify target path, and make safe decisions.
- **Focus Stealing & Window Misalignment**: Detect when a background process takes focus during a multi-step task, re-focus the target window via Hyprland IPC, and resume.
- **Browser Alerts & Cookie Banners**: Identify full-screen overlays in the browser runner and dismiss them before attempting navigation.

---

### 2.4 Deterministic Ground-Truth Verification

Never declare a step complete simply because a mouse click or keypress was sent. Verify ground truth:
- **Filesystem Verification**: Confirm the target file was created with `size > 0` and valid headers.
- **Process Verification**: Confirm the target PID is running in `/proc` or systemd user session.
- **Clipboard Verification**: Check `wl-paste` to verify text copy/cut succeeded.
- **D-Bus & IPC Inspection**: Query application state directly over D-Bus where available.

---

## 3. Phase 2: Mobile Second (Google Artemis Integration)

Once the core reliability runtime is operational on the Linux desktop, mobile capabilities are added by treating Google Artemis as a specialized mobile capability provider.

```
+-------------------------------------------------------------+
|                     JARVIS-OMA (Desktop Host)               |
|                                                             |
|   [Gemini Live Full-Duplex Voice] <---> [Skills Matrix]     |
|                                                |            |
|                                       [connectors/artemis.py]
+------------------------------------------------|------------+
                                                 | (MCP / ADB)
                                                 v
+-------------------------------------------------------------+
|                Google Artemis Engine (Daemon / MCP)          |
|                                                             |
|   [Pro Mode Reasoning] <---> [Hybrid Perception]            |
|   [Flash Direct Action] <--> [scrcpy / Accessibility / ADB]  |
+------------------------------------------------|------------+
                                                 | USB / Wi-Fi
                                                 v
+-------------------------------------------------------------+
|                   Android Mobile Device                     |
|                                                             |
|   [Android OS] <--> [Apps: WhatsApp, Maps, Uber, SMS]       |
+-------------------------------------------------------------+
```

### 3.1 Connector Architecture (`connectors/artemis.py`)
- Manages connection to the local Artemis MCP server.
- Probes connected devices via `adb devices -l`.
- Reports battery level, Wi-Fi connectivity, screen power state, and foreground package.

### 3.2 Voice-Enabled Mobile Skills (`skill_manifests/android-device.json`)
Exposes high-level skills to Gemini Live:
- `mobile_execute_task(goal: str)`: Dispatches complex goals to Artemis Pro Mode (e.g., *"Order my regular coffee on DoorDash"*).
- `mobile_quick_action(action: str)`: Executes instant Flash Mode actions (e.g., *"Toggle flashlight"*, *"Accept incoming call"*).
- `mobile_inspect_screen()`: Captures phone screen frame via `scrcpy` and pipes it into JARVIS's visual stream.
- `mobile_read_messages(app: str, limit: int)`: Reads latest incoming SMS, WhatsApp, or Telegram messages.

### 3.3 Cross-Device Ecosystem Bridges
1. **2FA & OTP Relay**: Artemis monitors incoming SMS; upon receiving an OTP, JARVIS speaks it immediately or pastes it into the active desktop browser tab.
2. **Unified Clipboard**: Synchronize Wayland `wl-copy`/`wl-paste` with Android clipboard over ADB.
3. **Notification HUD**: Forward Android system notifications to JARVIS's Wayland overlay pill HUD.

---

## 4. Implementation Milestones

| Milestone | Target | Description |
|---|---|---|
| **M1: Pre-Action Boundary Guard** | Linux Desktop | Update `skills/gui_control.py` and `skills/system_control.py` with Hyprland window coordinate bounds, focus verification, and target-window guards preventing unintended terminal typing. |
| **M2: Modal & Focus Self-Healing** | Linux Desktop | Implement detection and dismissal routines for desktop file prompts, focus shifts, and application dialogs. |
| **M3: Ground-Truth Verification Engine** | Linux Desktop | Build verifiable state checkers (filesystem diff, process poll, clipboard inspection) before declaring task completion. |
| **M4: Artemis MCP Setup & Local Testing** | Mobile Setup | Set up `google/artemis` locally, configure ADB/scrcpy, and test basic device control. |
| **M5: Artemis Connector for JARVIS** | Mobile Integration | Implement `connectors/artemis.py` and register `skill_manifests/android-device.json` for full voice-driven phone automation. |
