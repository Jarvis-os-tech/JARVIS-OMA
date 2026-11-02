"""Regression coverage for silent tool replies and blocked provider reception."""
import asyncio
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock

import pytest

from jarvis_voice.daemon import LiveVoice
from jarvis_voice.playback import Playback


def content(**kwargs):
    return NS(server_content=NS(**kwargs))


@pytest.mark.asyncio
async def test_local_filler_does_not_complete_real_tool_answer(tmp_path):
    pcm = b'\x01\x00' * 480
    (tmp_path / 'thinking.pcm').write_bytes(pcm)
    config = NS(fillers=NS(enable_local_fillers=True, filler_audio_dir=str(tmp_path),
                           phrases=[{'context': 'test', 'file': 'thinking.pcm'}]))
    voice = LiveVoice(Playback('test'), config=config)
    voice._reply_authorized = voice._waiting = True
    voice._play_filler_reflex('test')
    assert voice.player.queued_bytes == len(pcm)
    assert not voice._reply_started
    voice._tool_response_pending = True
    await voice.handle(content(turn_complete=True))
    assert voice._reply_authorized
    await voice.handle(content(model_turn=NS(parts=[NS(inline_data=NS(data=pcm))])))
    assert voice.player.queued_bytes == len(pcm)  # Real speech replaces queued filler.
    await voice.handle(content(turn_complete=True))
    assert not voice._reply_authorized


@pytest.mark.asyncio
async def test_tool_boundary_after_pre_tool_audio_keeps_answer_authorized():
    voice = LiveVoice(Playback('test'))
    voice._reply_authorized = voice._reply_started = True
    voice._tool_response_pending = True
    await voice.handle(content(turn_complete=True))
    assert voice._reply_authorized
    assert voice._tool_intermediate_received


@pytest.mark.asyncio
async def test_slow_tool_does_not_block_receive_and_is_cancelled_on_disconnect():
    started, interrupted, cancelled = asyncio.Event(), asyncio.Event(), asyncio.Event()
    voice = LiveVoice(Playback('test'))
    voice._reply_authorized = True

    async def slow_tool(*args):
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    voice.handle_tools = slow_tool
    voice.player.interrupt = AsyncMock(side_effect=interrupted.set)

    class Session:
        async def receive(self):
            yield NS(tool_call=NS(function_calls=[]))
            await started.wait()
            yield content(interrupted=True)
            await asyncio.Event().wait()

    worker = asyncio.create_task(voice.receive(Session()))
    try:
        await asyncio.wait_for(interrupted.wait(), .5)
    finally:
        worker.cancel()
        await asyncio.gather(worker, return_exceptions=True)
    assert cancelled.is_set()


@pytest.mark.asyncio
async def test_queued_action_from_ended_turn_is_not_executed():
    from google.genai import types

    started, release, rejected = asyncio.Event(), asyncio.Event(), asyncio.Event()
    voice = LiveVoice(Playback('test'))
    voice._reply_authorized = True
    calls = []

    async def execute(call, session):
        calls.append(call.function_calls[0].id)
        started.set()
        await release.wait()

    voice.handle_tools = execute

    class Session:
        async def send_tool_response(self, function_responses):
            assert function_responses[0].response['status'] == 'not_run'
            rejected.set()

        async def receive(self):
            for name in ['first', 'stale']:
                yield types.LiveServerMessage(tool_call=types.LiveServerToolCall(
                    function_calls=[types.FunctionCall(id=name, name='test_action', args={})]))
                await started.wait()
            voice.player.generation += 1
            release.set()
            await asyncio.Event().wait()

    worker = asyncio.create_task(voice.receive(Session()))
    try:
        await asyncio.wait_for(rejected.wait(), 1)
        assert calls == ['first']
    finally:
        worker.cancel()
        await asyncio.gather(worker, return_exceptions=True)


@pytest.mark.asyncio
async def test_receive_preserves_boundary_during_tool_and_plays_result():
    from google.genai import types

    started, release, answered = asyncio.Event(), asyncio.Event(), asyncio.Event()
    pcm = b'\x01\x00' * 480
    skills = NS(declarations=[{'name': 'test_action'}])

    async def execute(*args):
        started.set()
        await release.wait()
        return {'done': True}

    skills.execute = execute
    voice = LiveVoice(Playback('test'), skills=skills)
    voice._reply_authorized = voice._waiting = True
    boundary_seen = asyncio.Event()
    original = voice.handle

    async def handle(event, session):
        await original(event, session)
        if getattr(getattr(event, 'server_content', None), 'turn_complete', False):
            boundary_seen.set()

    voice.handle = handle

    class Session:
        send_tool_response = AsyncMock(side_effect=lambda **_: answered.set())

        async def receive(self):
            yield types.LiveServerMessage(tool_call=types.LiveServerToolCall(
                function_calls=[types.FunctionCall(id='one', name='test_action', args={})]))
            await started.wait()
            yield content(turn_complete=True)
            release.set()
            await answered.wait()
            yield content(model_turn=NS(parts=[NS(inline_data=NS(data=pcm))]))
            yield content(turn_complete=True)
            await asyncio.Event().wait()

    worker = asyncio.create_task(voice.receive(Session()))
    try:
        await asyncio.wait_for(boundary_seen.wait(), 1)
        # Let the real response and final boundary pass through the receiver.
        async with asyncio.timeout(1):
            while voice._reply_authorized:
                await asyncio.sleep(0)
        assert voice.player.queued_bytes == len(pcm)
        assert voice._pending_tool_batches == 0
    finally:
        worker.cancel()
        await asyncio.gather(worker, return_exceptions=True)
