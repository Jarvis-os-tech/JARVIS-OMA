# ARCH-JARVIS-ENV-OS: ARCHITECTURAL MASTER PLAN & BUILD MAP
## An Independent, AI-Native, Voice-First Desktop Environment for Arch Linux

**Document Version:** 2.0.0-SOVEREIGN-EDITION  
**Architects:** AntiGravity & g0pi  
**Date:** November 2026  
**Status:** Canonical Implementation Blueprint & Execution Map  
**Target Platform:** Arch Linux (Kernel 7.2.x+ / Hyprland 0.56+ / Quickshell 0.1.0+ / Qt 6.8+ / PipeWire 1.x)

---

## 1. Executive Summary & Product Vision

### What We Are Building
**JARVIS OS** is an **independent, AI-native Wayland Desktop Environment (DE)** engineered from the ground up for Arch Linux. 

It is **not** a desktop theme, a collection of static desktop widgets, an Electron wrapper, or a window manager rice. In JARVIS OS, **the operating system itself becomes an intelligent coworker, personal companion, and autonomous system controller**.

The user interacts primarily through natural, continuous voice conversation. The desktop dynamically organizes itself around the user's intent: spawning contextual floating holographic data widgets, orchestrating background multi-agent workflows, controlling applications, managing windows, and manipulating system hardware handsfree.

```
                      +-----------------------------------------------------------+
                      |                      USER INTENT                          |
                      |   Natural Spoken Voice  •  Screen Context  •  Hotkeys     |
                      +-----------------------------------------------------------+
                                                    │
                                                    ▼
                      +-----------------------------------------------------------+
                      |                   JARVIS CORE BRAIN                       |
                      |   Gemini Live Multimodal  •  Needle SLM  •  Whistle ASR   |
                      |   287+ Registered OS Tools • Memory DB • Task Orchestrator|
                      +-----------------------------------------------------------+
                                        │                       │
                       Tool Call / IPC  │                       │  Audio Response / State
                                        ▼                       ▼
      +-----------------------------------------+   +-----------------------------------------+
      |      AUTONOMOUS OS CONTROLLER           |   |       HOLOGRAPHIC SPATIAL DESKTOP       |
      | - Hyprland Window Management & Tiling   |   | - Arc Reactor Core HUD (State & Audio)  |
      | - Application Execution (POSIX/XDG)     |   | - Spatial JIT Floating Widgets (Image#3)|
      | - PipeWire Audio / Brightness / Power   |   | - Chamfered Data Cards, Charts, & PiP   |
      | - Browser Automation & Android ADB      |   | - Unified Top Bar & System Tray         |
      +-----------------------------------------+   +-----------------------------------------+
                                        │                       │
                                        ▼                       ▼
                      +-----------------------------------------------------------+
                      |              SHARED ARCH LINUX INFRASTRUCTURE             |
                      |  Arch Linux Rolling • Kernel 7.2 • systemd • Mesa / DRM   |
                      +-----------------------------------------------------------+
```

### The Non-Interference Mandate (Omarchy Coexistence)
The host machine currently runs Arch Linux with Omarchy. **JARVIS OS will never alter, overwrite, or mutate the existing Omarchy desktop files.** 

The user selects between two completely isolated desktop sessions at the SDDM display manager login screen:
1. **Omarchy Session**: Stock environment preserved identically (`~/.config/hypr/`, `/usr/share/omarchy/`).
2. **JARVIS OS Session**: Pure sovereign environment (`~/.config/jarvis/hypr/`, `~/.config/jarvis/shell/`, independent session target).

---

## 2. Spatial Visual Experience (The Reference Interface)

Based on the holographic multi-card interface, the desktop is organized as a dynamic **Spatial Intelligence Canvas**:

