import asyncio
import hashlib
import json

import pytest

from jarvis_control.device_bridge import DeviceBridge
from scripts.publish_mobile_update import publish


def build(tmp_path, version=2, contents=b'test-apk'):
    directory = tmp_path / 'build';directory.mkdir(exist_ok=True)
    (directory / 'app-debug.apk').write_bytes(contents)
    (directory / 'output-metadata.json').write_text(json.dumps({'applicationId': 'com.jarvis.os', 'elements': [
        {'versionCode': version, 'versionName': '1.1.0', 'outputFile': 'app-debug.apk'}]}))
    return directory


def test_published_updates_are_versioned_and_cannot_replace_same_version(tmp_path):
    directory = build(tmp_path)
    release = publish(directory, tmp_path / 'release')
    assert release['sha256'] == hashlib.sha256(b'test-apk').hexdigest()
    assert release['package'] == 'com.jarvis.os'
    (directory / 'app-debug.apk').write_bytes(b'changed-build')
    with pytest.raises(ValueError, match='Increment Android versionCode'):
        publish(directory, tmp_path / 'release')


@pytest.mark.asyncio
async def test_mobile_release_download_requires_pairing_and_serves_exact_file(tmp_path):
    release_root = tmp_path / 'releases'
    published = publish(build(tmp_path), release_root)
    bridge = DeviceBridge('x' * 64, tmp_path / 'unused.sock', release_root)
    server = await asyncio.start_server(bridge.handle, '127.0.0.1', 0)
    port = server.sockets[0].getsockname()[1]
    async def request(path, token):
        reader, writer = await asyncio.open_connection('127.0.0.1', port)
        writer.write(f'GET {path} HTTP/1.1\r\nHost: localhost\r\nAuthorization: Bearer {token}\r\n\r\n'.encode())
        await writer.drain();data = await reader.read();writer.close();await writer.wait_closed()
        head, body = data.split(b'\r\n\r\n', 1)
        return int(head.split(b' ')[1]), body
    try:
        assert (await request('/v1/mobile-release/apk', 'wrong'))[0] == 401
        status, body = await request('/v1/mobile-release', 'x' * 64)
        info = json.loads(body)
        assert status == 200 and info['sha256'] == published['sha256'] and 'file' not in info
        status, body = await request('/v1/mobile-release/apk', 'x' * 64)
        assert status == 200 and body == b'test-apk'
        metadata = json.loads((release_root / 'current.json').read_text());metadata['file'] = '../../private.apk'
        (release_root / 'current.json').write_text(json.dumps(metadata))
        assert (await request('/v1/mobile-release/apk', 'x' * 64))[0] == 404
    finally:
        server.close();await server.wait_closed()
