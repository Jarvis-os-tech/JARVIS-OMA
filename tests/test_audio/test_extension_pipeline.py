"""Exercise extension boundaries through the real conversation/router APIs.

Neither backend starts a device or native subprocess in these tests.
"""
import asyncio
import contextlib
import struct
import time
from types import SimpleNamespace as NS
import unittest
from unittest.mock import AsyncMock, patch

from google.genai import types

from audio.downstream import DownstreamRouter
from audio.engine import NativeAudioEngine
from audio.extension import AudioExtensionRegistry, ExtendedAudioEngine
from audio.plugins.native_backend import AUDIO, CAPTURE, HEADER, NativeCompanionEngine
from core.agent import LiveVoice, recover_audio


INPUT = b'\x01\x00' * 320
OUTPUT = b'\x01\x00' * 480


class Processor:
    def __init__(self, incoming=lambda frame: frame, outgoing=lambda frame: frame):
        self.incoming, self.outgoing = incoming, outgoing
        self.input_frames, self.output_frames = [], []

    def process_input_frame(self, frame):
        self.input_frames.append(frame)
        return self.incoming(frame)

    def process_output_frame(self, frame):
        self.output_frames.append(frame)
        return self.outgoing(frame)


class Hook:
    def __init__(self):
        self.events = []

    def on_state_change(self, state):
        self.events.append(('state', state))

    def on_barge_in(self):
        self.events.append(('barge',))

    def on_turn_started(self):
        self.events.append(('start',))

    def on_turn_completed(self):
        self.events.append(('complete',))


def capture(engine, pcm=INPUT, *, age=0):
    if isinstance(engine, NativeCompanionEngine):
        engine._event(CAPTURE, 0, struct.pack('<Q', time.monotonic_ns() - int(age * 1e9)) + pcm)
    else:
        engine._safe_enqueue_input(pcm, captured_at=time.monotonic() - age)


def output_frames(engine):
    if isinstance(engine, NativeCompanionEngine):
        packets = [bytes(packet) for packet in engine._pending]
        return [(HEADER.unpack_from(packet)[2], packet[HEADER.size:])
                for packet in packets if HEADER.unpack_from(packet)[1] == AUDIO]
    result = []
    while not engine.c_output_queue.empty():
        result.append(engine.c_output_queue.get_nowait())
    return result


