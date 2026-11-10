# Universal Teaching Mode for JARVIS OS

A decoupled, standalone package providing voice-guided visual teaching, dynamic visualizers, and an isolated virtual mouse cursor for JARVIS on Wayland (Hyprland).

---

## 📁 Package Structure

```
teaching_mode/
├── ui/                     # Native Wayland Quickshell Overlay & Visualizers
│   ├── shell.qml           # Shell root entry point
│   ├── manifest.json       # Plugin metadata
│   ├── TeachingOverlay.qml # Layer-shell overlay with IPC target "teaching"
│   ├── JarvisCursor.qml    # Dedicated isolated virtual mouse pointer for JARVIS
│   ├── MathCalculationView.qml  # Step-by-step formula & algebra derivations
│   ├── GraphChartView.qml  # Complexity curves, bar charts, and node graphs
│   ├── TableView.qml       # Comparison and matrix data tables
│   ├── BubbleSortView.qml  # Animated array & sorting visualizer
│   ├── QuadcopterView.qml  # Physics, flight dynamics & rotor torque model
│   └── WhiteboardCanvas.qml# Freeform 2D vector drawing canvas
├── domain/
│   └── teaching.py         # Python skill domain with pedagogical actuation guards
├── manifest/
│   └── teaching.json       # Tool definitions & JSON parameter schemas
└── tests/
    └── test_teaching_mode.py # Unit tests for teaching mode workflows
```

---

## 🚀 How to Run Standalone

### 1. Launch the Visual Overlay Daemon
```bash
quickshell -p "/home/g0pi/JARVIS OS/teaching_mode/ui" -d
```

### 2. Send Live IPC Commands
- **Check Status**:
  ```bash
  quickshell -p "/home/g0pi/JARVIS OS/teaching_mode/ui" ipc call teaching status
  ```
- **Start a Lesson**:
  ```bash
  # Math calculation
  quickshell -p "/home/g0pi/JARVIS OS/teaching_mode/ui" ipc call teaching start '{"topic":"Quadratic Equation","mode":"math"}'

  # Complexity Graph
  quickshell -p "/home/g0pi/JARVIS OS/teaching_mode/ui" ipc call teaching start '{"topic":"Big-O Time Complexity","mode":"graph"}'

  # Comparison Table
  quickshell -p "/home/g0pi/JARVIS OS/teaching_mode/ui" ipc call teaching start '{"topic":"Sorting Comparison","mode":"table"}'

  # Bubble Sort
  quickshell -p "/home/g0pi/JARVIS OS/teaching_mode/ui" ipc call teaching start '{"topic":"Bubble Sort","mode":"bubble_sort"}'

  # Quadcopter Physics
  quickshell -p "/home/g0pi/JARVIS OS/teaching_mode/ui" ipc call teaching start '{"topic":"Quadcopter Rotors","mode":"quadcopter"}'
  ```
- **Step Through Lesson**:
  ```bash
  quickshell -p "/home/g0pi/JARVIS OS/teaching_mode/ui" ipc call teaching step '{"step":1,"action":"compare","say":"Comparing elements."}'
  ```
- **Direct Cursor Movement**:
  ```bash
  quickshell -p "/home/g0pi/JARVIS OS/teaching_mode/ui" ipc call teaching cursor '{"x":350,"y":220,"click":true,"label":"Focus here"}'
  ```
- **Close the Overlay**:
  ```bash
  quickshell -p "/home/g0pi/JARVIS OS/teaching_mode/ui" ipc call teaching close
  ```

---

## 🔌 How to Re-Integrate into JARVIS OS Skills

1. Copy `domain/teaching.py` to `skills/domains/teaching.py`.
2. Copy `manifest/teaching.json` to `skill_manifests/teaching.json`.
3. In `skills/skills.py`:
   - Import `TeachingDomain, ADAPTERS as TEACHING_ADAPTERS, ADAPTER_COMMANDS as TEACHING_COMMANDS, RESTRICTED_TEACHING_TOOLS`.
   - Inherit `TeachingDomain` in `DesktopSkills`.
   - Add `**TEACHING_ADAPTERS` and `**TEACHING_COMMANDS`.