```
+-----------------------------------------------------------------------------------------------------------------+
| [14:02:45] [W1: DEV]  [AUDIO WAVEFORM PILL: ● REC]   [CPU: 18%  RAM: 6.2G] [BAT: 94%] [NET: 120M] [TRAY]     | <- Top Bar (32px)
+-----------------------------------------------------------------------------------------------------------------+
|                                                                                                                 |
|  +--------------------+                                       +--------------------------------+                |
|  | [PiP STREAM]       |     +-------------------------+       | [COMPARISON MATRIX]            |                |
|  | Live Video / Camera|     | [STAT COUNTER]          |       | Meta Quest 3 vs 3S             |                |
|  | Feed Monitor       |     |  100+ Active Tasks      |       | Spec Matrix & Architecture     |                |
|  +--------------------+     +-------------------------+       +--------------------------------+                |
|                                                                                                                 |
|  +--------------------------------+     +-------------------------------+     +-------------------------------+ |
|  | [BAR CHART TELEMETRY]          |     |                               |     | [BAR CHART TELEMETRY]         | |
|  | Performance Throughput (FPS)   |     |      ACTIVE FOCUSED WORKSPACE |     | Model Inference Latency (ms)  | |
|  | Real-time hardware telemetry   |     |      (e.g., Neovim / Terminal)|     | Real-time token streaming     | |
|  +--------------------------------+     |                               |     +-------------------------------+ |
|                                         +-------------------------------+                                       |
|  +--------------------------------+                                           +-------------------------------+ |
|  | [TECHNICAL SPEC CARD]          |     +-------------------------------+     | [HARDWARE 3D / DEVICE VIEW]   | |
|  | Kernel: 7.2.15-1-omarchy       |     | [AUDIO / ASR TRANSCRIPT]      |     | Connected Sensors / ADB Phone | |
|  | Compositor: Hyprland v0.56.2   |     | Live Intent & Tool Feedback   |     | Physical Hardware Status      | |
|  +--------------------------------+     +-------------------------------+     +-------------------------------+ |
|                                                                                                                 |
|                                                                                         +---------------------+ |
|                                                                                         | (●) ARC REACTOR HUD | |
|                                                                                         | Live Audio Energy   | |
|                                                                                         | Pulsing Core Visual | |
|                                                                                         +---------------------+ |
+-----------------------------------------------------------------------------------------------------------------+
```

### Visual Specifications
1. **Color Palette**:
   - Deep Obsidian Void: `#020408` to `#050914` (replaces video wallpaper engines).
   - Primary Vector Glow: Electric Cyan (`#00e5ff`).
   - Secondary Alert/Warning Accent: Golden Amber (`#ffb020`).
   - Critical Alert: Crimson Pulse (`#ff3366`).
   - Translucent Chamfered Glass: `rgba(2, 11, 20, 0.78)` with subtle 1px border `rgba(0, 229, 255, 0.25)`.
2. **JIT Dynamic Widget Surfaces**:
   - Floating glass cards with angled chamfered borders and technical status coordinates.
   - Built-in primitives: Bar charts, KPI stat counters, comparison tables, monospace code blocks, progress trackers, video PiP, and technical spec matrices.
   - Cards appear smoothly when relevant, track with active windows, and dissolve when dismissed or expired.
3. **Arc Reactor Core HUD**:
   - Mounted in the bottom-right or center-bottom.
   - Driven by real audio RMS energy and conversational state (`Listening`, `Thinking`, `Speaking`, `Executing Tool`).

---

## 3. Audited System State & Current Bottlenecks

### Host Specifications (Audited Nov 2026)
- **Base OS**: Arch Linux with Omarchy 4.5.0 layer (`Kernel: 7.2.15-1-omarchy`).
- **Compositor**: Hyprland v0.56.2 (Wayland session `wayland-1`, display scaling 1.5x on 1080p).
- **Core Repository**: `/home/g0pi/JARVIS OS` (Git branch: `JARVIS-OS`).
- **Active Runtime**: `/home/g0pi/.local/share/jarvis-runtime/current`.

### Critical Conflicts Discovered
1. **Dual-Shell Collision**:
   - Omarchy Quickshell (PID 1404) and JARVIS Quickshell (PID 39011) run simultaneously.
   - Both bind to Wayland `WlrLayer.Bottom`, creating overlapping bottom surfaces and redundant CPU/GPU polling.
