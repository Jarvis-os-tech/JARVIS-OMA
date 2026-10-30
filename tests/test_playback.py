# tests/test_playback.py
import asyncio
from pathlib import Path
import sys
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

@pytest.mark.asyncio
async def test_fix6_stale_generation_discarded_not_error():
    """Fix 6: cancelled playback generation must discard stale chunks cleanly."""
    from jarvis_voice.playback import Playback

    player = Playback(sink='default')
    # Enqueue data in generation 0
    player.enqueue(b'\x00' * 960)
    assert player.queued_bytes == 960

    # Cancel — advances generation
    player.cancel_pending()
    assert player.generation == 1
    assert player.queued_bytes == 0

    # Enqueue in new generation
    player.enqueue(b'\x00' * 960)
    assert player.queued_bytes == 960

@pytest.mark.asyncio
async def test_playback_backlog_raises():
    """Exceeding bounded backlog raises PlaybackBacklogError."""
    from jarvis_voice.playback import Playback, PlaybackBacklogError

    player = Playback(sink='default')
    # Fill past the max
    with pytest.raises(PlaybackBacklogError):
        for _ in range(7000):
            player.enqueue(b'\x00' * 960)

@pytest.mark.asyncio
async def test_begin_reply_resets_timing():
    """begin_reply resets first-write timing state."""
    from jarvis_voice.playback import Playback

    player = Playback(sink='default')
    player.enqueue(b'\x00' * 960)
    player.begin_reply()
    assert player.first_enqueued_at is None
    assert player.first_write_at is None

@pytest.mark.asyncio
async def test_cancel_pending_clears_queue():
    """cancel_pending empties the queue and advances generation."""
    from jarvis_voice.playback import Playback

    player = Playback(sink='default')
    player.enqueue(b'\x00' * 960)
    player.enqueue(b'\x00' * 960)
    assert player.queued_bytes == 1920

    player.cancel_pending()
    assert player.queued_bytes == 0
    assert player.queue.empty()


@pytest.mark.asyncio
async def test_is_playing_with_echo_tail():
    """is_playing honors echo tail duration for acoustic reflection holdoff."""
    import time
    from jarvis_voice.playback import Playback

    player = Playback(sink='default')
    assert not player.is_playing()

    # Simulate active playback ending 0.1s from now
    now = time.monotonic()
    player.playback_until = now + 0.1

    assert player.is_playing(tail=0.0)
    assert player.is_playing(tail=0.35)

    # Fast forward past playback_until but within tail
    player.playback_until = now - 0.05
    assert not player.is_playing(tail=0.0)
    assert player.is_playing(tail=0.35)

    # Past tail
    player.playback_until = now - 0.40
    assert not player.is_playing(tail=0.35)


@pytest.mark.asyncio
async def test_fragmented_reply_keeps_pcm_intact_with_continuity_buffer():
    from types import SimpleNamespace
    from unittest.mock import AsyncMock, Mock, patch
    from jarvis_voice.playback import Playback

    process = SimpleNamespace(returncode=None, stdin=SimpleNamespace(
        write=Mock(), drain=AsyncMock(), close=Mock()))
    player = Playback('default')

    async def until(predicate):
        async with asyncio.timeout(1):
            while not predicate():
                await asyncio.sleep(0)

    with patch('jarvis_voice.playback.asyncio.create_subprocess_exec',
               AsyncMock(return_value=process)) as spawn:
        worker = asyncio.create_task(player.run())
        try:
            player.enqueue(b'\x01\x00')
            await until(lambda: player._writing)
            process.stdin.write.assert_not_called()
            rest = b'\x02\x00' * 3000
            player.enqueue(rest)
            player.finish_reply()
            await until(lambda: sum(len(c.args[0]) for c in process.stdin.write.call_args_list) == 2 + len(rest))
            assert b''.join(c.args[0] for c in process.stdin.write.call_args_list) == b'\x01\x00' + rest
            args = spawn.call_args.args
            assert args[args.index('--latency') + 1] == '80ms'
        finally:
            worker.cancel()
            await asyncio.gather(worker, return_exceptions=True)


@pytest.mark.asyncio
async def test_cancel_during_buffering_discards_old_audio_and_flushes_short_reply():
    from types import SimpleNamespace
    from unittest.mock import AsyncMock, Mock, patch
    from jarvis_voice.playback import Playback

    process = SimpleNamespace(returncode=None, stdin=SimpleNamespace(
        write=Mock(), drain=AsyncMock(), close=Mock()))
    player = Playback('default')

    async def until(predicate):
        async with asyncio.timeout(1):
            while not predicate():
                await asyncio.sleep(0)

    with patch('jarvis_voice.playback.asyncio.create_subprocess_exec', AsyncMock(return_value=process)):
        worker = asyncio.create_task(player.run())
        try:
            player.enqueue(b'\x01\x00')
            await until(lambda: player._writing)
            player.cancel_pending()
            player.enqueue(b'\x02\x00')
            player.finish_reply()
            await until(lambda: process.stdin.write.called)
            assert [c.args[0] for c in process.stdin.write.call_args_list] == [b'\x02\x00']
        finally:
            worker.cancel()
            await asyncio.gather(worker, return_exceptions=True)
