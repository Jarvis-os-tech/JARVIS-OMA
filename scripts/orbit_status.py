#!/usr/bin/env python3
"""Print one bounded JARVIS daemon status record for the Aura Orbit UI."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.ipc import default_socket_path


async def status() -> dict:
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_unix_connection(str(default_socket_path())), timeout=0.2)
        writer.write(b'{"command":"status"}\n')
        await writer.drain()
        line = await asyncio.wait_for(reader.readline(), timeout=0.2)
        writer.close()
        await writer.wait_closed()
        payload = json.loads(line.decode("utf-8"))
        if payload.get("standby"):
            payload["state"] = "standby"
        return payload
    except (OSError, asyncio.TimeoutError, ValueError, json.JSONDecodeError):
        return {"status": "offline", "state": "offline", "standby": False,
                "muted": False}


async def subscribe() -> None:
    """Stream merged status records, reconnecting when the daemon restarts."""
    marker = PROJECT_ROOT / '.orbit-demo-once'
    if marker.exists():
        marker.unlink()
        for state, label in [('idle', 'Idle'), ('connecting', 'Connecting'),
                             ('listening', 'Listening'), ('thinking', 'Thinking'),
                             ('processing', 'Processing'), ('processing', 'Searching the web'),
                             ('processing', 'Reading files'), ('processing', 'Opening an application'),
                             ('processing', 'Background processing'), ('speaking', 'Speaking'),
                             ('standby', 'Standby'), ('error', 'Error'), ('offline', 'Offline')]:
            print(json.dumps({'state': state, 'activity': label,
                              'standby': state == 'standby', 'muted': False,
                              'demo': True}), flush=True)
            await asyncio.sleep(4)
    current = {"state": "offline", "standby": False, "muted": False}
    while True:
        try:
            reader, writer = await asyncio.open_unix_connection(
                str(default_socket_path()))
            writer.write(b'{"command":"subscribe"}\n')
            await writer.drain()
            while True:
                line = await reader.readline()
                if not line:
                    raise ConnectionError("JARVIS status stream closed")
                update = json.loads(line.decode("utf-8"))
                current.update(update)
                if current.get("standby"):
                    current["state"] = "standby"
                print(json.dumps(current, separators=(",", ":")), flush=True)
        except (OSError, ValueError, json.JSONDecodeError, ConnectionError):
            current.update({"state": "offline", "standby": False, "muted": False})
            print(json.dumps(current, separators=(",", ":")), flush=True)
            await asyncio.sleep(0.5)
        finally:
            if "writer" in locals():
                writer.close()
                try:
                    await writer.wait_closed()
                except OSError:
                    pass


async def demo() -> None:
    """Cycle every visual state without connecting to the JARVIS daemon."""
    states = ('idle', 'connecting', 'listening', 'thinking', 'speaking',
              'standby', 'error', 'offline')
    while True:
        for state in states:
            print(json.dumps({
                'state': state,
                'standby': state == 'standby',
                'muted': False,
                'demo': True,
            }, separators=(',', ':')), flush=True)
            await asyncio.sleep(3)


if __name__ == "__main__":
    if "--demo" in sys.argv:
        asyncio.run(demo())
    elif "--subscribe" in sys.argv:
        asyncio.run(subscribe())
    else:
        print(json.dumps(asyncio.run(status()), separators=(",", ":")))