2. **Wallpaper Engine Resource Drain**:
   - `owed.service` (PID 1467) actively decodes video wallpapers on Layer 0, even though JARVIS mounts an opaque cyber canvas on Layer 1 over it.
3. **Hardcoded Omarchy IPC in Widget Backend**:
   - In `ui/jarvis_widgets/backend.py:213`, `shell_call()` invokes `omarchy-shell jarvis-canvas`. This tethers the dynamic widget engine to Omarchy.
4. **Shell Architecture Incompleteness**:
   - `ui/jarvis_shell/TopBar.qml` is drawn inside the bottom-layer HUD rather than as an exclusive top panel (`WlrLayer.Top`) with reserved screen bounds (32px).
   - No native freedesktop notification daemon (`org.freedesktop.Notifications`) exists in standalone JARVIS; notifications currently leak to Omarchy's dynamic island.
5. **Compositor Bootstrap Coupling**:
   - Hyprland currently requires `/usr/share/omarchy/default/hypr/bootstrap.lua`. A sovereign `hyprland.conf` / `hyprland.lua` is required.

---

## 4. Total Sovereign Architecture

### 4.1 Layer-Shell Composition (Unified Quickshell Process)
JARVIS OS runs as a single, lightweight Quickshell process managing three clean Wayland layers:

```
[Screen Space (1920x1080 @ 1.5x Scaling)]
│
├── Layer 2: TOP (Exclusive Zone: 32px)
│   └── JarvisTopBar.qml
│       ├── Workspaces & Active Window Title
│       ├── Audio Visualizer Capsule (PipeWire Level Meter)
│       ├── System Telemetry (CPU / RAM / GPU / Battery)
│       └── Native SNI System Tray & Clock
│
├── Application Tiling Layer (Hyprland Managed Windows)
│   └── Terminals, Editors, Browsers, IDEs (Tiled or Floating)
│
├── Layer 1: BOTTOM (ExclusionMode: Ignore)
│   └── JarvisDesktopSurface.qml
│       ├── Procedural Cybernetic Atmosphere (Dark Gradient & Grid)
│       ├── Arc Reactor Core HUD (Responsive to voice RMS)
│       └── Spatial JIT Dynamic Widgets (Charts, Metrics, Spec Cards)
│
└── Layer 3: OVERLAY (On-Demand / Floating)
    ├── JarvisInputBar.qml (Spoken voice transcript & keyboard input)
    └── JarvisNotificationBanner.qml (Native org.freedesktop.Notifications)
```

### 4.2 Voice-First & Tool Execution Engine
- **Duplex Audio Loop**: Persistent bidirectional WebSocket to Google Gemini Multimodal Live (`gemini-3.8-live`, voice: Aoede) over PipeWire AEC capture pipeline (`jarvis_aec`).
- **Offline Fallback**: Seamless local failover to Whistle (ASR) + Needle (SLM/tool router) when network drops.
- **Handsfree OS Controller**: 287 registered tools in `jarvis_control/tools.py` executing:
  - Window movement, workspace switching, application focus via `hyprctl`.
  - Application launching via standard `.desktop` XDG execution.
  - Volume, audio sinks, brightness, and system power states.
  - Wayland screen awareness via `grim` snapshot buffer.
  - External web automation and phone control via ADB.
- **Dynamic Widget Tool**: Gemini issues `render_widget(kind="view"|"chart"|"table", spec={...})` to materialize interactive visual cards directly onto the spatial desktop.

---

## 5. Comprehensive Build & Decoupling Map

This actionable roadmap details the exact steps to build JARVIS OS and achieve total independence from Omarchy.

