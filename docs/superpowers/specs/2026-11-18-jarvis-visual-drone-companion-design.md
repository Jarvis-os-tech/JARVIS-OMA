# Specification: JARVIS Visual Drone Companion (Desktop Avatar)

* **Date:** 2026-11-18
* **Author:** Gopi & Antigravity
* **Status:** Draft / Pending Review
* **Target Environment:** Linux (Arch/Omarchy), Hyprland (Wayland), Node/Electron or Webview runner

---

## 1. Overview & Objectives

JARVIS currently operates as a background intelligence and voice layer with top-bar/island widgets. This project introduces a visual, physical "body" for JARVIS: an articulated holographic sci-fi micro-drone that freely navigates the user's desktop, exhibits organic robotic behaviors, and serves as an interactive companion.

### Core Objectives
1. **Interactive Desktop Presence:** A floating 3D holographic drone that hovers, roams, and can be clicked, grabbed, and flung across the screen with natural inertia.
2. **True Click-Through:** The transparent canvas across the screen passes 100% of mouse interactions through to underlying windows; only the compact (84×84 px) drone hitbox intercepts clicks and drags.
3. **Agent State Expression:** Visually conveys what JARVIS is doing (Idle, Listening, Thinking, Speaking, Completed, Alert) using continuous kinetic postures and one-shot physical gestures (`nod`, `gyroRoll`, `recoil`).
4. **Desktop Courtesy (Auto-Dodge):** Drifts gently away from active typing and cursor activity to remain accessible without obstructing active work.
5. **Bidirectional IPC:** Listens to JARVIS OS voice and agent lifecycle events over a local WebSocket/IPC bridge, and triggers voice listening when tapped.

---

## 2. Visual & Kinetic Design

### 2.1 Anatomy
The drone is composed of nested 3D transform layers rendered via GPU-accelerated CSS and Web Animations:
* **Ambient Aura:** Soft radial glow (`--accent-glow`) reflecting the active state color.
* **Gimbal Halo:** Outer neon energy ring inclined at 68° with continuous 360° rotational spin.
* **Articulated Stabilizer Wings:** Dual mechanical pods that dynamically pitch, splay, or retract based on motion and state.
* **Armored Spherical Core:** Dark-metallic chassis housing the primary sensor crest and ventral thruster emitter.
* **Optic Visor:** OLED visor displaying dual cursor-tracking optic eyes with randomized blinking and a lateral thinking scan beam.

### 2.2 State Machine & Visual Postures
| State | Accent Color | Continuous Body Posture | Visor / Wings Behavior |
|---|---|---|---|
| **Idle** | Cyan (`#22d3ee`) | Gentle zero-G hovering drift (3.6s loop) | Visor eyes track cursor; natural blinks every 2–5s |
| **Listening** | Bright Blue (`#3b82f6`) | Attentive forward pitch (16–20° lean) | Wings splay outward; eyes enlarge; auto-triggers `nod` |
| **Thinking** | Purple (`#8b5cf6`) | Rapid side-to-side analytical scanning | Wings tuck; gimbal spins at 2x; visor scan-beam sweeps |
| **Speaking** | Neon Teal (`#06b6d4`) | Rhythmic vocal cadence bounce (0.42s) | Optic eyes pulse vertically in sync with speech rhythm |
| **Complete** | Emerald (`#10b981`) | Thruster flares to 1.6x scale | Executes celebratory 360° `gyroRoll`, then settles to `idle` |
| **Alert** | Amber (`#f59e0b`) | Defensive backward pitch | Wings splay wide; eyes narrow; auto-triggers `recoil` |

### 2.3 One-Shot Kinematic Gestures
Executed on an isolated transform layer with `composite: "add"` to prevent interruption of continuous hover loops:
* **`nod` (480ms):** Affirmative double forward pitch-nod upon wake-word trigger or command acknowledgment.
* **`gyroRoll` (680ms):** 360° celebratory barrel roll along pitch and roll axes upon task success.
* **`recoil` (540ms):** Startled backward recoil and dual horizontal wobble upon execution error or alert.

---

## 3. Desktop Integration & Wayland Architecture

### 3.1 Hyprland Rules
The overlay window runs with application class `jarvis-drone`:
```ini
windowrulev2 = float, class:^(jarvis-drone)$
windowrulev2 = pin, class:^(jarvis-drone)$
windowrulev2 = noborder, class:^(jarvis-drone)$
windowrulev2 = noshadow, class:^(jarvis-drone)$
windowrulev2 = nodim, class:^(jarvis-drone)$
windowrulev2 = opacity 1.0 override 1.0 override, class:^(jarvis-drone)$
windowrulev2 = noinitialfocus, class:^(jarvis-drone)$
```

