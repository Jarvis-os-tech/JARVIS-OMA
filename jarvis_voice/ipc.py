"""Protected Unix domain socket for status queries and control commands."""
import asyncio
import json
import logging
from pathlib import Path
from typing import Callable, Optional

from .config import RUNTIME_DIR, SOCKET_PATH

log = logging.getLogger('jarvis.ipc')


class ControlServer:
    def __init__(
        self,
        socket_path: Optional[Path] = None,
        status_provider: Optional[Callable] = None,
        toggle_mute_cb: Optional[Callable] = None,
        set_mute_cb: Optional[Callable] = None,
        interrupt_cb: Optional[Callable] = None,
    ):
        self.socket_path = Path(socket_path) if socket_path else SOCKET_PATH
        self.status_provider = status_provider or (lambda: {})
        self.toggle_mute_cb = toggle_mute_cb
        self.set_mute_cb = set_mute_cb
        self.interrupt_cb = interrupt_cb
        self._server = None

    async def start(self):
        self.socket_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.socket_path.unlink(missing_ok=True)
        self._server = await asyncio.start_unix_server(
            self._handle_client, path=str(self.socket_path))
        self.socket_path.chmod(0o600)
        log.info('IPC listening on %s', self.socket_path)

    async def close(self):
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
        self.socket_path.unlink(missing_ok=True)

    def broadcast_state(self, status: dict):
        """Write atomic state file for external readers."""
        from .config import STATE_FILE
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        temp = STATE_FILE.with_suffix('.tmp')
        temp.write_text(json.dumps(status))
        temp.chmod(0o600)
        temp.replace(STATE_FILE)

    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        try:
            line = await asyncio.wait_for(reader.readline(), 5)
            command = line.decode().strip()
            response = self._dispatch(command)
            writer.write(response.encode() if isinstance(response, str) else response)
            await writer.drain()
        except Exception as e:
            log.warning('IPC client error: %s', e)
        finally:
            writer.close()

    def _dispatch(self, command: str) -> str:
        if command == 'status --json':
            return json.dumps(self.status_provider()) + '\n'
        if command == 'status':
            status = self.status_provider()
            state = 'listening' if status.get('listening') else 'idle'
            model = status.get('model', 'unknown')
            return f'jarvis-voice: {state} (model={model})\n'
        if command == 'listen toggle':
            if self.toggle_mute_cb:
                muted = self.toggle_mute_cb()
                return json.dumps({'muted': muted}) + '\n'
            return json.dumps({'error': 'toggle not available'}) + '\n'
        if command == 'listen start':
            if self.set_mute_cb:
                self.set_mute_cb(False)
                return json.dumps({'muted': False}) + '\n'
            return json.dumps({'error': 'not available'}) + '\n'
        if command == 'listen stop':
            if self.set_mute_cb:
                self.set_mute_cb(True)
                return json.dumps({'muted': True}) + '\n'
            return json.dumps({'error': 'not available'}) + '\n'
        if command == 'listen cancel':
            if self.interrupt_cb:
                self.interrupt_cb()
                return json.dumps({'cancelled': True}) + '\n'
            return json.dumps({'error': 'not available'}) + '\n'
        return json.dumps({'error': f'unknown command: {command}'}) + '\n'