```
PHASE 1: Session Foundation & Environment Scaffolding
   ├── 1.1 Create ~/.config/jarvis/{hypr,shell} directory trees
   ├── 1.2 Write /usr/share/wayland-sessions/jarvis-os.desktop
   ├── 1.3 Write /usr/bin/jarvis-session (Isolated runtime, UWSM envelope)
   └── 1.4 Write sovereign ~/.config/jarvis/hypr/hyprland.conf (Zero Omarchy Lua)

PHASE 2: Shell Engine Consolidation & Decoupling
   ├── 2.1 Refactor backend.py (Line 213): Redirect from omarchy-shell to jarvis socket
   ├── 2.2 Unify TopBar.qml & Shell.qml into single Quickshell ShellRoot
   ├── 2.3 Implement WlrLayer.Top for TopBar with 32px exclusive monitor reservation
   ├── 2.4 Implement native freedesktop Notification D-Bus service in JARVIS shell
   └── 2.5 Build native application search/launcher to eliminate omarchy-menu dependency

PHASE 3: Spatial JIT Widget Engine Maturity (Matching Reference Image)
   ├── 3.1 Pre-compile Holographic Card Templates (Bar Charts, Stat Counters, Spec Matrix, PiP)
   ├── 3.2 Implement Coordinate-Aware Spatial Placement (Anchor widgets to active windows)
   ├── 3.3 Wire SQLite persistence (~/.local/state/jarvis/widgets.db) for pinned cards
   └── 3.4 Wire real-time data providers (PipeWire, sysinfo, task pipelines) to card models

PHASE 4: Voice-First Autonomous OS Integration
   ├── 4.1 Standardize NDJSON socket protocol ($XDG_RUNTIME_DIR/jarvis/shell.sock)
   ├── 4.2 Harden PipeWire AEC capture filter for persistent wake-word & barge-in
   ├── 4.3 Connect Gemini Live tool routing directly to dynamic widget spawner
   └── 4.4 Validate full handsfree desktop navigation (voice alone controls whole system)

PHASE 5: Systemd Unit Integration & SDDM Dual-Session Verification
   ├── 5.1 Create jarvis-session.target and user units (jarvis-shell, jarvis-voice)
   ├── 5.2 Configure SDDM to present both Omarchy and JARVIS OS
   ├── 5.3 Verify memory budget (<120 MiB GUI, <180 MiB Core) and zero-conflict dual boot
   └── 5.4 Run scripts/verify_voice_lock.py to ensure voice baseline integrity
```

---

## 6. Actionable Implementation Checklists

### Milestone 1: Session Isolation & Environment Scaffolding
- [ ] **Directory Scaffolding**: Create `~/.config/jarvis/hypr/` and `~/.config/jarvis/shell/`.
- [ ] **Wayland Desktop Entry**: Create `/usr/share/wayland-sessions/jarvis-os.desktop`:
  ```desktop
  [Desktop Entry]
  Name=JARVIS OS
  Comment=AI-Native Desktop Environment powered by Gemini Live & Quickshell
  Exec=/usr/bin/jarvis-session
  Type=Application
  DesktopNames=JARVIS-OS
  Keywords=Wayland;Hyprland;JARVIS;AI;Desktop;
  ```
- [ ] **Session Runner (`/usr/bin/jarvis-session`)**:
  - Export `XDG_CURRENT_DESKTOP="JARVIS-OS"`.
  - Initialize `$XDG_RUNTIME_DIR/jarvis/` and `~/.local/state/jarvis/`.
  - Launch Hyprland with dedicated config `--config ~/.config/jarvis/hypr/hyprland.conf`.
- [ ] **Sovereign Hyprland Config**: Create standalone `hyprland.conf` with:
  - Standard keybindings (`SUPER + SPACE` for launcher, `SUPER + V` for voice toggle, `SUPER + Q` for close).
  - Autostart directives: `systemctl --user start jarvis-session.target`.
  - Window rules: Float widget cards, blur background layers, remove Omarchy decoration hooks.

### Milestone 2: Quickshell Consolidation & Decoupling
- [ ] **Eliminate Dual-Shell Collision**:
  - Remove `"jarvis-shell"` entry from `~/.config/omarchy/shell.json`.
  - Retain Omarchy shell strictly for the Omarchy login session.
- [ ] **Refactor `ui/jarvis_widgets/backend.py`**:
  - Replace line 213 `shutil.which("omarchy-shell")` with direct IPC to `$XDG_RUNTIME_DIR/jarvis/shell.sock` or `quickshell ipc`.
