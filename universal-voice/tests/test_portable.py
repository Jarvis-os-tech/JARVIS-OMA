import ast
import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from universal_voice import config
from universal_voice.daemon import LiveVoice, run
from universal_voice.playback import Playback


def test_no_host_application_imports():
    package = Path(config.__file__).parent
    for path in package.glob('*.py'):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.ImportFrom):
                assert not (node.module or '').startswith(('jarvis_control', 'jarvis_memory', 'orchestration', 'skills.'))


def test_separate_paths_and_config(monkeypatch, tmp_path):
    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path))
    assert config.SOCKET_PATH.parent.name == 'universal-voice'
    assert not config.load().enable_tools
    assert config.load().barge_in
    directory = tmp_path / 'universal-voice'
    directory.mkdir()
    (directory / 'config.toml').write_text('enable_tools = true\n')
    with pytest.raises(ValueError, match='voice only'):
        config.load()


@pytest.mark.asyncio
async def test_runner_has_no_application_service(monkeypatch):
    launch = AsyncMock()
    monkeypatch.setattr('universal_voice.daemon._run_voice', launch)
    args = SimpleNamespace(config_obj=config.Config())
    await run(args, 'dummy-test-key')
    assert launch.await_args.args[-1] is None


@pytest.mark.asyncio
async def test_unattached_tools_are_rejected():
    voice = LiveVoice(Playback('test'), config=config.Config())
    session = SimpleNamespace(send_tool_response=AsyncMock())
    call = SimpleNamespace(function_calls=[SimpleNamespace(id='1', name='open_application')])
    await voice.handle_tools(call, session)
    reply = session.send_tool_response.await_args.kwargs['function_responses'][0]
    assert reply.response['status'] == 'not_run'


def test_assets_match_shipped_checksums():
    import hashlib
    assets = Path(config.__file__).parent / 'assets'
    manifest = json.loads((assets / 'acknowledgements.json').read_text())
    # Manifest structure follows the original frozen cache.
    assert (assets / 'ack_short_hmm.pcm').stat().st_size == 22080
    for name, entry in manifest.items():
        assert hashlib.sha256((assets / (name + '.pcm')).read_bytes()).hexdigest() == entry['sha256']

@pytest.mark.asyncio
async def test_startup_reaches_provider_without_parent_project(monkeypatch):
    from universal_voice.daemon import _run_voice
    from google import genai
    for owner in ('universal_voice.echo.MonitorEchoCancellation', 'universal_voice.daemon.ControlServer'):
        monkeypatch.setattr(owner + '.start', AsyncMock())
        monkeypatch.setattr(owner + '.close', AsyncMock())
    reached = []
    def client(**kwargs):
        reached.append(True)
        raise RuntimeError('synthetic provider unavailable')
    monkeypatch.setattr(genai, 'Client', client)
    with pytest.raises(RuntimeError, match='synthetic provider unavailable'):
        await _run_voice(SimpleNamespace(retries=0), 'dummy-test-key', config.Config(), None)
    assert reached
