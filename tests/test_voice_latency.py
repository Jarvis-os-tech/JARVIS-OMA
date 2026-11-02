import asyncio
import struct
from types import SimpleNamespace as NS

import pytest

from jarvis_voice.playback import Playback
from jarvis_voice.standby import StandbyController


def test_real_reply_drops_unplayed_filler_without_changing_generation():
    player = Playback('test')
    player.enqueue_filler(struct.pack('<h', 2000) * 24000)
    reply = struct.pack('<h', -2000) * 960
    player.enqueue_response(reply)
    assert player.queue.qsize() == 2
    assert player.queued_bytes == len(reply)
    assert player.generation == 0
    first = player.queue.get_nowait()[1]
    assert struct.unpack_from('<h', first)[0] > 1900
    assert struct.unpack_from('<h', first, 958)[0] == -2000
    assert player.queue.get_nowait()[1] == reply[960:]


def test_new_playback_generation_cannot_mix_stale_filler():
    player = Playback('test')
    player.enqueue_filler(bytes(9600))
    player.cancel_pending()
    reply = b'\x01\x00' * 480
    player.enqueue_response(reply)
    assert player.queue.get_nowait() == (1, reply)
    assert player.queued_bytes == len(reply)


@pytest.mark.asyncio
async def test_wake_requested_before_listener_is_not_lost():
    controller = StandbyController(detector=None, arming_delay=30)
    controller._requested.set()
    controller.wake()
    await asyncio.wait_for(controller.listen_for_wake_word(asyncio.StreamReader()), .2)
    assert not controller.engaged


@pytest.mark.asyncio
async def test_manual_wake_interrupts_arming_delay():
    controller = StandbyController(detector=NS(reset=lambda: None), arming_delay=30)
    worker = asyncio.create_task(controller.listen_for_wake_word(asyncio.StreamReader()))
    try:
        await asyncio.sleep(0)
        controller.wake()
        await asyncio.wait_for(worker, .2)
        assert not controller.engaged
    finally:
        worker.cancel()
        await asyncio.gather(worker, return_exceptions=True)


@pytest.mark.asyncio
async def test_fresh_capture_preserves_wake_audio_buffered_while_arming():
    frame = b'\x01\x00' * 320
    detector = NS(reset=lambda: None, process=lambda pcm: pcm == frame)
    controller = StandbyController(detector=detector, arming_delay=.01)
    reader = asyncio.StreamReader()
    reader.feed_data(frame)
    await asyncio.wait_for(controller.listen_for_wake_word(reader), .2)
    assert not controller.engaged


@pytest.mark.asyncio
async def test_wake_while_awake_does_not_cancel_the_next_standby():
    detector = NS(reset=lambda: None, process=lambda frame: False)
    controller = StandbyController(detector=detector, arming_delay=0)
    controller.wake()
    assert not controller._wake_event.is_set()
    await controller.request()
    worker = asyncio.create_task(controller.listen_for_wake_word(asyncio.StreamReader()))
    try:
        await asyncio.sleep(0)
        assert not worker.done()
        controller.wake()
        await asyncio.wait_for(worker, .2)
    finally:
        worker.cancel()
        await asyncio.gather(worker, return_exceptions=True)


@pytest.mark.asyncio
async def test_answer_replaces_queued_waiting_notice_too():
    from jarvis_voice.daemon import LiveVoice
    instance = LiveVoice(Playback('test'))
    instance._reply_authorized = True
    instance._reply_notices = {'reply_waiting': bytes(48000)}
    instance._play_reply_notice('reply_waiting')
    await instance.handle(NS(server_content=NS(model_turn=NS(parts=[
        NS(inline_data=NS(data=b'\x01\x00' * 480))]))))
    assert instance.player.queue.qsize() == 1
    assert instance.player.queued_bytes == 960
