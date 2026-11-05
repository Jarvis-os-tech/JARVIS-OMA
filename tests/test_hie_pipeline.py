"""Conversation scenarios using real admission/playback queues, without devices."""
import asyncio
import struct
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock

import pytest

from voice_layer.config import Config
from voice_layer.daemon import LiveVoice
from voice_layer.playback import Playback
from voice_layer.speech import GateFrame


@pytest.mark.asyncio
async def test_long_narrative_backchannel_preserves_resumed_microphone_turn(monkeypatch):
    voice = LiveVoice(Playback('test'), config=Config(), barge_in=False)
    voice.connected = voice.echo_cancellation_active = True
    voice.gate.detector = lambda pcm: .95 if any(pcm) else 0
    speech = struct.pack('<320h', *([2000] * 320))
    frames = [speech] * 420 + [bytes(640)] * 20 + [speech] * 5 + [bytes(640)] * 60
    clock = [100.0]
    monkeypatch.setattr('voice_layer.daemon.time.monotonic', lambda: clock[0])

    class Reader:
        index = 0

        async def readexactly(self, size):
            if self.index == len(frames):
                raise asyncio.IncompleteReadError(b'', size)
            clock[0] = 100 + self.index * .02
            if self.index > 1:
                voice._user_text = 'I have been developing a personal project and learning Python'
            chunk = frames[self.index]
            self.index += 1
            return chunk

    queue = asyncio.Queue()
    with pytest.raises(EOFError):
        await voice._capture_audio(Reader(), queue)
    captured = [queue.get_nowait() for _ in range(queue.qsize())]
    assert voice.backchannels_played == 1
    assert voice.gate.accepted_turns == 1
    assert voice.player.generation == 0
    assert not voice._listening_backchannel
    assert voice.player.queue.empty()
    assert sum(frame.opened for frame, _ in captured) == 1
    assert sum(frame.closed for frame, _ in captured) == 1
    assert all(generation == 0 for _, generation in captured)
    assert b''.join(frame.pcm for frame, _ in captured).count(speech) >= 425


@pytest.mark.parametrize('state', ['muted', 'standby', 'tool', 'answer', 'disabled', 'short_pause', 'no_text', 'no_aec', 'ack_played'])
def test_backchannels_require_safe_conversation_state(state):
    voice = LiveVoice(Playback('test'), config=Config())
    voice.connected = voice.echo_cancellation_active = voice.gate.active = True
    voice.gate._quiet = 20
    voice._speech_opened_at = 0
    voice._user_text = 'I have been developing a personal project and learning Python'
    if state == 'muted': voice.muted = True
    elif state == 'standby': voice.standby._requested.set()
    elif state == 'tool': voice._tools_in_flight = 1
    elif state == 'answer': voice._reply_started = True
    elif state == 'disabled': voice.config.fillers.enable_local_fillers = False
    elif state == 'short_pause': voice.gate._quiet = 5
    elif state == 'no_aec': voice.echo_cancellation_active = False
    elif state == 'ack_played': voice._filler_played = True
    else: voice._user_text = ''
    assert not voice._maybe_backchannel(10)
    assert voice.player.queue.empty()


@pytest.mark.asyncio
async def test_answer_preempts_listening_audio_without_invalidating_user_frames():
    voice = LiveVoice(Playback('test'), config=Config())
    voice.connected = voice.echo_cancellation_active = voice.gate.active = True
    voice.gate._quiet = 20
    voice._speech_opened_at = 0
    voice._user_text = 'I have been developing a personal project and learning Python'
    assert voice._maybe_backchannel(10)
    voice.gate.active = False
    voice._reply_authorized = True
    answer = b'\x05\x00' * 480
    await voice.handle(NS(server_content=NS(model_turn=NS(parts=[NS(inline_data=NS(data=answer))]))))
    assert not voice._listening_backchannel
    assert voice.player.generation == 0
    assert b''.join(chunk for _, chunk in voice.player.queue._queue) == answer


@pytest.mark.asyncio
@pytest.mark.parametrize('pending_state', ['running', 'finished', 'stale'])
async def test_deferred_contextual_ack_replays_only_current_running_work(pending_state):
    voice = LiveVoice(Playback('test'), config=Config())
    voice._reply_authorized = voice.gate.active = True
    voice._acknowledge_task_start('system_control', {'action': 'volume_get'})
    voice.gate.active = False
    voice._tools_in_flight = int(pending_state != 'finished')
    if pending_state == 'stale':
        serial, name, args = voice._pending_task_ack
        voice._pending_task_ack = (serial - 1, name, args)
    queue = asyncio.Queue()
    queue.put_nowait((GateFrame(bytes(640), opened=True, closed=True), 0))
    session = NS(send_realtime_input=AsyncMock())
    worker = asyncio.create_task(voice._send_frames_cloud(session, queue))
    try:
        async with asyncio.timeout(1):
            while voice.activity_end_sent_at is None:
                await asyncio.sleep(0)
        if pending_state == 'running':
            assert voice.last_acknowledgement == 'Let me check that.'
            expected = voice._reply_notices['ack_general_2']
            assert b''.join(chunk for _, chunk in voice.player.queue._queue) == expected
        else:
            assert voice.player.queue.empty()
    finally:
        worker.cancel()
        await asyncio.gather(worker, return_exceptions=True)


@pytest.mark.asyncio
async def test_listening_cue_echo_is_filtered_without_becoming_user_speech(monkeypatch):
    import math
    voice = LiveVoice(Playback('test'), config=Config())
    voice.connected = voice.echo_cancellation_active = True
    voice.gate.detector = lambda pcm: .95 if any(pcm) else 0
    speech = struct.pack('<320h', *([2000] * 320))

    def tone(rate):
        return struct.pack(f'<{rate // 5}h', *(
            round(10000 * math.sin(2 * math.pi * 440 * i / rate)) for i in range(rate // 5)))

    echo = tone(16000)
    echo_frames = [echo[i:i + 640] for i in range(0, len(echo), 640)]
    frames = [speech] * 420 + [bytes(640)] * 20 + echo_frames + [bytes(640)] * 60
    clock = [100.0]
    monkeypatch.setattr('voice_layer.daemon.time.monotonic', lambda: clock[0])

    class Reader:
        index = 0

        async def readexactly(self, size):
            if self.index == len(frames):
                raise asyncio.IncompleteReadError(b'', size)
            clock[0] = 100 + self.index * .02
            if self.index > 1:
                voice._user_text = 'I have been developing a personal project and learning Python'
            if self.index == 440:
                voice.player.reference.add(tone(24000), now=clock[0])
            chunk = frames[self.index]
            self.index += 1
            return chunk

    queue = asyncio.Queue()
    with pytest.raises(EOFError):
        await voice._capture_audio(Reader(), queue)
    captured = [queue.get_nowait()[0] for _ in range(queue.qsize())]
    assert voice.backchannels_played == 1
    assert voice.gate.accepted_turns == 1
    uploaded = b''.join(frame.pcm for frame in captured)
    assert echo_frames[0] not in uploaded
    assert uploaded.count(speech) == 420
    assert sum(frame.closed for frame in captured) == 1
