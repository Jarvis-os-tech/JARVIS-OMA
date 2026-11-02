import asyncio
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock

import pytest

from voice_layer.config import Config
from voice_layer.daemon import LiveVoice
from voice_layer.local_speech import LocalSpeechConfig, WhistleClient, app_names, command_for
from voice_layer.playback import Playback
from voice_layer.speech import GateFrame


@pytest.mark.parametrize('text,expected', [
    ('Jarvis, please volume down.', ('system_control', {'action': 'volume_adjust', 'value': -5})),
    ('set brightness to 40 percent', ('system_control', {'action': 'brightness_set', 'value': 40})),
    ('switch to workspace two', ('system_control', {'action': 'workspace_switch', 'workspace': '2'})),
    ('Open Firefox', ('launch_app', {'app': 'firefox'})),
    ('stop talking', ('stop', {})),
    ('go to standby', ('enter_standby', {})),
    ('do not open Firefox', None), ('open Firefox and delete documents', None),
    ('could you explain volume down', None), ('set volume to 999', None),
    ('set brightness to 0', None), ('shutdown', None), ('open arbitrary-program', None),
])
def test_exact_commands_only(text, expected):
    assert command_for(text, {'firefox': 'firefox'}) == expected


def test_ambiguous_application_name_is_not_routed():
    assert 'editor' not in app_names([('a', 'Editor; Text'), ('b', 'Editor; Code')])


def instance(text='volume down'):
    skills = NS(execute=AsyncMock(return_value='{"ok":true,"status":"completed"}'))
    voice = LiveVoice(Playback('test'), config=Config(), skills=skills)
    voice.local_speech = NS(ready=True, config=LocalSpeechConfig(enabled=True),
                            transcribe=AsyncMock(return_value=text))
    voice._reply_authorized = True
    voice._local_apps = {'firefox': 'firefox'}
    return voice


async def short_turn(voice, session):
    queue = asyncio.Queue()
    queue.put_nowait((GateFrame(bytes(640), opened=True), 0))
    queue.put_nowait((GateFrame(bytes(640), closed=True), 0))
    worker = asyncio.create_task(voice._send_frames(session, queue))
    return worker


@pytest.mark.asyncio
async def test_local_action_never_reaches_cloud():
    voice = instance()
    session = NS(send_realtime_input=AsyncMock())
    worker = await short_turn(voice, session)
    try:
        async with asyncio.timeout(.5):
            while voice.last_local_outcome is None:
                await asyncio.sleep(0)
        voice.skills.execute.assert_awaited_once_with('system_control', {'action': 'volume_adjust', 'value': -5})
        session.send_realtime_input.assert_not_awaited()
        assert not voice._reply_authorized
    finally:
        worker.cancel()
        await asyncio.gather(worker, return_exceptions=True)


@pytest.mark.asyncio
@pytest.mark.parametrize('text', ['tell me a story', None])
async def test_unmatched_or_uncertain_short_speech_forwards_original_audio_once(text):
    voice = instance(text)
    finished = asyncio.Event()
    sent = []
    async def send(**kwargs):
        sent.append(kwargs)
        if 'activity_end' in kwargs:
            finished.set()
    worker = await short_turn(voice, NS(send_realtime_input=send))
    try:
        await asyncio.wait_for(finished.wait(), .5)
        assert [next(iter(item)) for item in sent] == ['activity_start', 'audio', 'audio', 'activity_end']
        voice.skills.execute.assert_not_awaited()
    finally:
        worker.cancel()
        await asyncio.gather(worker, return_exceptions=True)


@pytest.mark.asyncio
async def test_long_speech_starts_cloud_streaming_before_turn_ends():
    voice = instance()
    voice.local_speech.config.max_command_seconds = .02
    queue = asyncio.Queue()
    queue.put_nowait((GateFrame(bytes(640), opened=True), 0))
    queue.put_nowait((GateFrame(bytes(640)), 0))
    sent = asyncio.Event()
    async def send(**kwargs):
        if 'audio' in kwargs:
            sent.set()
    worker = asyncio.create_task(voice._send_frames(NS(send_realtime_input=send), queue))
    try:
        await asyncio.wait_for(sent.wait(), .5)
        voice.local_speech.transcribe.assert_not_awaited()
        voice.skills.execute.assert_not_awaited()
    finally:
        worker.cancel()
        await asyncio.gather(worker, return_exceptions=True)


@pytest.mark.asyncio
async def test_offline_short_command_uses_same_executor():
    voice = instance()
    worker = await short_turn(voice, None)
    try:
        async with asyncio.timeout(.5):
            while voice.last_local_outcome is None:
                await asyncio.sleep(0)
        voice.skills.execute.assert_awaited_once()
    finally:
        worker.cancel()
        await asyncio.gather(worker, return_exceptions=True)


@pytest.mark.asyncio
async def test_stale_decode_does_not_execute_after_new_turn():
    voice = instance()
    async def decode(pcm):
        voice.gate.accepted_turns += 1
        return 'volume down'
    voice.local_speech.transcribe = decode
    assert await voice._try_local_command(bytes(640), (0, 0))
    voice.skills.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_failed_action_is_consumed_without_cloud_retry():
    voice = instance()
    voice.skills.execute.side_effect = RuntimeError('execution uncertain')
    assert await voice._try_local_command(bytes(640), (0, 0))
    assert voice.last_local_outcome == 'failed'
    voice.skills.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_native_timeout_kills_worker_and_returns_to_cloud_path():
    client = WhistleClient(LocalSpeechConfig(enabled=True, decode_timeout=.05))
    stopped = asyncio.Event()
    async def forever():
        await asyncio.Event().wait()
    process = NS(stdin=NS(write=lambda data: None, drain=AsyncMock()),
                 stdout=NS(readline=forever), returncode=None,
                 kill=stopped.set, wait=AsyncMock())
    client.process, client.ready = process, True
    assert await asyncio.wait_for(client.transcribe(bytes(640)), .2) is None
    assert stopped.is_set()
    assert not client.ready


@pytest.mark.asyncio
async def test_low_confidence_words_cannot_run_a_command():
    client = WhistleClient(LocalSpeechConfig(enabled=True))
    client.process = NS(stdin=NS(write=lambda data: None, drain=AsyncMock()),
                        stdout=NS(readline=AsyncMock(return_value=b'{"text":"volume down","words":[{"probability":0.3}]}\n')))
    client.ready = True
    assert await client.transcribe(bytes(640)) is None


@pytest.mark.asyncio
async def test_cancellation_does_not_abandon_an_admitted_action():
    voice = instance()
    admitted, finish = asyncio.Event(), asyncio.Event()
    async def action(*args):
        admitted.set()
        await finish.wait()
        return '{"ok":true}'
    voice.skills.execute.side_effect = action
    worker = asyncio.create_task(voice._try_local_command(bytes(640), (0, 0)))
    await admitted.wait()
    worker.cancel()
    await asyncio.sleep(0)
    assert not worker.done()
    finish.set()
    with pytest.raises(asyncio.CancelledError):
        await worker
    voice.skills.execute.assert_awaited_once()
