"""Mode-0600 UNIX domain socket control plane for Omarchy 4 Quickshell & jarvisctl."""
import asyncio
import json
import logging
import os
import socket
import stat
from pathlib import Path
from typing import Any, Callable, Optional

log = logging.getLogger("jarvis.ipc")


def unlink_owned_socket(path: Path, identity) -> None:
    try:
        node = path.lstat()
        if identity == (node.st_dev, node.st_ino):
            path.unlink()
    except FileNotFoundError:
        pass


async def start_control_server(callback, path: Path, **kwargs):
    """Bind without asyncio's implicit unlink of an existing live socket."""
    if path.exists() or path.is_symlink():
        node = path.lstat()
        if not stat.S_ISSOCK(node.st_mode) or node.st_uid != os.getuid():
            raise PermissionError('Refusing to replace an unowned or non-socket control path')
        try:
            _, writer = await asyncio.wait_for(asyncio.open_unix_connection(str(path)), 1)
        except (ConnectionRefusedError, FileNotFoundError):
            try:
                current = path.lstat()
            except FileNotFoundError:
                pass
            else:
                if (current.st_dev, current.st_ino) != (node.st_dev, node.st_ino):
                    raise RuntimeError('Control socket changed during startup')
                path.unlink()
        else:
            writer.close()
            await writer.wait_closed()
            raise RuntimeError('JARVIS control server is already running')
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        sock.bind(str(path))
        path.chmod(0o600)
        sock.listen(socket.SOMAXCONN)
        sock.setblocking(False)
        return await asyncio.start_unix_server(callback, sock=sock, **kwargs)
    except BaseException:
        sock.close()
        raise


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
        set_mute_cb: Optional[Callable[[bool], bool]] = None,
    ):
        self.socket_path = Path(socket_path) if socket_path else default_socket_path()
        self.status_provider = status_provider or (lambda: {})
        self.toggle_mute_cb = toggle_mute_cb or (lambda: False)
        self.interrupt_cb = interrupt_cb or (lambda: None)
        self.set_vision_mode_cb = set_vision_mode_cb or (lambda mode: {"vision_mode": mode})
        self.test_voice_cb = test_voice_cb
        self.set_mute_cb = set_mute_cb
        self._server: Optional[asyncio.AbstractServer] = None
        self._owns_socket = False
        self._subscribers: set[asyncio.StreamWriter] = set()

    async def start(self) -> None:
        self.socket_path.parent.mkdir(parents=True, exist_ok=True)
        self._server = await start_control_server(
            self._handle_client, self.socket_path
        )
        node = self.socket_path.lstat()
        self._owns_socket = (node.st_dev, node.st_ino)
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
            elif cmd == "set_mute":
                requested = req.get("muted")
                if type(requested) is not bool:
                    payload = {"status": "error", "error": "muted must be a boolean"}
                elif self.set_mute_cb is None:
                    payload = {"status": "unavailable", "error": "Explicit mute control is unavailable"}
                else:
                    muted = self.set_mute_cb(requested)
                    payload = {"status": "ok", "muted": muted}
                    self.broadcast_state({"muted": muted})
                writer.write((json.dumps(payload) + "\n").encode("utf-8"))
                await writer.drain()
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
        if self._owns_socket:
            try:
                unlink_owned_socket(self.socket_path, self._owns_socket)
            except OSError:
                pass
            self._owns_socket = False
