"""Mode-0600 UNIX domain socket control plane for Omarchy 4 Quickshell & jarvisctl."""
import asyncio
import json
import logging
import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional

log = logging.getLogger("jarvis.ipc")

_SUBSCRIBER_QUEUE_SIZE = 32
_SUBSCRIBER_DRAIN_TIMEOUT = 1.0
_MAX_SUBSCRIBERS = 64
_MAX_EVENT_BYTES = 64 * 1024


@dataclass(eq=False)
class _Subscriber:
    writer: asyncio.StreamWriter
    queue: asyncio.Queue[bytes]
    sender_task: Optional[asyncio.Task] = None


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
        subscriber_queue_size: int = _SUBSCRIBER_QUEUE_SIZE,
        subscriber_drain_timeout: float = _SUBSCRIBER_DRAIN_TIMEOUT,
        max_subscribers: int = _MAX_SUBSCRIBERS,
        max_event_bytes: int = _MAX_EVENT_BYTES,
    ):
        if type(subscriber_queue_size) is not int or subscriber_queue_size < 1:
            raise ValueError("subscriber_queue_size must be a positive integer")
        if (isinstance(subscriber_drain_timeout, bool)
                or not isinstance(subscriber_drain_timeout, (int, float))
                or not math.isfinite(subscriber_drain_timeout)
                or subscriber_drain_timeout <= 0):
            raise ValueError("subscriber_drain_timeout must be a finite positive number")
        if type(max_subscribers) is not int or max_subscribers < 1:
            raise ValueError("max_subscribers must be a positive integer")
        if type(max_event_bytes) is not int or max_event_bytes < 1:
            raise ValueError("max_event_bytes must be a positive integer")
        self.socket_path = Path(socket_path) if socket_path else default_socket_path()
        self.status_provider = status_provider or (lambda: {})
        self.toggle_mute_cb = toggle_mute_cb or (lambda: False)
        self.set_mute_cb = set_mute_cb
        self.interrupt_cb = interrupt_cb or (lambda: None)
        self.set_vision_mode_cb = set_vision_mode_cb or (lambda mode: {"vision_mode": mode})
        self.test_voice_cb = test_voice_cb
        self.subscriber_queue_size = subscriber_queue_size
        self.subscriber_drain_timeout = float(subscriber_drain_timeout)
        self.max_subscribers = max_subscribers
        self.max_event_bytes = max_event_bytes
        self._server: Optional[asyncio.AbstractServer] = None
        self._subscribers: dict[asyncio.StreamWriter, _Subscriber] = {}
        self._sender_tasks: set[asyncio.Task] = set()
        self._clients: set[asyncio.StreamWriter] = set()
        self._closing = False

    async def start(self) -> None:
        self._closing = False
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
        self._clients.add(writer)
        is_subscriber = False
        try:
            if self._closing:
                return
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
                desired = req.get("muted")
                if type(desired) is not bool:
                    writer.write((json.dumps({
                        "status": "error",
                        "error": "set_mute requires a boolean muted value",
                    }) + "\n").encode("utf-8"))
                    await writer.drain()
                    return

                if self.set_mute_cb is not None:
                    muted = self.set_mute_cb(desired)
                else:
                    current = self.status_provider().get("muted")
                    if type(current) is not bool:
                        writer.write((json.dumps({
                            "status": "error",
                            "error": "Mute state unavailable",
                        }) + "\n").encode("utf-8"))
                        await writer.drain()
                        return
                    muted = current if current == desired else self.toggle_mute_cb()

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
                if len(self._sender_tasks) >= self.max_subscribers:
                    writer.write((json.dumps({
                        "status": "error", "error": "Subscriber limit reached",
                    }) + "\n").encode("utf-8"))
                    await writer.drain()
                    return
                is_subscriber = True
                subscriber = _Subscriber(
                    writer=writer,
                    queue=asyncio.Queue(maxsize=self.subscriber_queue_size),
                )
                self._subscribers[writer] = subscriber
                subscriber.sender_task = asyncio.create_task(
                    self._send_subscriber_events(subscriber),
                    name="jarvis-ipc-subscriber-sender",
                )
                self._sender_tasks.add(subscriber.sender_task)
                subscriber.sender_task.add_done_callback(self._sender_tasks.discard)
                init_payload = {"event": "state_change", **self.status_provider()}
                self._enqueue(subscriber, init_payload)
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
                subscriber = self._subscribers.get(writer)
                if subscriber is not None:
                    await self._close_subscriber(subscriber)
            else:
                await self._close_writer(writer)
            self._clients.discard(writer)

    def _enqueue(self, subscriber: _Subscriber, payload: dict[str, Any]) -> bool:
        try:
            message = (json.dumps(payload) + "\n").encode("utf-8")
            if len(message) > self.max_event_bytes:
                raise ValueError("outgoing event exceeds max_event_bytes")
            subscriber.queue.put_nowait(message)
            return True
        except (asyncio.QueueFull, TypeError, ValueError):
            self._drop_subscriber(subscriber, "outgoing queue full or invalid event")
            return False

    async def _send_subscriber_events(self, subscriber: _Subscriber) -> None:
        try:
            while self._subscribers.get(subscriber.writer) is subscriber:
                message = await subscriber.queue.get()
                subscriber.writer.write(message)
                await asyncio.wait_for(
                    subscriber.writer.drain(), timeout=self.subscriber_drain_timeout
                )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self._drop_subscriber(subscriber, f"sender failed: {exc}")
        finally:
            # A dropped handler may already be waiting on reader.read(); keep
            # the bounded sender task responsible for completing socket close.
            await self._close_writer(subscriber.writer)

    def _drop_subscriber(self, subscriber: _Subscriber, reason: str) -> None:
        if self._subscribers.get(subscriber.writer) is not subscriber:
            return
        self._subscribers.pop(subscriber.writer, None)
        log.debug("Dropping slow or failed IPC subscriber: %s", reason)
        try:
            subscriber.writer.close()
        except Exception:
            pass
        task = subscriber.sender_task
        if task is not None and task is not asyncio.current_task() and not task.done():
            task.cancel()

    async def _close_writer(self, writer: asyncio.StreamWriter) -> None:
        try:
            writer.close()
            await asyncio.wait_for(writer.wait_closed(), timeout=self.subscriber_drain_timeout)
        except Exception:
            pass

    async def _close_subscriber(self, subscriber: _Subscriber) -> None:
        self._drop_subscriber(subscriber, "subscriber disconnected or server closing")
        task = subscriber.sender_task
        if task is not None and task is not asyncio.current_task():
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        await self._close_writer(subscriber.writer)

    def broadcast_state(self, state_payload: dict[str, Any]) -> None:
        try:
            msg = (json.dumps({"event": "state_change", **state_payload}) + "\n").encode("utf-8")
        except (TypeError, ValueError) as exc:
            log.warning("Skipping non-serializable IPC state event: %s", exc)
            return
        if len(msg) > self.max_event_bytes:
            log.warning("Skipping oversized IPC state event (%d bytes)", len(msg))
            return
        for subscriber in list(self._subscribers.values()):
            try:
                subscriber.queue.put_nowait(msg)
            except asyncio.QueueFull:
                self._drop_subscriber(subscriber, "outgoing queue full")
            except Exception as exc:
                self._drop_subscriber(subscriber, f"enqueue failed: {exc}")

    async def close(self) -> None:
        self._closing = True
        server = self._server
        self._server = None
        if server:
            server.close()
        subscribers = list(self._subscribers.values())
        if subscribers:
            await asyncio.gather(
                *(self._close_subscriber(subscriber) for subscriber in subscribers),
                return_exceptions=True,
            )
        sender_tasks = list(self._sender_tasks)
        for task in sender_tasks:
            if not task.done():
                task.cancel()
        if sender_tasks:
            await asyncio.gather(*sender_tasks, return_exceptions=True)
        # An accepted client can be waiting to send its first command, too.
        # Closing only subscribers leaves wait_closed waiting on that client.
        clients = list(self._clients)
        if clients:
            await asyncio.gather(*(self._close_writer(writer) for writer in clients),
                                 return_exceptions=True)
        # Python 3.13 waits for accepted connections here, so subscribers must
        # be closed before awaiting server shutdown.
        if server:
            await server.wait_closed()
        if self.socket_path.exists():
            try:
                self.socket_path.unlink()
            except OSError:
                pass
