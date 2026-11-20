import argparse
import asyncio
import json
import logging
import os
from pathlib import Path
import time
from typing import Any, Callable, Optional, Set
import websockets

logger = logging.getLogger("jarvis_drone_bridge")

# Default runtime paths for JARVIS OS
DEFAULT_RUNTIME_DIR = Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")) / "jarvis"
DEFAULT_STATE_FILE = DEFAULT_RUNTIME_DIR / "state.json"
DEFAULT_SOCKET_PATH = DEFAULT_RUNTIME_DIR / "control.sock"


class DroneBridge:
    def __init__(
        self,
        host: str = "127.0.0.1",
        port: Optional[int] = None,
        enable_jarvis_sync: bool = True,
        state_file: Optional[Path] = None,
        socket_path: Optional[Path] = None,
    ):
        self.host = host
        self.port = port if port is not None else int(os.environ.get("JARVIS_DRONE_PORT", "8768"))
        self.clients: Set[Any] = set()
        self.server: Optional[Any] = None
        self._tap_handlers = []
        self._running = False

        # JARVIS Voice Core Integration
        self.enable_jarvis_sync = enable_jarvis_sync
        self.jarvis_state_file = Path(state_file) if state_file else DEFAULT_STATE_FILE
        self.jarvis_socket_path = Path(socket_path) if socket_path else DEFAULT_SOCKET_PATH
        self.current_drone_state = "idle"
        self.last_tools_in_flight = 0
        self.sync_task: Optional[asyncio.Task] = None

    def register_tap_handler(self, handler: Callable[[], Any]):
        self._tap_handlers.append(handler)

    async def send_jarvis_command(self, cmd: str) -> Optional[str]:
        """Send a control command to JARVIS Voice Daemon over its Unix domain socket."""
        if not self.jarvis_socket_path.exists():
            logger.debug(f"JARVIS control socket does not exist at {self.jarvis_socket_path}")
            return None
        try:
            reader, writer = await asyncio.open_unix_connection(str(self.jarvis_socket_path))
            writer.write((cmd.strip() + "\n").encode())
            await writer.drain()
            line = await asyncio.wait_for(reader.readline(), timeout=1.5)
            writer.close()
            await writer.wait_closed()
            return line.decode().strip()
        except Exception as e:
            logger.warning(f"Error communicating with JARVIS control socket: {e}")
            return None

    def _map_jarvis_state(self, data: dict) -> str:
        """Map JARVIS daemon state and activity metrics into the 6 Drone states."""
        tools_in_flight = data.get("tools_in_flight", 0)
        raw_state = data.get("state", "idle")
        error = data.get("error", "")

        # Check for critical or alert notifications
        recent_alerts = data.get("recent_alerts", [])
        has_active_alert = False
        if recent_alerts and isinstance(recent_alerts, list):
            last_alert = recent_alerts[-1]
            if isinstance(last_alert, dict) and last_alert.get("priority") in ("critical", "alert"):
                if time.time() - last_alert.get("timestamp", 0) < 6:
                    has_active_alert = True

        if has_active_alert or (error and data.get("connected", True)):
            return "alert"
        if tools_in_flight > 0 or raw_state == "thinking":
            return "thinking"
        if raw_state == "speaking":
            return "speaking"
        if raw_state == "listening" and data.get("listening", True):
            return "listening"
        return "idle"

    async def _poll_jarvis_state(self):
        """Read atomic state.json and propagate state transitions & gestures."""
        if not self.jarvis_state_file.exists():
            return

        try:
            text = self.jarvis_state_file.read_text(encoding="utf-8")
            if not text.strip():
                return
            data = json.loads(text)
        except Exception:
            return

        tools_in_flight = data.get("tools_in_flight", 0)
        target_state = self._map_jarvis_state(data)

        # Detect tool completion: transition from running tools to 0
        if self.last_tools_in_flight > 0 and tools_in_flight == 0:
            logger.info("JARVIS task/tool execution completed: celebrating with gyroRoll")
            await self.broadcast_state("complete")
            await self.broadcast_gesture("gyroRoll")
            self.current_drone_state = "complete"
        elif target_state != self.current_drone_state:
            # Settle away from 'complete' automatically or follow new state
            logger.info(f"JARVIS state changed: {self.current_drone_state} -> {target_state}")
            self.current_drone_state = target_state
            await self.broadcast_state(target_state)

            if target_state == "listening":
                await self.broadcast_gesture("nod")
            elif target_state == "alert":
                await self.broadcast_gesture("recoil")

        self.last_tools_in_flight = tools_in_flight

    async def _jarvis_sync_loop(self):
        """Background coroutine that keeps drone companion synchronized with JARVIS."""
        logger.info(f"Starting JARVIS sync loop (monitoring {self.jarvis_state_file})...")
        while self._running:
            try:
                await self._poll_jarvis_state()
            except Exception as e:
                logger.debug(f"Error in jarvis sync loop: {e}")
            await asyncio.sleep(0.12)  # ~8 Hz polling rate

    async def _handle_connection(self, websocket):
        self.clients.add(websocket)
        logger.info(f"Drone client connected: {getattr(websocket, 'remote_address', 'unknown')}")
        try:
            async for message in websocket:
                try:
                    data = json.loads(message)
                    msg_type = data.get("type")
                    if data.get("event") == "DRONE_TAP":
                        # 1. Execute registered tap handlers
                        for handler in self._tap_handlers:
                            try:
                                res = handler()
                                if asyncio.iscoroutine(res):
                                    asyncio.create_task(res)
                            except Exception as handler_err:
                                logger.error(f"Error executing tap handler: {handler_err}")

                        # 2. Built-in link: wake / toggle JARVIS voice listening
                        if self.enable_jarvis_sync and self.jarvis_socket_path.exists():
                            logger.info("Drone tapped: sending 'listen toggle' to JARVIS")
                            asyncio.create_task(self.send_jarvis_command("listen toggle"))

                        # 3. Visual affirmative nod feedback
                        asyncio.create_task(self.broadcast_gesture("nod"))
                    elif msg_type == "VISIBILITY" and data.get("action"):
                        action = data["action"]
                        logger.info(f"Relaying VISIBILITY action '{action}' to drone clients")
                        asyncio.create_task(self.broadcast_visibility(action))
                    elif msg_type == "STATE" and data.get("state"):
                        new_state = data["state"]
                        logger.info(f"Relaying STATE '{new_state}' to drone clients")
                        self.current_drone_state = new_state
                        asyncio.create_task(self.broadcast_state(new_state))
                    elif msg_type == "GESTURE" and data.get("name"):
                        gesture = data["name"]
                        logger.info(f"Relaying GESTURE '{gesture}' to drone clients")
                        asyncio.create_task(self.broadcast_gesture(gesture))
                except Exception as e:
                    logger.error(f"Error handling message: {e}")
        finally:
            self.clients.discard(websocket)
            logger.info("Drone client disconnected")

    async def broadcast_state(self, state: str):
        if not self.clients:
            return
        payload = json.dumps({"version": "1.0", "type": "STATE", "state": state})
        await asyncio.gather(
            *[client.send(payload) for client in list(self.clients)],
            return_exceptions=True
        )

    async def broadcast_gesture(self, gesture: str):
        if not self.clients:
            return
        payload = json.dumps({"version": "1.0", "type": "GESTURE", "name": gesture})
        await asyncio.gather(
            *[client.send(payload) for client in list(self.clients)],
            return_exceptions=True
        )

    async def broadcast_visibility(self, action: str):
        if not self.clients:
            return
        payload = json.dumps({"version": "1.0", "type": "VISIBILITY", "action": action})
        await asyncio.gather(
            *[client.send(payload) for client in list(self.clients)],
            return_exceptions=True
        )

    async def start(self):
        self._running = True
        self.server = await websockets.serve(self._handle_connection, self.host, self.port)
        if self.enable_jarvis_sync:
            self.sync_task = asyncio.create_task(self._jarvis_sync_loop())
        await self.server.wait_closed()

    async def stop(self):
        self._running = False
        if self.sync_task:
            self.sync_task.cancel()
            try:
                await self.sync_task
            except asyncio.CancelledError:
                pass
            self.sync_task = None
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        for client in list(self.clients):
            await client.close()
        self.clients.clear()


