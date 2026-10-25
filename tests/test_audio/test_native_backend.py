"""Native companion protocol and failure isolation, no desktop/cloud needed."""
import asyncio
from pathlib import Path
import struct
import subprocess
import time
import unittest
from unittest.mock import patch

from audio.engine import StreamLostError
from audio.plugins.native_backend import (
    NativeCompanionEngine, CaptureQueue, CAPTURE, STATS, AUDIO, FLUSH, graph_ready,
)


class NativeBackendTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = NativeCompanionEngine()

    async def test_gain_is_explicitly_requested_from_native_helper(self):
        for enabled in (False, True):
            with self.subTest(enabled=enabled):
                engine = NativeCompanionEngine(native_webrtc_gain=enabled)
                with patch.object(Path, 'is_file', return_value=True), \
                     patch('audio.plugins.native_backend.subprocess.Popen',
                           side_effect=OSError('test: no process opened')) as launch:
                    with self.assertRaises(OSError):
                        engine.start('cleaned-source', 'reference-sink')
                args = launch.call_args.args[0]
                self.assertEqual('--webrtc-gain' in args, enabled)
                self.assertEqual(args[1:4], ['cleaned-source', 'reference-sink', '80'])

    def test_gain_flag_rejects_ambiguous_values(self):
        for value in ('true', 1, None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                NativeCompanionEngine(native_webrtc_gain=value)

    async def test_capture_expiration_and_mute_before_native_ack(self):
        old = struct.pack('<Q', time.monotonic_ns() - 200_000_000) + b'\x01\0' * 320
        self.engine._event(CAPTURE, 0, old)
        self.assertTrue(self.engine.async_input_queue.empty())
        self.engine.muted = True
        fresh = struct.pack('<Q', time.monotonic_ns()) + b'\x01\0' * 320
        self.engine._event(CAPTURE, 0, fresh)
        self.assertEqual(await self.engine.async_input_queue.get(), bytes(640))

    async def test_capture_that_expires_while_waiting_is_never_replayed(self):
        queue = CaptureQueue()
        asyncio.Queue.put_nowait(queue, (time.monotonic_ns() - 200_000_000, bytes(640)))
        with self.assertRaises(asyncio.QueueEmpty):
            queue.get_nowait()
        self.assertEqual(queue.expired_frames, 1)

    async def test_generation_fences_output_and_flush_is_ordered(self):
        engine = self.engine
        engine.enqueue_output(0, bytes(960))
        engine.handle_barge_in()
        engine.enqueue_output(0, bytes(960))
        engine.enqueue_output(1, bytes(960))
        # No child in this unit test; explicitly exercise control framing too.
        engine._command(FLUSH, 1)
        self.assertEqual(len(engine._pending), 3)
        self.assertEqual(struct.unpack_from('<IIII', engine._pending[0])[1:3], (AUDIO, 0))
        self.assertEqual(struct.unpack_from('<IIII', engine._pending[1])[1:3], (AUDIO, 1))

    async def test_backlog_overflow_fails_explicitly_instead_of_truncating(self):
        engine = NativeCompanionEngine(queue_max_seconds=1)
        for _ in range(50):
            engine.enqueue_output(0, bytes(960))
        with self.assertRaisesRegex(StreamLostError, 'backlog'):
            engine.enqueue_output(0, bytes(960))

    async def test_stale_stats_do_not_complete_new_generation(self):
        engine = self.engine
        engine.handle_barge_in()
        engine.enqueue_output(1, bytes(960))
        engine._event(STATS, 0, struct.pack('<8Q', 320, 100000, 0, 0, 10, 0, 0, 0))
        self.assertTrue(engine.speaking)
        engine._event(STATS, 1, struct.pack('<8Q', 320, 480, 0, 0, 10, 0, 0, 1))
        self.assertFalse(engine.speaking)

    def test_graph_requires_correct_owner_direction_and_active_links(self):
        def node(i, name, client=None):
            props = {'node.name': name}
            if client:
                props['client.id'] = client
            return {'id': i, 'type': 'PipeWire:Interface:Node', 'info': {'props': props}}
        objects = [node(1, 'source'), node(2, 'sink'), node(3, 'capture', 5), node(4, 'playback', 5),
                   {'id': 5, 'type': 'PipeWire:Interface:Client',
                    'info': {'props': {'application.process.id': '123'}}}]
        def link(i, out, into):
            return {'id': i, 'type': 'PipeWire:Interface:Link', 'info': {
                'output-node-id': out, 'input-node-id': into, 'state': 'active'}}
        objects += [link(6, 1, 3), link(7, 4, 2)]
        self.assertTrue(graph_ready(objects, (3, 4), 123, 'source', 'sink'))
        self.assertFalse(graph_ready(objects, (3, 4), 456, 'source', 'sink'))
        objects[-1]['info']['state'] = 'paused'
        self.assertFalse(graph_ready(objects, (3, 4), 123, 'source', 'sink'))

    def test_compiled_native_rings_flush_and_partial_turns(self):
        root = Path(__file__).resolve().parents[2]
        subprocess.run(['make', '-C', str(root / 'audio/plugins/native'), 'check'],
                       check=True, capture_output=True, timeout=30)
