import asyncio
import json
import sys
from types import SimpleNamespace

import pytest

from jarvis_control.device_bridge import build_parser, run


def test_bridge_defaults_to_loopback_without_lan_access():
    args = build_parser().parse_args([])
    assert args.host == '127.0.0.1'
    assert args.allow_lan is False


def test_public_plaintext_bridge_is_refused_before_loading_credentials(tmp_path):
    args = SimpleNamespace(host='0.0.0.0', port=8766, pairing=tmp_path / 'missing.json',
                           socket=tmp_path / 'socket', allow_lan=False, cert=None, key=None)
    with pytest.raises(ValueError, match='explicit --allow-lan'):
        asyncio.run(run(args))


@pytest.mark.parametrize(('cert', 'key'), [('cert.pem', None), (None, 'key.pem')])
def test_incomplete_tls_pair_has_clear_error(tmp_path, cert, key):
    args = SimpleNamespace(host='127.0.0.1', port=8766, pairing=tmp_path / 'missing.json',
                           socket=tmp_path / 'socket', allow_lan=False, cert=cert, key=key)
    with pytest.raises(ValueError, match='both --cert and --key'):
        asyncio.run(run(args))


@pytest.mark.parametrize(('configured_endpoint', 'expected'), [
    (None, 'http://127.0.0.1:8766'),
    ('https://bridge.example:8766', 'https://bridge.example:8766'),
])
def test_pairing_qr_uses_loopback_default_and_preserves_explicit_endpoint(
        tmp_path, monkeypatch, capsys, configured_endpoint, expected):
    from scripts import jarvis_pair

    credentials = {
        'version': 1, 'project_id': 'project', 'device_id': 'desktop', 'gcs_bucket': 'bucket',
        'auth_token': 'token', 'sync_secret': 'secret', 'endpoint': 'https://sync.example',
    }
    if configured_endpoint:
        credentials['execution_endpoint'] = configured_endpoint
    monkeypatch.setattr(jarvis_pair, 'get_or_create_credentials', lambda: credentials)
    monkeypatch.setattr(jarvis_pair, 'get_gemini_api_key', lambda: 'api-key')
    monkeypatch.setattr(jarvis_pair, 'qrcode', None)
    monkeypatch.setattr(sys, 'argv', ['jarvis_pair.py', '--show-payload', '--no-ascii',
                                     '--transient', '--output', str(tmp_path / 'qr.png')])

    assert jarvis_pair.main() in (None, 0)
    output = capsys.readouterr().out
    payload_text = output.split('Private pairing payload — do not share publicly:\n', 1)[1].splitlines()[0]
    assert json.loads(payload_text)['exec'] == expected
