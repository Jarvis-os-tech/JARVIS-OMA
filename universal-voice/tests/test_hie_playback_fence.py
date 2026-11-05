"""Playback cancellation fences in-flight audio without resetting a live turn."""
import asyncio
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, Mock

import pytest

from universal_voice.playback import Playback


async def until(predicate):
    async with asyncio.timeout(1):
        while not predicate():
            await asyncio.sleep(0)


def process(*, drain=None):
    return NS(returncode=None, stdin=NS(write=Mock(), drain=drain or AsyncMock(), close=Mock()),
              wait=AsyncMock(return_value=0), terminate=Mock(), kill=Mock())


@pytest.mark.asyncio
async def test_preserving_cancel_during_prime_discards_old_chunk():
    player = Playback('test')
    spawned = process()
    spawn = AsyncMock(return_value=spawned)
    from unittest.mock import patch

    worker = None
    with patch('universal_voice.playback.asyncio.create_subprocess_exec', spawn):
        worker = asyncio.create_task(player.run())
        try:
            player.enqueue(b'\x01\x00')
            await until(lambda: player._writing)
            generation = player.generation
            assert player.cancel_pending(preserve_generation=True) is None
            assert player.generation == generation
            assert not player.busy
            player.enqueue(b'\x02\x00')
            player.finish_reply()
            await until(lambda: spawned.stdin.write.called)
            assert spawned.stdin.write.call_args_list == [((b'\x02\x00',),)]
        finally:
            worker.cancel()
            await asyncio.gather(worker, return_exceptions=True)


@pytest.mark.asyncio
async def test_preserving_cancel_during_spawn_stops_unpublished_process():
    player = Playback('test')
    started, release = asyncio.Event(), asyncio.Event()
    spawned = process()

    async def spawn(*args, **kwargs):
        started.set()
        await release.wait()
        return spawned

    from unittest.mock import patch
    with patch('universal_voice.playback.asyncio.create_subprocess_exec', spawn):
        preparing = asyncio.create_task(player.prepare())
        await started.wait()
        generation = player.generation
        assert player.cancel_pending(preserve_generation=True) is None
        release.set()
        assert not await preparing
    assert player.generation == generation
    assert player.process is None
    spawned.terminate.assert_called_once()
    spawned.wait.assert_awaited_once()


@pytest.mark.asyncio
async def test_preserving_cancel_during_drain_fences_old_audio_and_accounting():
    player = Playback('test')
    drain_old, drain_new = asyncio.Event(), asyncio.Event()
    old_process, new_process = process(drain=AsyncMock(side_effect=drain_old.wait)), process(
        drain=AsyncMock(side_effect=drain_new.wait))
    spawned = iter((old_process, new_process))

    from unittest.mock import patch
    with patch('universal_voice.playback.asyncio.create_subprocess_exec',
               AsyncMock(side_effect=lambda *args, **kwargs: next(spawned))):
        worker = asyncio.create_task(player.run())
        try:
            player.enqueue(b'\x01\x00' * 480)
            await until(lambda: old_process.stdin.write.called)
            generation = player.generation
            assert player.cancel_pending(preserve_generation=True) is old_process
            assert player.generation == generation
            assert player.playback_until == 0
            assert not player.busy

            drain_old.set()
            player.enqueue(b'\x02\x00' * 480)
            player.finish_reply()
            await until(lambda: new_process.stdin.write.called)
            assert player.playback_until == 0  # Old drain completion added no playback time.
            assert old_process.stdin.write.call_args_list == [((b'\x01\x00' * 480,),)]
            assert new_process.stdin.write.call_args_list == [((b'\x02\x00' * 480,),)]
            drain_new.set()
            await until(lambda: player.playback_until > 0)
        finally:
            worker.cancel()
            await asyncio.gather(worker, return_exceptions=True)


def test_ordinary_cancel_still_advances_generation_and_epoch():
    player = Playback('test')
    player.enqueue(b'\x01\x00')
    assert player.cancel_pending() is None
    assert player.generation == 1
    assert player._epoch == 1
    assert player.queue.empty()
