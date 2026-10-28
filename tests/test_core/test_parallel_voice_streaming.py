"""Streaming contract: speech upload and reply playback precede turn completion."""
import asyncio
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, Mock, patch

import pytest
from google.genai import types

from core.speech_turn import SpeechTurnGate
from core.stable_voice import LiveVoice, Playback

FRAME = b'\x00\x10' * 320


async def until(predicate):
    async with asyncio.timeout(1):
        while not predicate():
            await asyncio.sleep(0)


@pytest.mark.asyncio
async def test_opening_words_upload_while_the_user_is_still_speaking():
    voice = LiveVoice(Playback('test'), speech_gate=SpeechTurnGate(detector=lambda _: .9,
                                                                silence_frames=20))
    reader = asyncio.StreamReader()
    session = NS(send_realtime_input=AsyncMock())
    worker = asyncio.create_task(voice.send_audio(session, reader))
    try:
        reader.feed_data(FRAME * 2)
        def speech_sent():
            return any('audio' in c.kwargs and any(c.kwargs['audio'].data)
                       for c in session.send_realtime_input.await_args_list)
        await until(speech_sent)
        assert voice.gate.active
        assert not any('activity_end' in c.kwargs for c in session.send_realtime_input.await_args_list)
        assert voice.first_speech_upload_ms is not None
        reader.feed_data(bytes(640) * 20)
        reader.feed_eof()
        with pytest.raises(EOFError):
            await worker
        assert sum('activity_end' in c.kwargs for c in session.send_realtime_input.await_args_list) == 1
    finally:
        worker.cancel()
        await asyncio.gather(worker, return_exceptions=True)


@pytest.mark.asyncio
async def test_network_backpressure_does_not_block_microphone_capture():
    voice = LiveVoice(Playback('test'), speech_gate=SpeechTurnGate(detector=lambda _: .9))
    reader = asyncio.StreamReader()
    network_entered, release = asyncio.Event(), asyncio.Event()
    async def send(**kwargs):
        network_entered.set()
        await release.wait()
    worker = asyncio.create_task(voice.send_audio(NS(send_realtime_input=send), reader))
    try:
        reader.feed_data(FRAME)
        await asyncio.wait_for(network_entered.wait(), 1)
        reader.feed_data(FRAME * 5)
        await until(lambda: voice._capture_queue.qsize() >= 5)
        assert voice.gate.accepted_turns == 1
        assert voice._capture_queue.maxsize == 50
    finally:
        worker.cancel()
        await asyncio.gather(worker, return_exceptions=True)
    assert not any(t.get_name() == 'jarvis-microphone-capture'
                   for t in asyncio.all_tasks() if not t.done())


@pytest.mark.asyncio
async def test_first_audio_writes_before_model_finishes_and_receiving_keeps_running():
    written, release = asyncio.Event(), asyncio.Event()
    async def drain():
        written.set()
        await release.wait()
    process = NS(returncode=None, stdin=NS(write=Mock(), drain=drain, close=Mock()),
                 terminate=Mock(), wait=AsyncMock(return_value=0))
    player = Playback('test')
    voice = LiveVoice(player)
    voice._reply_authorized = True
    event = types.LiveServerMessage(server_content=types.LiveServerContent(model_turn=types.Content(
        parts=[types.Part(inline_data=types.Blob(data=b'\x01\x00' * 480,
                                               mime_type='audio/pcm;rate=24000'))])))
    with patch('core.stable_voice.asyncio.create_subprocess_exec', AsyncMock(return_value=process)) as spawn:
        await player.prepare()
        await player.prepare()
        assert not player.busy  # Warming playback must not suppress user speech.
        worker = asyncio.create_task(player.run())
        try:
            await voice.handle(event)
            await asyncio.wait_for(written.wait(), 1)
            process.stdin.write.assert_called_once()
            assert voice._reply_authorized  # No turn-complete event has arrived.
            await voice.handle(event)
            assert player.queue.qsize() == 1  # Receive does not await playback.
            assert spawn.await_count == 1  # First chunk reuses the warm process.
            release.set()
            await until(lambda: player.first_chunk_write_ms is not None)
        finally:
            worker.cancel()
            await asyncio.gather(worker, return_exceptions=True)
            await player.interrupt()
