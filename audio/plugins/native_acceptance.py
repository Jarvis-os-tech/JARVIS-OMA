"""Local native device acceptance; silence only, no provider connection.

Stop the primary voice service before running. Creates its own AEC owner,
exercises turn/cancel/recovery, and cleans up all owned resources. This measures
transport/render acknowledgement, not audible latency or echo quality.
"""
import argparse
import asyncio
import contextlib
import json
import os
import time
from pathlib import Path

from audio.echo_cancel import EchoCancellation
from audio.engine import StreamLostError
from audio.extension import ExtendedAudioEngine
from audio.plugins.native_backend import NativeCompanionEngine
from core.agent import recover_audio


async def until(predicate, seconds=3):
    async with asyncio.timeout(seconds):
        while not predicate():
            await asyncio.sleep(.005)


def rss_bytes(pid):
    return int(Path(f'/proc/{pid}/statm').read_text().split()[1]) * os.sysconf('SC_PAGE_SIZE')


async def run(duration, output):
    echo = EchoCancellation()
    base = NativeCompanionEngine(native_webrtc_gain=True)
    engine = ExtendedAudioEngine(base)
    consumer = None
    captured = 0
    gaps = []
    result = {'scope': 'local silent device test; no cloud, no acoustic parity claim'}

    async def consume():
        nonlocal captured
        last = None
        while True:
            frame = await engine.async_input_queue.get()
            assert len(frame) == 640
            now = time.monotonic()
            if last is not None:
                gaps.append(now - last)
            last = now
            captured += 1

    try:
        await echo.start(noise_suppression=True)
        engine.start(echo.source, echo.sink)
        await engine.wait_ready(echo.source, echo.sink)
        consumer = asyncio.create_task(consume())
        for i in range(30):
            frames = (1, 2, 4, 8)[i % 4]
            before = base._generation_samples
            for _ in range(frames):
                engine.enqueue_output(engine.active_generation, bytes(960))
            engine.mark_turn_complete()
            await until(lambda: base._rendered == before + frames * 480 and not engine.speaking)
        result['complete_turns'] = 30
        print(json.dumps({'stage': '30 short/long turns passed'}), flush=True)

        acknowledgement_ms = []
        for _ in range(20):
            for _ in range(50):
                engine.enqueue_output(engine.active_generation, bytes(960))
            await asyncio.sleep(.025)
            start = time.monotonic()
            engine.handle_barge_in()
            target = engine.active_generation
            await until(lambda: base._applied_generation == target and not base._native_queued and not base._native_playing)
            acknowledgement_ms.append((time.monotonic() - start) * 1000)
        result['interruptions'] = 20
        result['interrupt_ack_max_ms'] = max(acknowledgement_ms)
        result['interrupt_ack_p95_ms'] = sorted(acknowledgement_ms)[18]
        assert result['interrupt_ack_max_ms'] < 250, result
        print(json.dumps({'stage': '20 interruptions passed', 'max_ack_ms': result['interrupt_ack_max_ms']}), flush=True)

        old = base._process
        old.kill()  # Only this probe's owned helper; never the service's process.
        try:
            await asyncio.wait_for(engine.monitor_health(), 3)
        except StreamLostError:
            pass
        else:
            raise AssertionError('helper failure was not detected')
        start = time.monotonic()
        await recover_audio(engine, echo.source, echo.sink, 1)
        assert old.poll() is not None and base._process.pid != old.pid
        assert base._aec_input_bound
        result['helper_recovery_ms'] = (time.monotonic() - start) * 1000
        print(json.dumps({'stage': 'owned helper crash/recovery passed', 'recovery_ms': result['helper_recovery_ms']}), flush=True)

        start_rss = rss_bytes(base._process.pid)
        start_starved = base._starved
        start = due = time.monotonic()
        frames = 0
        next_report = start + 30
        while time.monotonic() - start < duration:
            engine.enqueue_output(engine.active_generation, bytes(960))
            frames += 1
            due += .015 if frames % 2 else .025
            await asyncio.sleep(max(0, due - time.monotonic()))
            if time.monotonic() >= next_report:
                print(json.dumps({'stage': 'streaming', 'elapsed_s': round(time.monotonic() - start), 'starved_samples': base._starved}), flush=True)
                next_report += 30
            assert not base._failed, base._failed
        engine.mark_turn_complete()
        await until(lambda: base._rendered == frames * 480 and not engine.speaking)
        assert base._starved - start_starved == 0, 'playback starved during paced jitter run'
        result.update(duration_s=duration, paced_frames=frames, rendered_samples=base._rendered,
                      starved_samples_delta=base._starved-start_starved,
                      capture_frames=captured, capture_gap_max_ms=max(gaps, default=0)*1000,
                      callback_max_ns=base.callback_max_ns,
                      helper_rss_growth_bytes=rss_bytes(base._process.pid)-start_rss,
                      capture_dropped_frames=base.capture_dropped_frames,
                      completed=True)
        output.write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result), flush=True)
    finally:
        if consumer is not None:
            consumer.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await consumer
        await engine.aclose()
        await echo.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--duration', type=int, default=300)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if not 1 <= args.duration <= 3600:
        parser.error('duration must be 1..3600 seconds')
    asyncio.run(run(args.duration, args.output))
