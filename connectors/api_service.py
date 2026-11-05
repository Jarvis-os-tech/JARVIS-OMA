"""User-local API execution service. No TCP listener or arbitrary shell API."""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import signal

LIMIT = 1024 * 1024
DEADLINES = {'health': 3, 'search': 65, 'operations': 65, 'call': 50,
             'propose': 125, 'learn': 185}


def socket_path():
    return Path(os.environ.get('XDG_RUNTIME_DIR', f'/run/user/{os.getuid()}')) / 'jarvis-api-agent/control.sock'


async def request(operation, arguments):
    """None means never submitted; any later transport error is uncertain."""
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_unix_connection(str(socket_path()), limit=LIMIT), 2)
    except (OSError, asyncio.TimeoutError):
        return None
    try:
        packet = json.dumps({'operation': operation, 'arguments': arguments}) + '\n'
        if len(packet.encode()) > LIMIT:
            return {'ok': False, 'status': 'rejected', 'error': 'API request is too large'}
        writer.write(packet.encode())
        await writer.drain()
        raw = await asyncio.wait_for(reader.readline(), DEADLINES.get(operation, 3) + 5)
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise ValueError('Invalid service response')
        return value
    except (OSError, ValueError, asyncio.TimeoutError):
        return {'ok': False, 'status': 'unknown', 'completed': False,
                'error': 'API service response was interrupted; effect is unknown. Do not replay a write.'}
    finally:
        writer.close()
        try:
            await writer.wait_closed()
        except OSError:
            pass


async def dispatch_local(operation, arguments):
    from connectors import api_anything as api
    if operation not in DEADLINES or not isinstance(arguments, dict):
        return {'ok': False, 'status': 'rejected', 'error': 'Unknown API operation or invalid arguments'}
    if operation == 'health':
        return {'ok': True, 'service': 'jarvis-api-agent', 'status': 'ready',
                'operations': list(DEADLINES), 'scope': 'transport_only'}
    text_fields = {'search': ('query',), 'operations': ('site',), 'call': ('site', 'op'),
                   'propose': ('problem',), 'learn': ()}
    if any(not isinstance(arguments.get(key), str) or not arguments[key].strip()
           or arguments[key].startswith('-') for key in text_fields[operation]):
        return {'ok': False, 'status': 'rejected', 'error': 'Missing or invalid API arguments'}
    if operation == 'call':
        args = arguments.get('args', {})
        if not isinstance(args, dict) or type(arguments.get('allow_writes', False)) is not bool:
            return {'ok': False, 'status': 'rejected', 'error': 'Invalid API call parameters'}
        key = arguments.get('request_key')
        if key is not None and (not isinstance(key, str) or not 1 <= len(key) <= 200):
            return {'ok': False, 'status': 'rejected', 'error': 'Invalid request key'}
        if arguments.get('allow_writes') and not key:
            return {'ok': False, 'status': 'needs_confirmation', 'completed': False,
                    'error': 'Writes require an explicit allow_writes flag and a stable request_key.'}
        command = [str(api.CLI_SCRIPT), 'call', arguments['site'], arguments['op'],
                   '--json', json.dumps(args)]
        if arguments.get('allow_writes'):
            command.extend(['--allow-writes', '--idempotency-key', key])
        return await api._exec_bun_cmd(*command, timeout=45)
    if operation == 'learn':
        blueprint = arguments.get('blueprint')
        if not isinstance(blueprint, dict) or not blueprint:
            return {'ok': False, 'status': 'rejected', 'error': 'Blueprint must be a nonempty object'}
        return await api._exec_bun_cmd(str(api.DAEMON_SCRIPT), '--learn', json.dumps(blueprint),
                                       timeout=180, cwd=api.DAEMON_DIR)
    if operation == 'propose':
        return await api._exec_bun_cmd(str(api.DAEMON_SCRIPT), '--propose', arguments['problem'],
                                       timeout=120, cwd=api.DAEMON_DIR)
    command = ['search', arguments['query']] if operation == 'search' else ['ops', arguments['site']]
    return await api._exec_bun_cmd(str(api.CLI_SCRIPT), *command)


class ApiService:
    """Reject saturation rather than quietly queueing work past its deadline."""
    def __init__(self):
        self.active = 0

    async def handle(self, reader, writer):
        admitted = False
        try:
            raw = await asyncio.wait_for(reader.readline(), 3)
            data = json.loads(raw)
            if not isinstance(data, dict):
                raise ValueError('Expected object')
            operation, arguments = data.get('operation'), data.get('arguments', {})
            if not isinstance(operation, str) or operation not in DEADLINES:
                raise ValueError('Unknown operation')
            if self.active >= 2 and operation != 'health':
                result = {'ok': False, 'status': 'unavailable', 'error': 'API service is busy; request was not started'}
            else:
                admitted = True
                self.active += 1
                try:
                    result = await asyncio.wait_for(dispatch_local(operation, arguments), DEADLINES[operation])
                except asyncio.TimeoutError:
                    result = {'ok': False, 'status': 'unknown', 'completed': False,
                              'error': 'API deadline exceeded; final effect is unknown'}
        except (ValueError, TypeError, asyncio.TimeoutError):
            result = {'ok': False, 'status': 'rejected', 'error': 'Invalid API service request'}
        except Exception:
            result = {'ok': False, 'status': 'unknown', 'completed': False, 'error': 'API execution failed; inspect service status'}
        finally:
            if admitted:
                self.active -= 1
        try:
            encoded = json.dumps(result).encode() + b'\n'
            if len(encoded) > LIMIT:
                encoded = b'{"ok":false,"status":"unknown","completed":false,"error":"API response exceeds limit; do not replay writes"}\n'
            writer.write(encoded)
            await writer.drain()
        except (OSError, ValueError):
            pass
        finally:
            writer.close()


async def serve():
    path = socket_path()
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.parent.chmod(0o700)
    if path.exists():
        # Refuse a second listener. Only unlink a stale socket, never a file.
        if not path.is_socket():
            raise RuntimeError('API socket path is occupied by a non-socket')
        if await request('health', {}) is not None:
            raise RuntimeError('API service already has a listener')
        path.unlink()
    server = await asyncio.start_unix_server(ApiService().handle, str(path), limit=LIMIT)
    path.chmod(0o600)
    stop = asyncio.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        asyncio.get_running_loop().add_signal_handler(sig, stop.set)
    try:
        async with server:
            await stop.wait()
    finally:
        path.unlink(missing_ok=True)


if __name__ == '__main__':
    asyncio.run(serve())