### 3.2 Dynamic Click-Through (Mouse Passthrough)
* **Hitbox Filtering:** The host window manages mouse event passthrough:
  * When the mouse pointer is outside the drone's 84×84 interactive boundary, mouse event capture is disabled (`setIgnoreMouseEvents(true, { forward: true })`). All clicks and scrolls pass through to whatever window is behind it.
  * When the pointer enters the drone's boundary, mouse capture is activated (`setIgnoreMouseEvents(false)`), allowing instant hover, drag, and click handling.

---

## 4. Physics & Roaming Mechanics

### 4.1 Inertial Drag & Fling
1. **Grab (`pointerdown`):** Pointer capture is acquired via `setPointerCapture`. Active roaming/patrol stops immediately.
2. **Move (`pointermove`):** Drone anchor tracks pointer coordinates. Release velocity samples $\vec{v} = (\Delta x / \Delta t, \Delta y / \Delta t)$ are averaged over the last 5 frames.
3. **Release (`pointerup`):**
   * If total drag distance is $< 5\text{ px}$, it is registered as a **tap**: triggers JARVIS voice prompt / command input.
   * If dragged and released with velocity, the drone enters an inertial glide loop:
     $$\vec{v}_{t+1} = \vec{v}_t \times 0.92$$
     Once $\|\vec{v}\| < 0.5\text{ px/frame}$, the drone settles into its target hover coordinates.
4. **Boundary Clamping:** Positions are bounded within $[10, \text{screenWidth} - 150]$ and $[10, \text{screenHeight} - 150]$ with soft bounce elasticity.

### 4.2 Autonomous Patrol & Auto-Dodge
* **Idle Patrol:** After 15 seconds without user interaction or active voice tasks, the drone periodically selects random points within screen margins and drifts smoothly using cubic-bezier interpolation ($30\text{--}50\text{ px/s}$).
* **Auto-Dodge:** When mouse velocity is high near the drone, or if typing focus is active in the vicinity, the drone applies a gentle repulsive vector away from the cursor.

---

## 5. IPC Bridge & Event Contracts

### 5.1 Transport
A local WebSocket server hosted by a lightweight Python bridge or embedded in the runner:
* URL: `ws://127.0.0.1:8765`
* Fallback: Standalone operation with demo shortcuts and internal state machine if bridge is offline.

### 5.2 Schema: JARVIS Core → Drone Overlay
```json
{
  "version": "1.0",
  "type": "STATE",
  "state": "idle" | "listening" | "thinking" | "speaking" | "complete" | "alert"
}
```
```json
{
  "version": "1.0",
  "type": "GESTURE",
  "name": "nod" | "gyroRoll" | "recoil"
}
```

### 5.3 Schema: Drone Overlay → JARVIS Core
```json
{
  "version": "1.0",
  "event": "DRONE_TAP",
  "action": "TOGGLE_VOICE_LISTENING"
}
```

---

## 6. Directory & File Structure

```
ui/jarvis_drone/
├── index.html           # Full 3D animated micro-drone (HTML/CSS/JS)
├── main.js              # Frameless transparent Wayland runner with dynamic click-through
├── package.json         # Runtime manifest & scripts
├── bridge.py            # Local WebSocket bridge connecting JARVIS voice/agent events
├── launch.sh            # Hyprland rule setup and runner startup script
└── tests/
    └── test_bridge.py   # Automated IPC event test suite
```

---

## 7. Error Handling & Edge Cases

1. **Wayland / Hyprland Display Changes:** Listen to `window.resize` events and re-clamp drone position within active display bounds.
2. **IPC Disconnect:** If the WebSocket connection drops, the drone logs a warning, falls back to local autonomous patrol, and attempts exponential-backoff reconnection every 3 seconds.
3. **Off-Screen Prevention:** Regardless of flings or window resizing, coordinates are strictly clamped to visible viewports.
4. **Performance Throttling:** Cursor tracking and render loop use `requestAnimationFrame`; when the drone is stationary and state is unchanged, transform updates minimize GPU utilization.

---

## 8. Verification & Acceptance Criteria

1. **Visual Fidelity:** Drone renders with 3D gimbal ring, articulated wings, optic visor, and thruster glow at steady 60+ FPS.
2. **Click-Through Verification:** Clicking anywhere on the screen outside the drone's 84×84 hitbox interacts directly with windows below without losing desktop focus.
3. **Drag & Fling Verification:** Dragging is smooth with zero cursor slip; throwing the drone produces realistic deceleration into a hover.
4. **State Machine Verification:** Switching states triggers the exact color shifts, postures, and gesture animations defined in Section 2.
5. **IPC Verification:** Sending JSON commands to `ws://127.0.0.1:8765` transitions the drone instantly between states.
