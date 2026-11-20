"""
End-to-end integration tests for JARVIS Visual Drone Companion.

Verifies:
1. Complete agent state broadcast cycle:
   ('idle', 'listening', 'thinking', 'speaking', 'complete', 'alert').
2. One-shot gesture broadcast cycle:
   ('nod', 'gyroRoll', 'recoil').
3. Drone client tap event delivery:
   ('DRONE_TAP' -> synchronous & asynchronous callback execution).
4. Multi-client broadcast resilience & dynamic disconnection handling.
5. Clean shutdown with zero dangling tasks and immediate socket release.
"""

import asyncio
import json
import socket
from typing import List
import pytest
import websockets
from ui.jarvis_drone.bridge import DroneBridge


def get_free_port() -> int:
    """Dynamically allocate an ephemeral port to prevent address collision."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.mark.asyncio
async def test_full_agent_state_cycle():
    """Verify complete agent state broadcast cycle across WebSocket."""
    port = get_free_port()
    bridge = DroneBridge(host="127.0.0.1", port=port)
    server_task = asyncio.create_task(bridge.start())
    await asyncio.sleep(0.05)

    received_states: List[str] = []
    target_states = ["idle", "listening", "thinking", "speaking", "complete", "alert"]

    async def fake_drone_client():
        async with websockets.connect(f"ws://127.0.0.1:{port}") as ws:
            while len(received_states) < len(target_states):
                data = json.loads(await ws.recv())
                if data.get("type") == "STATE":
                    received_states.append(data.get("state"))

    client_task = asyncio.create_task(fake_drone_client())
    await asyncio.sleep(0.05)

    try:
        for state in target_states:
            await bridge.broadcast_state(state)
            await asyncio.sleep(0.02)

        await asyncio.wait_for(client_task, timeout=3.0)
        assert received_states == target_states
    finally:
        if not client_task.done():
            client_task.cancel()
            try:
                await client_task
            except asyncio.CancelledError:
                pass
        await bridge.stop()
        server_task.cancel()
        try:
            await server_task
        except asyncio.CancelledError:
            pass


@pytest.mark.asyncio
async def test_one_shot_gesture_broadcast_cycle():
    """Verify one-shot gesture broadcast cycle (nod, gyroRoll, recoil)."""
    port = get_free_port()
    bridge = DroneBridge(host="127.0.0.1", port=port)
    server_task = asyncio.create_task(bridge.start())
    await asyncio.sleep(0.05)

    received_gestures: List[str] = []
    target_gestures = ["nod", "gyroRoll", "recoil"]

    async def fake_drone_client():
        async with websockets.connect(f"ws://127.0.0.1:{port}") as ws:
            while len(received_gestures) < len(target_gestures):
                data = json.loads(await ws.recv())
                if data.get("type") == "GESTURE":
                    received_gestures.append(data.get("name"))

    client_task = asyncio.create_task(fake_drone_client())
    await asyncio.sleep(0.05)

    try:
        for gesture in target_gestures:
            await bridge.broadcast_gesture(gesture)
            await asyncio.sleep(0.02)

        await asyncio.wait_for(client_task, timeout=3.0)
        assert received_gestures == target_gestures
    finally:
        if not client_task.done():
            client_task.cancel()
            try:
                await client_task
            except asyncio.CancelledError:
                pass
        await bridge.stop()
        server_task.cancel()
        try:
            await server_task
        except asyncio.CancelledError:
            pass


@pytest.mark.asyncio
async def test_drone_tap_event_delivery():
    """Verify drone client tap event delivery triggers synchronous and asynchronous callbacks."""
    port = get_free_port()
    bridge = DroneBridge(host="127.0.0.1", port=port)
    server_task = asyncio.create_task(bridge.start())
    await asyncio.sleep(0.05)

    sync_tap_count = 0
    async_tap_events: List[str] = []

    def sync_handler():
        nonlocal sync_tap_count
        sync_tap_count += 1

    async def async_handler():
        await asyncio.sleep(0.01)
        async_tap_events.append("tap_acknowledged")

    bridge.register_tap_handler(sync_handler)
    bridge.register_tap_handler(async_handler)

    try:
        async with websockets.connect(f"ws://127.0.0.1:{port}") as ws:
            # Send standard tap event with action payload
            await ws.send(json.dumps({"event": "DRONE_TAP", "action": "TOGGLE_VOICE_LISTENING"}))
            await asyncio.sleep(0.05)

            # Send secondary tap event
            await ws.send(json.dumps({"event": "DRONE_TAP"}))
            await asyncio.sleep(0.05)

        assert sync_tap_count == 2
        assert len(async_tap_events) == 2
        assert async_tap_events == ["tap_acknowledged", "tap_acknowledged"]
    finally:
        await bridge.stop()
        server_task.cancel()
        try:
            await server_task
        except asyncio.CancelledError:
            pass


@pytest.mark.asyncio
async def test_multi_client_broadcast_resilience():
    """Verify simultaneous multi-client broadcast and graceful handling when a client leaves."""
    port = get_free_port()
    bridge = DroneBridge(host="127.0.0.1", port=port)
    server_task = asyncio.create_task(bridge.start())
    await asyncio.sleep(0.05)

    try:
        async with websockets.connect(f"ws://127.0.0.1:{port}") as ws1:
            async with websockets.connect(f"ws://127.0.0.1:{port}") as ws2:
                assert len(bridge.clients) == 2

                await bridge.broadcast_state("listening")
                msg1 = json.loads(await ws1.recv())
                msg2 = json.loads(await ws2.recv())
                assert msg1 == {"version": "1.0", "type": "STATE", "state": "listening"}
                assert msg2 == {"version": "1.0", "type": "STATE", "state": "listening"}

            # ws2 disconnected, wait brief moment for bridge cleanup
            await asyncio.sleep(0.05)
            assert len(bridge.clients) == 1

            # Broadcast after ws2 disconnect should reach ws1 without raising exceptions
            await bridge.broadcast_state("thinking")
            msg1_after = json.loads(await ws1.recv())
            assert msg1_after == {"version": "1.0", "type": "STATE", "state": "thinking"}
    finally:
        await bridge.stop()
        server_task.cancel()
        try:
            await server_task
        except asyncio.CancelledError:
            pass


@pytest.mark.asyncio
async def test_clean_shutdown_and_resource_cleanup():
    """Verify clean shutdown releases server socket and leaves zero dangling tasks."""
    port = get_free_port()
    bridge = DroneBridge(host="127.0.0.1", port=port)
    server_task = asyncio.create_task(bridge.start())
    await asyncio.sleep(0.05)

    ws = None
    try:
        ws = await websockets.connect(f"ws://127.0.0.1:{port}")
        await bridge.broadcast_state("idle")
        msg = json.loads(await ws.recv())
        assert msg.get("state") == "idle"

        # Teardown bridge
        await bridge.stop()
        await server_task

        # Client socket should be closed by bridge
        try:
            await asyncio.wait_for(ws.wait_closed(), timeout=1.0)
        except Exception:
            pass

        # Check connection closed state across websocket library versions
        is_closed = ws.closed if hasattr(ws, "closed") else getattr(ws.state, "name", "") == "CLOSED"
        assert is_closed

        # Verify clients set is drained
        assert len(bridge.clients) == 0

        # Verify zero dangling tasks
        await asyncio.sleep(0.05)
        current_task = asyncio.current_task()
        pending = [t for t in asyncio.all_tasks() if t is not current_task and not t.done()]
        assert len(pending) == 0

        # Verify socket is immediately re-bindable on the same port
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as check_sock:
            check_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            check_sock.bind(("127.0.0.1", port))
            check_sock.listen(1)
    finally:
        if ws:
            try:
                await ws.close()
            except Exception:
                pass
        await bridge.stop()
        if not server_task.done():
            server_task.cancel()
            try:
                await server_task
            except asyncio.CancelledError:
                pass