async def _client_send(port: int, msg: dict):
    """Utility client to send control message to running bridge."""
    async with websockets.connect(f"ws://127.0.0.1:{port}") as ws:
        await ws.send(json.dumps(msg))
        await asyncio.sleep(0.05)


def main():
    parser = argparse.ArgumentParser(description="JARVIS Visual Drone Companion WebSocket Bridge")
    parser.add_argument("--port", type=int, default=None, help="WebSocket port (default: 8768)")
    parser.add_argument("--state", type=str, choices=["idle", "listening", "thinking", "speaking", "complete", "alert"], help="Send state to running drone")
    parser.add_argument("--gesture", type=str, choices=["nod", "gyroRoll", "recoil"], help="Send gesture to running drone")
    parser.add_argument("--tap", action="store_true", help="Simulate a drone tap event")
    parser.add_argument("--appear", "--show", dest="appear", action="store_true", help="Make drone appear / de-cloak")
    parser.add_argument("--disappear", "--hide", dest="disappear", action="store_true", help="Make drone disappear / cloak")
    parser.add_argument("--toggle-visibility", action="store_true", help="Toggle drone visibility (appear/disappear)")
    parser.add_argument("--no-sync", action="store_true", help="Disable automatic JARVIS state file polling")
    args = parser.parse_args()

    port = args.port or int(os.environ.get("JARVIS_DRONE_PORT", "8768"))

    if args.state:
        asyncio.run(_client_send(port, {"version": "1.0", "type": "STATE", "state": args.state}))
        print(f"Sent state '{args.state}' to drone on port {port}")
        return
    if args.gesture:
        asyncio.run(_client_send(port, {"version": "1.0", "type": "GESTURE", "name": args.gesture}))
        print(f"Sent gesture '{args.gesture}' to drone on port {port}")
        return
    if args.tap:
        asyncio.run(_client_send(port, {"version": "1.0", "event": "DRONE_TAP", "action": "TOGGLE_VOICE_LISTENING"}))
        print(f"Sent tap event to drone on port {port}")
        return
    if args.appear:
        asyncio.run(_client_send(port, {"version": "1.0", "type": "VISIBILITY", "action": "appear"}))
        print(f"Sent 'appear' visibility command to drone on port {port}")
        return
    if args.disappear:
        asyncio.run(_client_send(port, {"version": "1.0", "type": "VISIBILITY", "action": "disappear"}))
        print(f"Sent 'disappear' visibility command to drone on port {port}")
        return
    if args.toggle_visibility:
        asyncio.run(_client_send(port, {"version": "1.0", "type": "VISIBILITY", "action": "toggle"}))
        print(f"Sent 'toggle' visibility command to drone on port {port}")
        return

    logging.basicConfig(level=logging.INFO)
    bridge = DroneBridge(port=port, enable_jarvis_sync=not args.no_sync)
    print(f"Starting Drone WebSocket Bridge on ws://{bridge.host}:{bridge.port} (JARVIS sync={not args.no_sync})...")
    try:
        asyncio.run(bridge.start())
    except KeyboardInterrupt:
        print("Bridge stopped.")


if __name__ == "__main__":
    main()
