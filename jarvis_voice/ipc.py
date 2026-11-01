"""Protected Unix domain socket for status queries and control commands."""
import asyncio
import json
import logging
import os
import stat
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
        standby_cb: Optional[Callable] = None,
        confirm_cb: Optional[Callable] = None,
        cancel_cb: Optional[Callable] = None,
        send_text_cb: Optional[Callable] = None,
    ):
        self.socket_path = Path(socket_path) if socket_path else SOCKET_PATH
        self.status_provider = status_provider or (lambda: {})
        self.toggle_mute_cb = toggle_mute_cb
        self.set_mute_cb = set_mute_cb
        self.interrupt_cb = interrupt_cb
        self.standby_cb = standby_cb
        self.confirm_cb = confirm_cb
        self.cancel_cb = cancel_cb
        self.send_text_cb = send_text_cb
        self._server = None
        self._owns_socket = False

    async def start(self):
        self.socket_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        parent = self.socket_path.parent.lstat()
        if not stat.S_ISDIR(parent.st_mode) or parent.st_uid != os.getuid() or parent.st_mode & 0o077:
            raise PermissionError('Voice runtime directory must be private and owned by this user')
        if self.socket_path.exists() or self.socket_path.is_symlink():
            node = self.socket_path.lstat()
            if not stat.S_ISSOCK(node.st_mode) or node.st_uid != os.getuid():
                raise PermissionError('Refusing to replace an unowned or non-socket control path')
            try:
                reader, writer = await asyncio.wait_for(asyncio.open_unix_connection(str(self.socket_path)), 1)
            except (ConnectionRefusedError, FileNotFoundError):
                self.socket_path.unlink(missing_ok=True)
            else:
                writer.close()
                await writer.wait_closed()
                raise RuntimeError('JARVIS voice is already running')
        self._server = await asyncio.start_unix_server(
            self._handle_client, path=str(self.socket_path))
        self._owns_socket = True
        self.socket_path.chmod(0o600)
        log.info('IPC listening on %s', self.socket_path)

    async def close(self):
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
        if self._owns_socket:
            self.socket_path.unlink(missing_ok=True)
            self._owns_socket = False

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
            if not line:
                return
            command = line.decode().strip()
            response = self._dispatch(command)
            if asyncio.iscoroutine(response):
                response = await response
            writer.write(response.encode() if isinstance(response, str) else response)
            await writer.drain()
        except Exception as e:
            log.warning('IPC client error: %s', e)
        finally:
            writer.close()

    async def _control_result(self, callback) -> str:
        result = callback()
        if asyncio.iscoroutine(result):
            result = await result
        return json.dumps({'result': result}) + '\n'

    def _dispatch(self, command: str):
        if command == 'status --json':
            return json.dumps(self.status_provider()) + '\n'
        if command == 'status':
            status = self.status_provider()
            state = status.get('state') or ('listening' if status.get('listening') else 'idle')
            model = status.get('model', 'unknown')
            issue = status.get('microphone', {}).get('issue')
            detail = f' — {issue}' if issue else ''
            return f'jarvis-voice: {state} (model={model}){detail}\n'
        if command in ('standby', 'standby enter', 'listen standby'):
            if self.standby_cb:
                res = self.standby_cb()
                if asyncio.iscoroutine(res):
                    asyncio.create_task(res)
                return json.dumps({'standby': True, 'status': 'standby_requested'}) + '\n'
            return json.dumps({'error': 'standby not available'}) + '\n'
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
                if self.cancel_cb:
                    return self._control_result(self.cancel_cb)
                return json.dumps({'cancelled': True}) + '\n'
            return json.dumps({'error': 'not available'}) + '\n'
        if command == 'listen confirm':
            if self.confirm_cb:
                return self._control_result(self.confirm_cb)
            return json.dumps({'error': 'confirmation not available'}) + '\n'
        if command.startswith(('send ', 'tell ', 'prompt ', 'say ')):
            _, _, text = command.partition(' ')
            text = text.strip()
            if not text:
                return json.dumps({'error': 'empty text'}) + '\n'
            if self.send_text_cb:
                res = self.send_text_cb(text)
                if asyncio.iscoroutine(res):
                    asyncio.create_task(res)
                return json.dumps({'status': 'sent', 'text': text}) + '\n'
            return json.dumps({'error': 'text input not available'}) + '\n'
        return json.dumps({'error': f'unknown command: {command}'}) + '\n'
