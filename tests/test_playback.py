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
