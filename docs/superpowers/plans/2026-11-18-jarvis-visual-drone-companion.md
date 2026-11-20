# JARVIS Visual Drone Companion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an interactive, draggable 3D holographic drone avatar for JARVIS OS that roams the Hyprland desktop with hardware click-through transparency and synchronizes live with JARVIS voice/agent states.

**Architecture:** An Electron-based transparent, borderless overlay window running on Hyprland (`wlr-foreign-toplevel` / Wayland) with dynamic mouse passthrough (`setIgnoreMouseEvents`). The overlay renders an articulated 3D micro-drone in CSS/JS with inertial fling physics, cursor tracking, and continuous posture loops. A local Python WebSocket bridge synchronizes JARVIS OS events (wake-word, LLM thinking, TTS speech, task completion, alert) to the drone.

**Tech Stack:** JavaScript (ES6+), CSS 3D Transforms, Web Animations API, Electron v45+, Python 3 (websockets, asyncio), Hyprland IPC (`hyprctl`).

**Spec:** [docs/superpowers/specs/2026-11-18-jarvis-visual-drone-companion-design.md](file:///home/g0pi/JARVIS%20OS/docs/superpowers/specs/2026-11-18-jarvis-visual-drone-companion-design.md)

## Global Constraints
- Platform: Linux (Wayland / Hyprland)
- Window Class: `jarvis-drone`
- Drone Hitbox: 84×84 px interactive core; outer area must be 100% click-through to underlying desktop windows
- WebSocket Bridge: `ws://127.0.0.1:8765`
- Gestures: `nod`, `gyroRoll`, `recoil`
- States: `idle`, `listening`, `thinking`, `speaking`, `complete`, `alert`

---

### Task 1: Python WebSocket Bridge & Event Broker

**Files:**
- Create: `ui/jarvis_drone/bridge.py`
- Test: `tests/test_jarvis_drone_bridge.py`

**Interfaces:**
- Consumes: JARVIS state events (`type: "STATE"`, `type: "GESTURE"`)
- Produces: WebSocket server on `127.0.0.1:8765`, client broadcast method `broadcast_state(state)`, `broadcast_gesture(gesture)`, and incoming tap handler `on_drone_tap()`

- [ ] **Step 1: Write the failing test for the WebSocket bridge**

```python
# tests/test_jarvis_drone_bridge.py
import pytest
import asyncio
import json
import websockets
from ui.jarvis_drone.bridge import DroneBridge

@pytest.mark.asyncio
async def test_bridge_broadcast_state_and_gesture():
    bridge = DroneBridge(host="127.0.0.1", port=8765)
    server_task = asyncio.create_task(bridge.start())
    await asyncio.sleep(0.1)

    try:
        async with websockets.connect("ws://127.0.0.1:8765") as ws:
            # Broadcast state
            await bridge.broadcast_state("listening")
            msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=1.0))
            assert msg == {"type": "STATE", "state": "listening"}

            # Broadcast gesture
            await bridge.broadcast_gesture("nod")
            msg2 = json.loads(await asyncio.wait_for(ws.recv(), timeout=1.0))
            assert msg2 == {"type": "GESTURE", "name": "nod"}

            # Send tap from client to bridge
            taps = []
            bridge.register_tap_handler(lambda: taps.append(True))
            await ws.send(json.dumps({"event": "DRONE_TAP", "action": "TOGGLE_VOICE_LISTENING"}))
            await asyncio.sleep(0.1)
            assert len(taps) == 1
    finally:
        await bridge.stop()
        server_task.cancel()
        try:
            await server_task
        except asyncio.CancelledError:
            pass
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_jarvis_drone_bridge.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ui.jarvis_drone.bridge'`

- [ ] **Step 3: Implement DroneBridge in Python**

```python
# ui/jarvis_drone/bridge.py
import asyncio
import json
import logging
from typing import Callable, Optional, Set
import websockets

logger = logging.getLogger("jarvis_drone_bridge")

class DroneBridge:
    def __init__(self, host: str = "127.0.0.1", port: int = 8765):
        self.host = host
        self.port = port
        self.clients: Set[websockets.WebSocketServerProtocol] = set()
        self.server: Optional[websockets.server.Serve] = None
        self._tap_handlers = []
        self._running = False

    def register_tap_handler(self, handler: Callable[[], None]):
        self._tap_handlers.append(handler)

    async def _handle_connection(self, websocket):
        self.clients.add(websocket)
        logger.info(f"Drone client connected: {websocket.remote_address}")
        try:
            async for message in websocket:
                try:
                    data = json.loads(message)
                    if data.get("event") == "DRONE_TAP":
                        for handler in self._tap_handlers:
                            handler()
                except Exception as e:
                    logger.error(f"Error handling message: {e}")
        finally:
            self.clients.remove(websocket)
            logger.info("Drone client disconnected")

    async def broadcast_state(self, state: str):
        if not self.clients:
            return
        payload = json.dumps({"type": "STATE", "state": state})
        await asyncio.gather(
            *[client.send(payload) for client in self.clients],
            return_exceptions=True
        )

    async def broadcast_gesture(self, gesture: str):
        if not self.clients:
            return
        payload = json.dumps({"type": "GESTURE", "name": gesture})
        await asyncio.gather(
            *[client.send(payload) for client in self.clients],
            return_exceptions=True
        )

    async def start(self):
        self._running = True
        self.server = await websockets.serve(self._handle_connection, self.host, self.port)
        await self.server.wait_closed()

    async def stop(self):
        self._running = False
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        for client in list(self.clients):
            await client.close()
        self.clients.clear()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    bridge = DroneBridge()
    print(f"Starting Drone WebSocket Bridge on ws://{bridge.host}:{bridge.port}...")
    try:
        asyncio.run(bridge.start())
    except KeyboardInterrupt:
        print("Bridge stopped.")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_jarvis_drone_bridge.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add ui/jarvis_drone/bridge.py tests/test_jarvis_drone_bridge.py
git commit -m "feat(drone): implement Python WebSocket bridge and tests"
```

---

### Task 2: Articulated 3D Drone Frontend with Fling Physics & IPC Integration

**Files:**
- Create: `ui/jarvis_drone/index.html`

**Interfaces:**
- Consumes: WebSocket messages from `ws://127.0.0.1:8765`, cursor movements, drag events
- Produces: Interactive rendered drone on `#jarvis-stage`, global `window.jarvisDrone` controller, WebSocket tap notifications

- [ ] **Step 1: Create `ui/jarvis_drone/index.html` with complete styling, 3D anatomy, gestures, and physics**

Write the complete HTML application into `ui/jarvis_drone/index.html` featuring:
1. Composable 3D layers: gimbal ring, stabilizer wings, core head shell, visor with cursor-tracking optics and scan beam, ventral thruster.
2. Inertial fling physics ($v_{t+1} = v_t \times 0.92$), screen boundary clamping, and auto-patrol drift.
3. Additive kinematic gestures (`nod`, `gyroRoll`, `recoil`) via Web Animations API.
4. Auto-reconnecting WebSocket client connecting to `ws://127.0.0.1:8765`.
5. IPC communication sending `{"event": "DRONE_TAP", "action": "TOGGLE_VOICE_LISTENING"}` on tap.
6. Electron mouse passthrough notification: dispatching `drone-hover` events so the Electron main process can toggle click-through dynamically.

- [ ] **Step 2: Verify HTML syntax and DOM integrity**

Run: `node -e 'const fs = require("fs"); const content = fs.readFileSync("ui/jarvis_drone/index.html", "utf8"); console.log("HTML byte length:", content.length);'`
Expected: Valid HTML file with > 5000 bytes.

- [ ] **Step 3: Commit**

```bash
git add ui/jarvis_drone/index.html
git commit -m "feat(drone): create 3D animated micro-drone frontend with fling physics"
```

---

### Task 3: Electron Frameless Transparent Overlay Runner

**Files:**
- Create: `ui/jarvis_drone/package.json`
- Create: `ui/jarvis_drone/main.js`

**Interfaces:**
- Consumes: `ui/jarvis_drone/index.html`
- Produces: Transparent, frameless, pinned Wayland window with dynamic `setIgnoreMouseEvents`

- [ ] **Step 1: Create `ui/jarvis_drone/package.json`**

```json
{
  "name": "jarvis-drone-companion",
  "version": "1.0.0",
  "description": "JARVIS Visual Drone Companion for Hyprland",
  "main": "main.js",
  "scripts": {
    "start": "electron ."
  },
  "devDependencies": {
    "electron": "^34.0.0"
  }
}
```

- [ ] **Step 2: Create `ui/jarvis_drone/main.js`**

Implement the Electron host with:
- Transparent, borderless, frameless window.
- Always-on-top, skip taskbar, `hasShadow: false`.
- IPC listener for `set-ignore-mouse-events`:
  ```javascript
  const { app, BrowserWindow, ipcMain, screen } = require('electron');
  const path = require('path');

  let win = null;

  function createWindow() {
    const primaryDisplay = screen.getPrimaryDisplay();
    const { width, height } = primaryDisplay.bounds;

    win = new BrowserWindow({
      width,
      height,
      x: 0,
      y: 0,
      transparent: true,
      frame: false,
      alwaysOnTop: true,
      skipTaskbar: true,
      hasShadow: false,
      enableLargerThanScreen: true,
      webPreferences: {
        nodeIntegration: false,
        contextIsolation: true,
        preload: path.join(__dirname, 'preload.js')
      }
    });

    // Default: pass mouse events through empty space
    win.setIgnoreMouseEvents(true, { forward: true });

    win.loadFile(path.join(__dirname, 'index.html'));
  }

  ipcMain.on('set-ignore-mouse-events', (event, ignore, options) => {
    const webContents = event.sender;
    const window = BrowserWindow.fromWebContents(webContents);
    if (window) {
      window.setIgnoreMouseEvents(ignore, options);
    }
  });

  app.whenReady().then(createWindow);

  app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') app.quit();
  });
  ```

- [ ] **Step 3: Create `ui/jarvis_drone/preload.js`**

```javascript
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  setIgnoreMouseEvents: (ignore, options) => {
    ipcRenderer.send('set-ignore-mouse-events', ignore, options);
  }
});
```

- [ ] **Step 4: Verify Electron syntax and files**

Run: `node -c ui/jarvis_drone/main.js && node -c ui/jarvis_drone/preload.js`
Expected: Clean exit with zero syntax errors.

- [ ] **Step 5: Commit**

```bash
git add ui/jarvis_drone/package.json ui/jarvis_drone/main.js ui/jarvis_drone/preload.js
git commit -m "feat(drone): add Electron transparent overlay runner with dynamic click-through"
```

---

### Task 4: Hyprland Window Rules & Convenience Launcher

**Files:**
- Create: `ui/jarvis_drone/launch.sh`

**Interfaces:**
- Consumes: Hyprland compositor socket (`hyprctl`), Python bridge, Electron binary
- Produces: Injected Hyprland window rules and running companion process

- [ ] **Step 1: Write `ui/jarvis_drone/launch.sh`**

```bash
#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 1. Apply dynamic Hyprland window rules if hyprctl is available
if command -v hyprctl &>/dev/null; then
    echo "Configuring Hyprland window rules for jarvis-drone..."
    hyprctl keyword windowrulev2 "float, class:^(jarvis-drone-companion|electron)$" || true
    hyprctl keyword windowrulev2 "pin, class:^(jarvis-drone-companion|electron)$" || true
    hyprctl keyword windowrulev2 "noborder, class:^(jarvis-drone-companion|electron)$" || true
    hyprctl keyword windowrulev2 "noshadow, class:^(jarvis-drone-companion|electron)$" || true
    hyprctl keyword windowrulev2 "nodim, class:^(jarvis-drone-companion|electron)$" || true
    hyprctl keyword windowrulev2 "opacity 1.0 override 1.0 override, class:^(jarvis-drone-companion|electron)$" || true
fi

# 2. Start WebSocket bridge if not already running on port 8765
if ! ss -tuln | grep -q ":8765 "; then
    echo "Starting Drone WebSocket Bridge on port 8765..."
    python3 bridge.py &
    BRIDGE_PID=$!
    sleep 0.5
fi

# 3. Launch Electron Overlay
echo "Launching JARVIS Drone Companion..."
npx electron . "$@"
```

- [ ] **Step 2: Make executable and test syntax**

Run: `chmod +x ui/jarvis_drone/launch.sh && bash -n ui/jarvis_drone/launch.sh`
Expected: Syntax check passes with code 0.

- [ ] **Step 3: Commit**

```bash
git add ui/jarvis_drone/launch.sh
git commit -m "feat(drone): add Hyprland launcher script and window rule injector"
```

---

### Task 5: End-to-End Verification

**Files:**
- Test: `tests/test_jarvis_drone_integration.py`

- [ ] **Step 1: Write integration test script**

```python
# tests/test_jarvis_drone_integration.py
import pytest
import asyncio
import json
import websockets
from ui.jarvis_drone.bridge import DroneBridge

@pytest.mark.asyncio
async def test_full_agent_state_cycle():
    bridge = DroneBridge(port=8766)
    server_task = asyncio.create_task(bridge.start())
    await asyncio.sleep(0.1)

    received_states = []
    async def fake_drone_client():
        async with websockets.connect("ws://127.0.0.1:8766") as ws:
            while len(received_states) < 6:
                data = json.loads(await ws.recv())
                if data.get("type") == "STATE":
                    received_states.append(data.get("state"))

    client_task = asyncio.create_task(fake_drone_client())
    await asyncio.sleep(0.1)

    states = ["idle", "listening", "thinking", "speaking", "complete", "alert"]
    for s in states:
        await bridge.broadcast_state(s)
        await asyncio.sleep(0.05)

    await asyncio.wait_for(client_task, timeout=2.0)
    assert received_states == states

    await bridge.stop()
    server_task.cancel()
    try:
        await server_task
    except asyncio.CancelledError:
        pass
```

- [ ] **Step 2: Run all drone tests**

Run: `pytest tests/test_jarvis_drone_bridge.py tests/test_jarvis_drone_integration.py -v`
Expected: ALL PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_jarvis_drone_integration.py
git commit -m "test(drone): add end-to-end integration test for state cycle"
```
