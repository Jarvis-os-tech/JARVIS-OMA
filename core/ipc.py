"""Mode-0600 UNIX domain socket control plane for Omarchy 4 Quickshell & jarvisctl."""
import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any, Callable, Optional

log = logging.getLogger("jarvis.ipc")


def default_socket_path() -> Path:
    runtime_dir = os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}"
    return Path(runtime_dir) / "jarvis.sock"


class JarvisIPCServer:
    """Mode-0600 UNIX domain socket control plane for Omarchy 4 Quickshell & jarvisctl."""

    def __init__(
        self,
        socket_path: Optional[Path] = None,
        status_provider: Optional[Callable[[], dict[str, Any]]] = None,
        toggle_mute_cb: Optional[Callable[[], bool]] = None,
        interrupt_cb: Optional[Callable[[], None]] = None,
        set_vision_mode_cb: Optional[Callable[[str], dict[str, Any]]] = None,
        test_voice_cb: Optional[Callable[[], dict[str, Any]]] = None,
    ):
        self.socket_path = Path(socket_path) if socket_path else default_socket_path()
        self.status_provider = status_provider or (lambda: {})
        self.toggle_mute_cb = toggle_mute_cb or (lambda: False)
        self.interrupt_cb = interrupt_cb or (lambda: None)
        self.set_vision_mode_cb = set_vision_mode_cb or (lambda mode: {"vision_mode": mode})
        self.test_voice_cb = test_voice_cb
        self._server: Optional[asyncio.AbstractServer] = None
        self._subscribers: set[asyncio.StreamWriter] = set()

    async def start(self) -> None:
        self.socket_path.parent.mkdir(parents=True, exist_ok=True)
        if self.socket_path.exists():
            try:
                self.socket_path.unlink()
            except OSError:
                pass
        self._server = await asyncio.start_unix_server(
            self._handle_client, path=str(self.socket_path)
        )
        os.chmod(self.socket_path, 0o600)
        log.info("Jarvis IPC Server listening on %s (mode 0600)", self.socket_path)

    async def _handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        is_subscriber = False
        try:
            line = await reader.readline()
            if not line:
                return
            req = json.loads(line.decode("utf-8").strip())
            cmd = req.get("command")

            if cmd == "status":
                payload = {"status": "ok", **self.status_provider()}
                writer.write((json.dumps(payload) + "\n").encode("utf-8"))
                await writer.drain()
            elif cmd == "toggle_mute":
                muted = self.toggle_mute_cb()
                writer.write((json.dumps({"status": "ok", "muted": muted}) + "\n").encode("utf-8"))
                await writer.drain()
                self.broadcast_state({"muted": muted})
            elif cmd == "test_voice":
                payload = (self.test_voice_cb() if self.test_voice_cb is not None else
                           {'status': 'unavailable', 'error': 'Voice test is unavailable'})
                writer.write((json.dumps(payload) + '\n').encode('utf-8'))
                await writer.drain()
            elif cmd == "interrupt":
                self.interrupt_cb()
                writer.write((json.dumps({"status": "ok", "interrupted": True}) + "\n").encode("utf-8"))
                await writer.drain()
            elif cmd == "set_vision_mode":
                mode = req.get("mode", "off")
                res = self.set_vision_mode_cb(mode)
                writer.write((json.dumps({"status": "ok", **res}) + "\n").encode("utf-8"))
                await writer.drain()
                self.broadcast_state({"vision_mode": res.get("vision_mode", mode)})
            elif cmd == "get_vision_mode":
                status = self.status_provider()
                writer.write((json.dumps({"status": "ok", "vision_mode": status.get("vision_mode", "off")}) + "\n").encode("utf-8"))
                await writer.drain()
            elif cmd == "subscribe":
                is_subscriber = True
                self._subscribers.add(writer)
                init_payload = {"event": "state_change", **self.status_provider()}
                writer.write((json.dumps(init_payload) + "\n").encode("utf-8"))
                await writer.drain()
                # Hold stream open until client disconnects
                while True:
                    data = await reader.read(1024)
                    if not data:
                        break
            else:
                writer.write((json.dumps({"status": "error", "error": f"Unknown command: {cmd}"}) + "\n").encode("utf-8"))
                await writer.drain()
        except Exception:
            pass
        finally:
            if is_subscriber:
                self._subscribers.discard(writer)
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

    def broadcast_state(self, state_payload: dict[str, Any]) -> None:
        msg = (json.dumps({"event": "state_change", **state_payload}) + "\n").encode("utf-8")
        stale = []
        for writer in list(self._subscribers):
            try:
                writer.write(msg)
            except Exception:
                stale.append(writer)
        for writer in stale:
            self._subscribers.discard(writer)

    async def close(self) -> None:
        for writer in list(self._subscribers):
            try:
                writer.close()
            except Exception:
                pass
        self._subscribers.clear()
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
        if self.socket_path.exists():
            try:
                self.socket_path.unlink()
            except OSError:
                pass
