"""Synthetic input only; no real capture, playback or cloud requests."""
import asyncio
import base64
import json
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from skills.input_bar import TestBar as InputBar
from voice_layer.daemon import LiveVoice
from voice_layer.playback import Playback


@pytest.mark.asyncio
@pytest.mark.parametrize('name,mime,data,expected', [
    ('photo.png', 'image/png', b'\x89PNG\r\n\x1a\nsynthetic', 'image/png'),
    ('clip.wav', 'audio/wav', b'RIFF\x00\xffWAVEsynthetic', 'audio/wav'),
    ('clip.mp3', '', b'ID3\x00\xffsynthetic', 'audio/mpeg'),
    ('notes.txt', 'text/plain', b'Example notes', 'Example notes'),
    ('notes.pdf', 'application/pdf', b'%PDF-synthetic', 'Extracted example notes'),
    ('scan.pdf', 'application/pdf', b'%PDF-synthetic-scan', 'unreadable or scanned'),
])
async def test_attachment_bytes_and_metadata_reach_session(monkeypatch, name, mime, data, expected):
    bar = InputBar()
    bar.items.put_nowait({'text': '', 'name': name, 'mime': mime, 'data': data})
    voice = LiveVoice(Playback('test'), skills=NS(test_bar=bar))
    # Extraction is a boundary stub; no external document tools or file contents used.
    monkeypatch.setattr('subprocess.run', lambda *a, **k: NS(
        stdout='' if name == 'scan.pdf' else 'Extracted example notes', returncode=0))
    received = asyncio.Event()
    contents = []

    async def send(**kwargs):
        contents.extend(kwargs['turns'])
        assert kwargs['turn_complete'] is True
        received.set()

    worker = asyncio.create_task(voice.send_inputs(NS(send_client_content=send)))
    try:
        await asyncio.wait_for(received.wait(), 2)
    finally:
        worker.cancel()
        await asyncio.gather(worker, return_exceptions=True)
    assert len(contents) == 1 and contents[0].role == 'user'
    parts = contents[0].parts
    text = '\n'.join(p.text for p in parts if p.text)
    assert name in text
    if expected.startswith(('image/', 'audio/')):
        blobs = [p.inline_data for p in parts if p.inline_data]
        assert len(blobs) == 1
        assert blobs[0].data == data and blobs[0].mime_type == expected
    else:
        assert expected in text


def test_input_submission_requires_token_and_preserves_bytes():
    bar = InputBar()
    # No skip: a host unable to run loopback cannot certify this contract.
    endpoint, token = bar.start().split('/#')
    server, thread = bar.server, bar.thread
    data = b'\x00\xffsynthetic attachment'
    payload = json.dumps({'text': 'Inspect this', 'file': base64.b64encode(data).decode(),
                          'name': 'example.wav', 'mime': 'audio/wav'}).encode()

    def submit(key, body=payload):
        return urlopen(Request(endpoint + '/submit', data=body, method='POST',
                               headers={'Content-Type': 'application/json', 'X-Jarvis-Token': key}), timeout=2)

    try:
        for key in ('', 'wrong-token'):
            with pytest.raises(HTTPError) as failure:
                submit(key)
            assert failure.value.code == 403
            failure.value.close()
            assert bar.pop() is None
        with submit(token) as response:
            assert response.status == 202
        assert bar.pop() == {'text': 'Inspect this', 'data': data, 'name': 'example.wav', 'mime': 'audio/wav'}
        with pytest.raises(HTTPError) as failure:
            submit(token, b'{"file":"not-base64!"}')
        assert failure.value.code == 400
        failure.value.close()
        assert bar.pop() is None
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
        assert not thread.is_alive()
