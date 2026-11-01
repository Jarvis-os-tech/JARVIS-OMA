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
        wake_cb: Optional[Callable] = None,
        get_vision_mode_cb: Optional[Callable] = None,
        set_vision_mode_cb: Optional[Callable] = None,
        tools_provider: Optional[Callable] = None,
        tool_call_cb: Optional[Callable] = None,
        record_memory_cb: Optional[Callable] = None,
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
        self.wake_cb = wake_cb
        self.get_vision_mode_cb = get_vision_mode_cb
        self.set_vision_mode_cb = set_vision_mode_cb
        self.tools_provider = tools_provider
        self.tool_call_cb = tool_call_cb
        self.record_memory_cb = record_memory_cb
        self._server = None
        self._owns_socket = False
        self._legacy_symlink: Optional[Path] = None

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

        legacy_sock = Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")) / "jarvis.sock"
        if self.socket_path == SOCKET_PATH and legacy_sock != self.socket_path:
            try:
                if legacy_sock.is_symlink() or legacy_sock.exists():
                    legacy_sock.unlink()
                legacy_sock.symlink_to(self.socket_path)
                self._legacy_symlink = legacy_sock
                log.debug("Linked legacy socket %s -> %s", legacy_sock, self.socket_path)
            except Exception as err:
                log.debug("Could not create legacy jarvis.sock symlink: %s", err)

    async def close(self):
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
        if self._owns_socket:
            self.socket_path.unlink(missing_ok=True)
            self._owns_socket = False
        if getattr(self, '_legacy_symlink', None) and self._legacy_symlink.is_symlink():
            try:
                self._legacy_symlink.unlink(missing_ok=True)
            except Exception:
                pass

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

    async def _handle_json_command(self, req: dict) -> str:
        cmd = req.get('command')
        if cmd == 'tools':
            return json.dumps({'device': 'pc', 'tools': self.tools_provider() if self.tools_provider else []}) + '\n'
        if cmd == 'tool_call':
            if not self.tool_call_cb:
                return json.dumps({'error': 'Shared execution unavailable'}) + '\n'
            return json.dumps(await self.tool_call_cb(req)) + '\n'
        if cmd == 'sync_memory':
            records = req.get('records', [])
            user_text = req.get('user', '').strip()
            assistant_text = req.get('assistant', '').strip()
            device = str(req.get('device', 'mobile')).lower().strip() or 'mobile'
            if not self.record_memory_cb:
                return json.dumps({'error': 'Memory recording unavailable'}) + '\n'

            async def _save_turn(u: str, a: str) -> None:
                if not u and not a:
                    return
                try:
                    res = self.record_memory_cb(u, a, device=device)
                except TypeError:
                    res = self.record_memory_cb(u, a)
                if asyncio.iscoroutine(res):
                    await res

            if records:
                current_user = ""
                current_assistant = ""
                for r in records:
                    r_role = r.get('role', '')
                    r_content = r.get('content', '').strip()
                    if r_role == 'user':
                        if current_user or current_assistant:
                            await _save_turn(current_user, current_assistant)
                            current_user = ""
                            current_assistant = ""
                        current_user = r_content
                    elif r_role in ('assistant', 'model'):
                        current_assistant = (current_assistant + " " + r_content).strip() if current_assistant else r_content
                if current_user or current_assistant:
                    await _save_turn(current_user, current_assistant)
                log.info('Ingested %d remote memory records from %s companion', len(records), device)
                return json.dumps({'status': 'ok', 'saved': True, 'count': len(records)}) + '\n'
            elif user_text or assistant_text:
                await _save_turn(user_text, assistant_text)
                log.info('Ingested remote memory from %s companion (user=%d chars, assistant=%d chars)',
                         device, len(user_text), len(assistant_text))
                return json.dumps({'status': 'ok', 'saved': True, 'count': 1}) + '\n'
            return json.dumps({'status': 'ok', 'saved': False, 'count': 0, 'reason': 'empty_exchange'}) + '\n'
        if cmd == 'get_vision_mode':
            if self.get_vision_mode_cb:
                mode = self.get_vision_mode_cb()
                if asyncio.iscoroutine(mode):
                    mode = await mode
            else:
                mode = self.status_provider().get('vision_mode', 'off')
            return json.dumps({'status': 'ok', 'vision_mode': mode}) + '\n'
        if cmd == 'set_vision_mode':
            mode = str(req.get('mode', 'off')).strip().lower()
            res = {}
            if self.set_vision_mode_cb:
                res = self.set_vision_mode_cb(mode)
                if asyncio.iscoroutine(res):
                    res = await res
            if not isinstance(res, dict):
                res = {'vision_mode': mode}
            self.broadcast_state({'vision_mode': res.get('vision_mode', mode)})
            return json.dumps({'status': 'ok', **res}) + '\n'
        if cmd == 'status':
            return json.dumps(self.status_provider()) + '\n'
        if cmd == 'toggle_mute':
            muted = False
            if self.toggle_mute_cb:
                muted = self.toggle_mute_cb()
                if asyncio.iscoroutine(muted):
                    muted = await muted
            return json.dumps({'status': 'ok', 'muted': muted}) + '\n'
        if cmd == 'set_mute':
            requested = req.get('muted', True)
            if self.set_mute_cb:
                muted = self.set_mute_cb(requested)
                if asyncio.iscoroutine(muted):
                    muted = await muted
            else:
                muted = requested
            return json.dumps({'status': 'ok', 'muted': muted}) + '\n'
        if cmd == 'interrupt':
            if self.interrupt_cb:
                self.interrupt_cb()
            return json.dumps({'status': 'ok', 'interrupted': True}) + '\n'
        if cmd == 'standby':
            if self.standby_cb:
                res = self.standby_cb()
                if asyncio.iscoroutine(res):
                    asyncio.create_task(res)
                return json.dumps({'status': 'ok', 'standby': True}) + '\n'
            return json.dumps({'error': 'standby not available'}) + '\n'
        if cmd == 'wake':
            if self.wake_cb:
                res = self.wake_cb()
                if asyncio.iscoroutine(res):
                    asyncio.create_task(res)
                return json.dumps({'status': 'ok', 'standby': False}) + '\n'
            return json.dumps({'error': 'wake not available'}) + '\n'
        return json.dumps({'error': f'unknown json command: {cmd}'}) + '\n'

    def _dispatch(self, command: str):
        if command.startswith('{'):
            try:
                req = json.loads(command)
                return self._handle_json_command(req)
            except Exception as e:
                return json.dumps({'error': f'invalid json: {e}'}) + '\n'
        if command in ('vision status', 'vision get'):
            mode = (self.get_vision_mode_cb() if self.get_vision_mode_cb
                    else self.status_provider().get('vision_mode', 'off'))
            return f'jarvis-vision: {mode}\n'
        if command.startswith('vision '):
            _, _, mode = command.partition(' ')
            clean = mode.strip().lower()
            if self.set_vision_mode_cb:
                res = self.set_vision_mode_cb(clean)
                if asyncio.iscoroutine(res):
                    return self._control_result(lambda: res)
                return json.dumps({'status': 'ok', 'vision_mode': clean}) + '\n'
            return json.dumps({'error': 'vision control not available'}) + '\n'
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
        if command in ('wake', 'standby off', 'resume'):
            if self.wake_cb:
                res = self.wake_cb()
                if asyncio.iscoroutine(res):
                    asyncio.create_task(res)
                return json.dumps({'standby': False, 'status': 'awake'}) + '\n'
            return json.dumps({'error': 'wake not available'}) + '\n'
        if command == 'listen toggle':
            if self.wake_cb:
                self.wake_cb()
            if self.toggle_mute_cb:
                muted = self.toggle_mute_cb()
                return json.dumps({'muted': muted}) + '\n'
            return json.dumps({'error': 'toggle not available'}) + '\n'
        if command == 'listen start':
            if self.wake_cb:
                self.wake_cb()
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
            if self.wake_cb:
                self.wake_cb()
            if self.send_text_cb:
                res = self.send_text_cb(text)
                if asyncio.iscoroutine(res):
                    asyncio.create_task(res)
                return json.dumps({'status': 'sent', 'text': text}) + '\n'
            return json.dumps({'error': 'text input not available'}) + '\n'
        return json.dumps({'error': f'unknown command: {command}'}) + '\n'