- [ ] **Construct Single `ShellRoot` in `ui/jarvis_shell/Shell.qml`**:
  - Top Bar: `WlrLayer.Top`, `exclusionMode: ExclusionMode.Normal`, `exclusiveZone: 32`.
  - Holographic Canvas: `WlrLayer.Bottom`, `exclusionMode: ExclusionMode.Ignore`.
- [ ] **Native Top Bar Implementation**:
  - Workspaces indicator (listening to Hyprland socket2).
  - PipeWire audio visualizer pill.
  - SNI System Tray receiver (`Quickshell.Services.SystemTray`).
  - Battery, network, and system load dials.
- [ ] **Native Notifications**: Implement `org.freedesktop.Notifications` handler in QML to display cybernetic alert cards without Omarchy Dynamic Island.

### Milestone 3: Spatial JIT Widget Engine (Reference Image Alignment)
- [ ] **Card Components (`ui/jarvis_widgets/`)**:
  - `TelemetryCard.qml`: Radial gauges and multi-bar vertical charts.
  - `ComparisonCard.qml`: Two-column attribute matrix for hardware and data comparison.
  - `StatCard.qml`: Bold numeric KPI indicators with trend lines (`100+`, `≈20m`).
  - `MediaPipCard.qml`: Floating video / device visualizer with chamfered brackets.
  - `TaskPipelineCard.qml`: Stepped agent task execution tracker.
- [ ] **Spatial Coordinate Resolver**:
  - Query Hyprland for active window rect `(X, Y, W, H)`.
  - Resolve placement coordinates: spawn telemetry cards alongside the active window without overlapping.
- [ ] **State Persistence**:
  - Store card layout, pinned status, and position coordinates in `~/.local/state/jarvis/widgets.db` (SQLite).
  - Automatically restore pinned cards upon login.

### Milestone 4: Voice-First Total OS Control
- [ ] **Gemini Tool Routing**:
  - Ensure tool calls from Gemini Live automatically invoke `render_widget()` with validated AST schemas.
  - Ensure handsfree window manipulation, audio adjustment, and file navigation complete without mouse clicks.
- [ ] **Screen & Camera Perception**:
  - Connect `grim` framebuffer stream to Gemini Live session for real-time visual context.
- [ ] **Verification**:
  - Run `python scripts/verify_voice_lock.py` to ensure core voice code remains untouched.

### Milestone 5: Verification & System Hardening
- [ ] **SDDM Verification**:
  - Test login to Omarchy: Confirms Omarchy bar, dock, and theme are completely intact.
  - Test login to JARVIS OS: Confirms pure holographic desktop boots with independent top bar and dynamic widgets.
- [ ] **Resource Audit**:
  - Verify idle GUI footprint: `< 120 MiB RSS`.
  - Verify idle Voice Core footprint: `< 180 MiB RSS`.
  - Verify zero dual-process collisions or competing layer-shell surfaces.

---

## 7. Verification & Acceptance Matrix

| Category | Verification Test | Expected Pass Criteria |
| :--- | :--- | :--- |
| **Session Isolation** | Log in to Omarchy, execute `hyprctl layers` | Zero JARVIS processes running; stock Omarchy bar/island active |
| **Independent Boot** | Select "JARVIS OS" in SDDM, log in | Boots cleanly into Hyprland; `jarvis-shell` active; no Omarchy daemons |
| **Double-Shell Check** | Run `pgrep -a quickshell` in JARVIS | Exactly 1 quickshell process running pointing to `jarvis_shell/Shell.qml` |
| **Wallpaper Efficiency**| Run `systemctl --user status owed` in JARVIS | `owed.service` is inactive/masked; zero background video decoding |
| **Spatial Widget Spawn**| Speak: *"Jarvis, show telemetry and compare specs"*| Holographic bar chart and comparison cards spawn beside active window |
| **Handsfree Control** | Speak: *"Open foot terminal and tile to workspace 2"* | Window opens and moves handsfree; audio confirmation given |
| **Voice Lock Integrity**| Run `python scripts/verify_voice_lock.py` | All voice checksums match recorded baseline; zero regressions |