class ExtensionPipelineTests(unittest.IsolatedAsyncioTestCase):
    async def test_native_keeps_hearing_corrections_while_model_is_thinking(self):
        base = NativeCompanionEngine()
        voice = LiveVoice(ExtendedAudioEngine(base))
        voice._request_pending = True
        self.assertFalse(base.speaking)
        sent = await self.send_next(voice, base)
        self.assertEqual(sent[0].data, INPUT)
        self.assertEqual(voice.microphone_frames_sent, 1)

    async def test_native_frame_expiring_behind_send_lock_is_discarded(self):
        base = NativeCompanionEngine()
        voice = LiveVoice(ExtendedAudioEngine(base))
        sent = asyncio.Event()
        session = NS(send_realtime_input=AsyncMock(side_effect=lambda **kw: sent.set()))
        await voice.send_lock.acquire()
        capture(base)
        sender = asyncio.create_task(voice.send_audio(session))
        try:
            # Wait for dequeue while the sender is blocked on the held lock.
            for _ in range(10):
                await asyncio.sleep(0)
                if base.async_input_queue.last_capture_ns is not None:
                    break
            self.assertIsNotNone(base.async_input_queue.last_capture_ns)
            with patch('core.agent.time.monotonic_ns', return_value=base.async_input_queue.last_capture_ns + 200_000_000):
                voice.send_lock.release()
                for _ in range(5):
                    await asyncio.sleep(0)
            session.send_realtime_input.assert_not_awaited()
            self.assertEqual(voice.stale_microphone_frames_discarded, 1)
            capture(base)
            await asyncio.wait_for(sent.wait(), 1)
            session.send_realtime_input.assert_awaited_once()
        finally:
            if voice.send_lock.locked():
                voice.send_lock.release()
            sender.cancel()
            await asyncio.gather(sender, return_exceptions=True)

    async def send_next(self, voice, base, frames=(INPUT,)):
        sent, ready = [], asyncio.Event()

        async def send_realtime_input(*, audio):
            sent.append(audio)
            ready.set()

        sender = asyncio.create_task(voice.send_audio(NS(send_realtime_input=send_realtime_input)))
        try:
            for frame in frames:
                capture(base, frame)
            await asyncio.wait_for(ready.wait(), 1)
            return sent
        finally:
            sender.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await sender

    async def test_live_sender_processes_actual_cloud_frames_for_both_backends(self):
        for factory in (NativeAudioEngine, NativeCompanionEngine):
            with self.subTest(backend=factory.__name__):
                base = factory()
                wrapper = ExtendedAudioEngine(base)
                processor = Processor(incoming=lambda frame: b'\x02\x00' * 320)
                wrapper.register_processor(processor)
                sent = await self.send_next(LiveVoice(wrapper), base)
                self.assertEqual(sent[0].data, b'\x02\x00' * 320)
                self.assertEqual(sent[0].mime_type, 'audio/pcm;rate=16000')
                self.assertEqual(processor.input_frames, [INPUT])
                self.assertIs(wrapper.async_input_queue, base.async_input_queue)

    async def test_input_drop_then_transform_reaches_provider_once(self):
        base = NativeAudioEngine()
        wrapper = ExtendedAudioEngine(base)
        count = 0

        def process(frame):
            nonlocal count
            count += 1
            return None if count == 1 else b'\x02\x00' * 320

        wrapper.register_processor(Processor(incoming=process))
        voice = LiveVoice(wrapper)
        sent = await self.send_next(voice, base, (INPUT, INPUT))
        self.assertEqual([blob.data for blob in sent], [b'\x02\x00' * 320])
        self.assertEqual(voice.microphone_frames_sent, 1)

    async def test_standby_and_pending_request_bypass_input_processors(self):
        for gate in ('standby', 'request'):
            base = NativeAudioEngine()
            wrapper = ExtendedAudioEngine(base)
            processor = Processor()
            wrapper.register_processor(processor)
            voice = LiveVoice(wrapper)
            if gate == 'standby':
                voice.standby = NS(engaged=True)
            else:
                voice._request_pending = True
            send = AsyncMock()
            capture(base)
            sender = asyncio.create_task(voice.send_audio(NS(send_realtime_input=send)))
            try:
                async with asyncio.timeout(1):
                    while voice.stale_microphone_frames_discarded == 0:
                        await asyncio.sleep(0)
                self.assertEqual(processor.input_frames, [])
                send.assert_not_awaited()
            finally:
                sender.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await sender

    async def test_standby_engaged_while_waiting_for_send_lock_drops_frame(self):
        base = NativeAudioEngine()
        wrapper = ExtendedAudioEngine(base)
        processor = Processor()
        wrapper.register_processor(processor)
        voice = LiveVoice(wrapper)
        voice.standby = NS(engaged=False)
        send = AsyncMock()
        await voice.send_lock.acquire()
        capture(base)
        sender = asyncio.create_task(voice.send_audio(NS(send_realtime_input=send)))
        try:
            async with asyncio.timeout(1):
                while not base.async_input_queue.empty():
                    await asyncio.sleep(0)
            voice.standby.engaged = True
            voice.send_lock.release()
            async with asyncio.timeout(1):
                while voice.stale_microphone_frames_discarded == 0:
                    await asyncio.sleep(0)
            self.assertEqual(processor.input_frames, [])
            send.assert_not_awaited()
        finally:
            if voice.send_lock.locked():
                voice.send_lock.release()
            sender.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await sender

    async def test_muting_cannot_be_undone_by_an_input_processor(self):
        for factory in (NativeAudioEngine, NativeCompanionEngine):
            base = factory()
            wrapper = ExtendedAudioEngine(base)
            wrapper.register_processor(Processor(incoming=lambda frame: INPUT))
            wrapper.muted = True
            sent = await self.send_next(LiveVoice(wrapper), base)
            self.assertTrue(base.muted)
            self.assertEqual(sent[0].data, bytes(640))

    async def test_queue_expiration_and_raw_drain_do_not_process_stale_capture(self):
        for factory in (NativeAudioEngine, NativeCompanionEngine):
            base = factory()
            wrapper = ExtendedAudioEngine(base)
            processor = Processor()
            wrapper.register_processor(processor)
            voice = LiveVoice(wrapper)
            capture(base, age=10)
            capture(base)
            self.assertEqual(voice.discard_pending_microphone_audio(), 1)
            self.assertEqual(processor.input_frames, [])
            self.assertEqual(wrapper.async_input_queue.expired_frames, 1)
            self.assertTrue(wrapper.async_input_queue.empty())

    async def test_capture_capacity_is_not_replaced_by_unbounded_wrapper_queue(self):
        for factory, limit in ((NativeAudioEngine, 50), (NativeCompanionEngine, 8)):
            base = factory()
            wrapper = ExtendedAudioEngine(base)
            for _ in range(100):
                capture(base)
            self.assertLessEqual(wrapper.async_input_queue.qsize(), limit)

    async def test_router_processes_complete_frames_and_padded_tail_once(self):
        for factory in (NativeAudioEngine, NativeCompanionEngine):
            base = factory()
            wrapper = ExtendedAudioEngine(base)
            processor = Processor(outgoing=lambda frame: b'\x02\x00' * 480)
            wrapper.register_processor(processor)
            router = DownstreamRouter(wrapper)
            router.feed(OUTPUT[:200])
            self.assertEqual(processor.output_frames, [])
            router.feed(OUTPUT[200:] + b'\x01\x00')
            router.flush()
            self.assertEqual(len(processor.output_frames), 2)
            self.assertTrue(all(len(frame) == 960 for frame in processor.output_frames))
            self.assertEqual(output_frames(base), [(0, b'\x02\x00' * 480)] * 2)

    async def test_router_does_not_retag_frames_when_processor_interrupts(self):
        for factory in (NativeAudioEngine, NativeCompanionEngine):
            base = factory()
            wrapper = ExtendedAudioEngine(base)

            def interrupt(frame):
                wrapper.handle_barge_in()
                return frame

            processor = Processor(outgoing=interrupt)
            wrapper.register_processor(processor)
            DownstreamRouter(wrapper).feed(OUTPUT * 2)
            self.assertEqual(base.active_generation, 1)
            self.assertEqual(output_frames(base), [])
            self.assertEqual(processor.output_frames, [OUTPUT])

    async def test_processor_contract_failures_keep_previous_valid_pcm(self):
        def broken(frame):
            raise RuntimeError('extension failure')

        for bad in (lambda frame: b'', lambda frame: frame * 2,
                    lambda frame: bytearray(frame), lambda frame: 'invalid', broken):
            with self.subTest(processor=bad):
                base = NativeAudioEngine()
                wrapper = ExtendedAudioEngine(base)
                wrapper.register_processor(Processor(incoming=bad, outgoing=bad))
                wrapper.register_processor(Processor(
                    incoming=lambda frame: b'\x02\x00' * 320,
                    outgoing=lambda frame: b'\x02\x00' * 480))
                sent = await self.send_next(LiveVoice(wrapper), base)
                DownstreamRouter(wrapper).feed(OUTPUT)
                self.assertEqual(sent[0].data, b'\x02\x00' * 320)
                self.assertEqual(output_frames(base), [(0, b'\x02\x00' * 480)])
                self.assertEqual(wrapper.registry.processor_errors + wrapper.registry.invalid_results, 2)

    async def test_invalid_frames_never_reach_transport(self):
        base = NativeAudioEngine()
        wrapper = ExtendedAudioEngine(base)
        for frame in (b'', OUTPUT[:-1], bytearray(OUTPUT)):
            with self.assertRaises(ValueError):
                wrapper.enqueue_output(0, frame)
        for frame in (b'', INPUT[:-1], bytearray(INPUT)):
            self.assertIsNone(wrapper.process_input_frame(frame))
        self.assertEqual(output_frames(base), [])

    async def test_callback_assignment_composes_hooks_and_live_barge_handler(self):
        base = NativeAudioEngine()
        wrapper = ExtendedAudioEngine(base)
        hook = Hook()
        wrapper.register_hook(hook)
        voice = LiveVoice(wrapper)
        states = []
        wrapper.on_state_change = states.append
        wrapper.mark_turn_started()
        wrapper.mark_turn_started()
        base._set_state('speaking')
        await asyncio.sleep(0)
        wrapper.trigger_barge_in()
        # An already-scheduled base notification for the same generation is
        # harmless and must not duplicate extension interruption hooks.
        base.on_barge_in()
        await asyncio.sleep(0)
        self.assertTrue(voice._drop_interrupted_audio)
        self.assertIn('speaking', states)
        self.assertEqual(hook.events.count(('state', 'speaking')), 1)
        self.assertEqual(hook.events.count(('barge',)), 1)
        self.assertEqual(hook.events.count(('start',)), 1)
        wrapper.allow_barge_in = False
        self.assertFalse(base.allow_barge_in)

    async def test_live_provider_turn_hooks_are_not_duplicated_per_audio_chunk(self):
        wrapper = ExtendedAudioEngine(NativeAudioEngine())
        hook = Hook()
        wrapper.register_hook(hook)
        voice = LiveVoice(wrapper)
        for _ in range(2):
            await voice.handle(types.LiveServerMessage(server_content=types.LiveServerContent(
                model_turn=types.Content(parts=[types.Part(inline_data=types.Blob(
                    mime_type='audio/pcm;rate=24000', data=OUTPUT))]))))
        for _ in range(2):
            await voice.handle(types.LiveServerMessage(server_content=types.LiveServerContent(
                turn_complete=True)))
        self.assertEqual(hook.events.count(('start',)), 1)
        self.assertEqual(hook.events.count(('complete',)), 1)

    async def test_wrapped_native_recovery_awaits_cleanup_and_graph_ready(self):
        base = NativeCompanionEngine()
        wrapper = ExtendedAudioEngine(base)
        with patch.object(base, 'aclose', new_callable=AsyncMock) as close, \
             patch.object(base, 'start') as start, \
             patch.object(base, 'wait_ready', new_callable=AsyncMock) as ready:
            await recover_audio(wrapper, 'capture', 'playback', 0)
        close.assert_awaited_once()
        start.assert_called_once_with('capture', 'playback')
        ready.assert_awaited_once_with('capture', 'playback')


if __name__ == '__main__':
    unittest.main()
