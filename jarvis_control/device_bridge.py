"""Authenticated transport to the existing voice daemon; no executor lives here."""
import argparse
import asyncio
import collections
import json
import secrets
import ssl
import time
import os
import re
from pathlib import Path

from jarvis_voice.config import SOCKET_PATH


class DeviceBridge:
    def __init__(self, token, socket_path=SOCKET_PATH, release_root=None):
        if not isinstance(token, str) or len(token) < 32:
            raise ValueError('A desktop pairing token is required')
        self.token = token
        self.socket_path = socket_path
        self.requests = collections.deque()
        self.release_root = Path(release_root) if release_root else Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local/share')) / 'jarvis' / 'mobile-updates'

    def release(self):
        metadata = json.loads((self.release_root / 'current.json').read_text())
        name = metadata.get('file', '')
        if not re.fullmatch(r'jarvis-[0-9]+-[a-f0-9]{12}\.apk', name):
            raise ValueError('Invalid published APK')
        apk = self.release_root / name
        if metadata.get('package') != 'com.jarvis.os' or apk.is_symlink() or not apk.is_file() or apk.stat().st_size != metadata.get('size'):
            raise ValueError('Invalid published release')
        return metadata, apk

    async def serve_apk(self, writer, metadata, apk):
        writer.write(f"HTTP/1.1 200 OK\r\nContent-Type: application/vnd.android.package-archive\r\nContent-Length: {metadata['size']}\r\nCache-Control: no-store\r\nConnection: close\r\n\r\n".encode())
        with apk.open('rb') as stream:
            while chunk := stream.read(65536):
                writer.write(chunk)
                await writer.drain()
        writer.close()
        await writer.wait_closed()

    async def forward(self, payload):
        reader, writer = await asyncio.open_unix_connection(str(self.socket_path), limit=2**20)
        try:
            writer.write(json.dumps(payload).encode() + b'\n')
            await writer.drain()
            result = await asyncio.wait_for(reader.readline(), 180)
            return json.loads(result)
        finally:
            writer.close()
            await writer.wait_closed()

    async def handle(self, reader, writer):
        status, result = 400, {'error': 'Invalid request'}
        try:
            header = await asyncio.wait_for(reader.readuntil(b'\r\n\r\n'), 5)
            if len(header) > 16384:
                raise ValueError('Header too large')
            lines = header.decode('ascii').split('\r\n')
            method, path, version = lines[0].split(' ')
            headers = {}
            for line in lines[1:]:
                if not line:
                    continue
                name, value = line.split(':', 1)
                name = name.lower().strip()
                if name in headers:
                    raise ValueError('Duplicate header')
                headers[name] = value.strip()
            if not secrets.compare_digest(headers.get('authorization', ''), 'Bearer ' + self.token):
                status, result = 401, {'error': 'Pair this device before executing tools'}
            elif 'origin' in headers or 'transfer-encoding' in headers:
                status, result = 403, {'error': 'Unsupported request source or encoding'}
            else:
                now = time.monotonic()
                while self.requests and self.requests[0] < now - 60:
                    self.requests.popleft()
                if len(self.requests) >= 120:
                    status, result = 429, {'error': 'Too many device requests'}
                elif method == 'GET' and path in {'/v1/mobile-release', '/v1/mobile-release/apk'}:
                    self.requests.append(now)
                    try:
                        release, apk = self.release()
                    except (OSError, ValueError):
                        status, result = 404, {'error': 'No mobile update has been published yet'}
                    else:
                        if path.endswith('/apk'):
                            await self.serve_apk(writer, release, apk)
                            return
                        status, result = 200, {key: value for key, value in release.items() if key != 'file'}
                elif method == 'GET' and path == '/v1/tools':
                    self.requests.append(now)
                    status, result = 200, await self.forward({'command': 'tools'})
                elif method == 'POST' and path == '/v1/pairing/confirm':
                    length = int(headers.get('content-length', '0'))
                    if not 0 < length <= 2048 or headers.get('content-type', '').split(';')[0] != 'application/json':
                        raise ValueError('Invalid pairing acknowledgement')
                    payload = json.loads(await asyncio.wait_for(reader.readexactly(length), 5))
                    if not isinstance(payload, dict) or set(payload) != {'session'}:
                        raise ValueError('Invalid pairing acknowledgement')
                    from scripts.pairing_window_state import confirm
                    self.requests.append(now)
                    accepted = confirm(payload['session'])
                    status, result = (200, {'paired': True}) if accepted else (410, {'error': 'Pairing window expired'})
                elif method == 'POST' and path == '/v1/call':
                    length = int(headers.get('content-length', '0'))
                    if not 0 < length <= 48000:
                        raise ValueError('Invalid body size')
                    if headers.get('content-type', '').split(';')[0] != 'application/json':
                        raise ValueError('JSON required')
                    payload = json.loads(await asyncio.wait_for(reader.readexactly(length), 5))
                    if not isinstance(payload, dict) or set(payload) != {'name', 'args', 'request_id'}:
                        raise ValueError('Invalid tool request')
                    self.requests.append(now)
                    status, result = 200, await self.forward({**payload, 'command': 'tool_call'})
                elif method == 'POST' and path in ('/v1/sync', '/v1/memory'):
                    length = int(headers.get('content-length', '0'))
                    if not 0 < length <= 131072:
                        raise ValueError('Invalid body size')
                    if headers.get('content-type', '').split(';')[0] != 'application/json':
                        raise ValueError('JSON required')
                    payload = json.loads(await asyncio.wait_for(reader.readexactly(length), 5))
                    self.requests.append(now)
                    status, result = 200, await self.forward({**payload, 'command': 'sync_memory'})
                else:
                    status, result = 404, {'error': 'Unknown device endpoint'}
        except (ConnectionError, FileNotFoundError, asyncio.TimeoutError) as e:
            print(f"DeviceBridge connection error: {type(e).__name__}: {e}", flush=True)
            status, result = 503, {'error': 'PC executor unavailable or execution result unknown. Do not replay with a new request ID.'}
        except (ValueError, UnicodeError, asyncio.IncompleteReadError, asyncio.LimitOverrunError) as e:
            print(f"DeviceBridge handle error: {type(e).__name__}: {e}", flush=True)
            status, result = 400, {'error': f'Invalid request: {e}'}
        except Exception as e:
            print(f"DeviceBridge unexpected error: {type(e).__name__}: {e}", flush=True)
            status, result = 500, {'error': 'Device bridge could not return a result'}
        try:
            body = json.dumps(result).encode()
            writer.write(f'HTTP/1.1 {status} Result\r\nContent-Type: application/json\r\nContent-Length: {len(body)}\r\nConnection: close\r\nCache-Control: no-store\r\n\r\n'.encode() + body)
            await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()


async def run(args):
    credentials = json.loads(args.pairing.read_text())
    bridge = DeviceBridge(credentials['auth_token'], args.socket)
    tls = None
    if args.cert and args.key:
        tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        tls.minimum_version = ssl.TLSVersion.TLSv1_2
        tls.load_cert_chain(args.cert, args.key)
    if args.host not in {'127.0.0.1', '::1', 'localhost'} and tls is None and not getattr(args, 'allow_lan', False):
        raise ValueError('Non-loopback device access requires HTTPS certificate and key or --allow-lan')
    server = await asyncio.start_server(bridge.handle, args.host, args.port, ssl=tls, limit=16384)
    async with server:
        await server.serve_forever()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='0.0.0.0')
    parser.add_argument('--port', type=int, default=8766)
    parser.add_argument('--pairing', type=Path, default=Path.home() / '.config/jarvis/pairing_credentials.json')
    parser.add_argument('--socket', type=Path, default=SOCKET_PATH)
    parser.add_argument('--allow-lan', action='store_true', default=True, help='Allow authenticated access across trusted local network without TLS')
    parser.add_argument('--cert')
    parser.add_argument('--key')
    asyncio.run(run(parser.parse_args()))


if __name__ == '__main__':
    main()
