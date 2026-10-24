"""Short local-only native audio smoke test. No speech sent to any provider.

Run: .venv/bin/python -m audio.plugins.native_probe
Creates and cleans up its own AEC module; plays silence, not a test tone.
"""
import asyncio
import json
import argparse

from audio.echo_cancel import EchoCancellation
from audio.plugins.native_backend import NativeCompanionEngine


async def probe(duration=0):
    echo = EchoCancellation()
    engine = NativeCompanionEngine()
    try:
        await echo.start(noise_suppression=True)
        engine.start(echo.source, echo.sink)
        await engine.wait_ready(echo.source, echo.sink)
        async with asyncio.timeout(3):
            frame = await engine.async_input_queue.get()
        assert len(frame) == 640, 'unexpected microphone format'
        # Silence is enough to test the render ring and short-turn priming.
        for _ in range(4):
            engine.enqueue_output(engine.active_generation, bytes(960))
        engine.mark_turn_complete()
        await asyncio.sleep(.5)
        assert engine._rendered == 1920, 'native render did not consume all test samples'
        assert not engine.speaking, 'native render did not drain'
        # FLUSH followed immediately by PCM exercises the native epoch ack.
        for _ in range(5):
            engine.handle_barge_in()
            for _ in range(4):
                engine.enqueue_output(engine.active_generation, bytes(960))
            engine.mark_turn_complete()
            await asyncio.sleep(.2)
            assert engine._rendered == 1920 and not engine.speaking, 'generation transition failed'
        # Keep future silence available while exercising sustained native I/O.
        if duration:
            for _ in range(15):
                engine.enqueue_output(engine.active_generation, bytes(960))
        deadline = asyncio.get_running_loop().time() + duration
        while asyncio.get_running_loop().time() < deadline:
            for _ in range(10):
                engine.enqueue_output(engine.active_generation, bytes(960))
            await asyncio.sleep(.2)
        engine.mark_turn_complete()
        await asyncio.sleep(.3)
        assert not engine._failed, engine._failed
        print(json.dumps({'ready': True, 'links_verified': engine._aec_input_bound,
                          'capture_frame_bytes': len(frame), 'rendered_samples': engine._rendered,
                          'callback_max_ns': engine.callback_max_ns,
                          'starved_samples': engine._starved}))
    finally:
        await engine.aclose()
        await echo.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--duration', type=float, default=0, help='Additional silent streaming seconds')
    args = parser.parse_args()
    if not 0 <= args.duration <= 300:
        parser.error('duration must be between 0 and 300 seconds')
    asyncio.run(probe(args.duration))
