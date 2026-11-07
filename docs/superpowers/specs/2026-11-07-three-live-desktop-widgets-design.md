# Design Specification: Dynamic 3D Desktop Widgets for JARVIS OS

**Date:** 2026-11-07  
**Status:** Approved  
**Subsystem:** `ui/jarvis_widgets` / Omarchy Quickshell Desktop  
**Engine:** `google/three-live` on-device JIT compiler & runtime  

---

## 1. Overview & Objective

Enable JARVIS OS to dynamically generate, compile, and display interactive 3D spatial models and CAD assets directly on the Wayland/Hyprland desktop using `google/three-live`. 

When the user asks JARVIS to visualize a 3D object, mechanical part, or spatial concept (via voice or CLI), JARVIS produces standard procedural Three.js JavaScript. The system validates and compiles this script on-device into a binary `.glb` model, generates a high-definition 360° turntable animation, and renders a dynamic card in the Quickshell desktop deck with one-click interactive inspection and export capabilities.

Mobile (Android/iOS) is explicitly out of scope for this subsystem. The voice subsystem (`voice_layer/`, `jarvis_voice/`, `audio/`) remains strictly frozen and unmodified under `audio/.voice_lock.json`.

---

## 2. Architecture & Pipeline

```
                     User Voice / Text Request
                 "JARVIS, render a 3D bevel gear"
                                 │
                                 ▼
                     JARVIS Agent Orchestrator
             (Generates procedural Three.js JS snippet)
                                 │
                                 ▼
               ┌───────────────────────────────────┐
               │     ui/jarvis_widgets/backend.py  │
               │            (kind: "3d")           │
               └─────────────────┬─────────────────┘
                                 │
                                 ▼
               ┌───────────────────────────────────┐
               │    Local three-live Compiler      │
               │   (Sandboxed Rust VM / CLI)       │
               │                                   │
               │ 1. validate script diagnostics    │
               │ 2. convert -> model.glb           │
               │ 3. render --turntable -> .gif     │
               │ 4. extract AABB dimensions & stats│
               └─────────────────┬─────────────────┘
                                 │
                                 ▼
               ┌───────────────────────────────────┐
               │    Omarchy Quickshell Shell IPC   │
               │      (omarchy-shell / runtime)    │
               └─────────────────┬─────────────────┘
                                 │
                                 ▼
               ┌───────────────────────────────────┐
               │       Desktop 3D Widget Card      │
               │ • Smooth 360° Turntable Loop      │
               │ • Geometric Dimensions & Polycount│
               │ • [ 🔍 Inspect 3D ] [ 💾 Export ] │
               └─────────────────┬─────────────────┘
                                 │ (on "Inspect 3D")
                                 ▼
               ┌───────────────────────────────────┐
               │  Interactive Three-Live Inspector │
               │   (60 FPS Orbit, Pan, Zoom, CSG)  │
               └───────────────────────────────────┘
```

---

## 3. Data Contract & Schema

### 3.1 Input Payload Schema (`kind: "3d"`)

In `ui/jarvis_widgets/backend.py`:

```python
FIELDS["3d"] = {"script", "title", "caption", "actions"}
```

Example payload:
```json
{
  "kind": "3d",
  "title": "Procedural Bevel Gear",
  "data": {
    "script": "const gear = new THREE.Mesh(new THREE.CylinderGeometry(1, 1, 0.2, 16), new THREE.MeshStandardMaterial({color: 0x38bdf8, metalness: 0.8})); scene.add(gear);",
    "caption": "16-tooth bevel gear with 20° pressure angle",
    "actions": [
      { "label": "Inspect 3D", "action": "inspect_3d", "primary": true },
      { "label": "Export GLB", "action": "export_glb", "primary": false }
    ]
  },
  "presentation": "floating",
  "expires_seconds": 0
}
```

### 3.2 Output Telemetry Schema

The compilation worker enriches the widget data with computed spatial properties:

```json
{
  "source": "file:///path/to/turntable.gif",
  "model_path": "/path/to/model.glb",
  "script_path": "/path/to/scene.js",
  "caption": "16-tooth bevel gear with 20° pressure angle",
  "dimensions": { "width": 2.0, "height": 0.2, "depth": 2.0, "unit": "m" },
  "triangles": 128,
  "vertices": 66,
  "actions": [ ... ]
}
```

---

## 4. Subsystem Components

### 4.1 CLI & Compiler Bridge (`ui/jarvis_widgets/three_compiler.py`)
- Manages execution of `three-live-cli` (`convert`, `validate`, `render`).
- Manages temp/cache directories in `$XDG_RUNTIME_DIR/jarvis/widgets/3d/` with mode `0700`.
- Implements a strict **5.0-second execution fence** (`asyncio.wait_for` / subprocess timeout) to ensure untrusted scripts never block system operations.
- Extracts spatial bounds and mesh diagnostics from `three-live-cli info` or compiler JSON output.

### 4.2 Widget Controller Extension (`ui/jarvis_widgets/backend.py`)
- Registers `3d` in `KINDS`.
- Validates the Three.js script string (max 48 KiB limit).
- Triggers compilation asynchronously or during widget creation.
- Dispatches formatted IPC payload to `omarchy-shell jarvis-canvas`.

### 4.3 Desktop Presentation Card (`ui/jarvis_widgets/WidgetCard.qml`)
- Adds a `threeDBlock` component in the widget `Loader`.
- Displays the high-resolution turntable animation using `AnimatedImage`.
- Displays a clean telemetry badge (dimensions, triangle count) below the preview.
- Surfaces interactive action buttons (`Inspect 3D`, `Export GLB`).

### 4.4 Standalone Interactive Inspector (`ui/jarvis_widgets/inspector/`)
- A minimal, dark-themed standalone viewer page hosting `<three-live>` custom element.
- Opened on demand when the user clicks **Inspect 3D** or runs `jarvis 3d inspect <widget_id>`.
- Provides 60 FPS orbit, pan, zoom, camera reset, and wireframe toggle.
- Window is chromeless, floating, and managed by Hyprland window rules.

---

## 5. Security & Isolation Boundary

1. **Sandboxed JavaScript Execution:**
   The input script is executed strictly inside `three-live`'s embedded Rust Boa VM. No access is granted to host file systems, network sockets, child processes, or environment variables.
2. **Resource Boundaries:**
   - Max script size: 48 KiB.
   - Max compilation & render time: 5.0 seconds.
   - Max output GLB size: 64 MiB.
3. **Voice Subsystem Protection:**
   The voice lock files (`audio/.voice_lock.json` and `universal-voice/.voice_lock.json`) are untouched. `scripts/verify_voice_lock.py` runs as part of testing.

---

## 6. Testing Strategy

1. **Unit Tests (`tests/test_widget_3d.py`):**
   - Validation test: valid vs. malformed Three.js scripts.
   - Compilation test: successfully compiles procedural script to `.glb` and generates turntable `.gif`.
   - Timeout fence test: ensures long-running or infinite loops are caught within 5 seconds without raising unhandled exceptions.
   - Schema test: verifies QML contract compliance for `kind: "3d"`.
2. **Voice Guard Verification:**
   - Execute `python scripts/verify_voice_lock.py` to confirm zero changes to voice subsystems.
