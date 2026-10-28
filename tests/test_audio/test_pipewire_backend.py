"""Offline ownership, interruption and routing contracts for reference transport."""
import asyncio
import json
import unittest
from unittest.mock import AsyncMock, patch

from audio.engine import StreamLostError
from audio.plugins.pipewire_backend import PipeWireProcessEngine, verify_route
from core.config import AudioConfig
from core.agent import LiveVoice


class Input:
    def __init__(self):
        self.written = []
        self.closed = False

    def write(self, data):
        self.written.append(data)

    async def drain(self):
        await asyncio.sleep(0)

    def close(self):
        self.closed = True


class Process:
    def __init__(self, pid):
        self.pid, self.returncode = pid, None
        self.stdin = Input()
        self.stdout = asyncio.StreamReader()

    def terminate(self):
        self.returncode = -15

    def kill(self):
        self.returncode = -9

    async def wait(self):
        return self.returncode


async def until(predicate):
    async with asyncio.timeout(1):
        while not predicate():
            await asyncio.sleep(.001)


class PipeWireTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = PipeWireProcessEngine()
        self.processes = []
        self.commands = []
        self.spawn_patch = patch('audio.plugins.pipewire_backend.asyncio.create_subprocess_exec',
                                 side_effect=self.spawn)
        self.route_patch = patch('audio.plugins.pipewire_backend.verify_route', new_callable=AsyncMock)
        self.spawn_patch.start()
        self.route_patch.start()

    async def spawn(self, *args, **kwargs):
        process = Process(100 + len(self.processes))
        if args[0] == 'pw-record':
            process.stdout.feed_data(b'\x10\x00' * 320)
        self.processes.append(process)
        self.commands.append((args, kwargs))
        return process

    async def start(self):
        self.engine.start('private-source', 'private-sink')
        await self.engine.wait_ready('private-source', 'private-sink')

    async def asyncTearDown(self):
        await self.engine.aclose()
        self.spawn_patch.stop()
        self.route_patch.stop()

    async def test_capture_format_and_private_environment(self):
        with patch.dict('os.environ', {'GEMINI_API_KEY': 'secret', 'PIPEWIRE_QUANTUM': '1024'}):
            await self.start()
        self.assertEqual(await self.engine.async_input_queue.get(), b'\x10\x00' * 320)
        args, kwargs = self.commands[0]
        self.assertIn('private-source', args)
        self.assertNotIn('GEMINI_API_KEY', kwargs['env'])
        self.assertNotIn('PIPEWIRE_QUANTUM', kwargs['env'])
        self.assertTrue(self.engine._aec_input_bound)

    async def test_playback_order_and_persistent_process(self):
        await self.start()
        frames = [bytes([n, 0]) * 480 for n in (1, 2, 3)]
        for frame in frames:
            self.engine.enqueue_output(0, frame)
        self.engine.mark_turn_complete()
        await until(lambda: self.engine._output is not None and len(self.engine._output.stdin.written) == 3)
        self.assertEqual(self.engine._output.stdin.written, frames)
        self.assertIsNone(self.engine._output.returncode)
        self.assertIn('private-sink', self.commands[1][0])

    async def test_interruption_during_spawn_never_plays_old_generation(self):
        await self.start()
        entered, release = asyncio.Event(), asyncio.Event()
        original_spawn = self.spawn
        async def delayed(*args, **kwargs):
            if args[0] == 'pw-play' and not entered.is_set():
                entered.set()
                await release.wait()
            return await original_spawn(*args, **kwargs)
        with patch('audio.plugins.pipewire_backend.asyncio.create_subprocess_exec', side_effect=delayed):
            old, new = b'\x01\x00' * 480, b'\x02\x00' * 480
            self.engine.enqueue_output(0, old)
            await asyncio.wait_for(entered.wait(), 1)
            self.engine.handle_barge_in()
            self.engine.enqueue_output(1, new)
            release.set()
            await until(lambda: any(new in p.stdin.written for p in self.processes))
        self.assertFalse(any(old in p.stdin.written for p in self.processes))
        self.assertEqual(self.processes[1].returncode, -15)

    async def test_repeated_mute_does_not_interrupt_again(self):
        await self.start()
        self.engine.set_muted(True)
        generation = self.engine.active_generation
        self.engine.set_muted(True)
        self.assertEqual(self.engine.active_generation, generation)
        self.engine._capture.stdout.feed_data(b'\x20\x00' * 320)
        self.assertEqual(await asyncio.wait_for(self.engine.async_input_queue.get(), 1), bytes(640))
        self.engine.enqueue_output(generation, b'\x01\x00' * 480)
        self.assertTrue(self.engine._playback_queue.empty())

    async def test_capture_failure_reaches_health_supervisor(self):
        await self.start()
        self.engine._capture.stdout.feed_eof()
        await until(lambda: self.engine._failed is not None)
        with self.assertRaises(StreamLostError):
            await self.engine.monitor_health()

    async def test_shutdown_reaps_capture_and_playback(self):
        await self.start()
        self.engine.enqueue_output(0, bytes(960))
        await until(lambda: self.engine._output is not None)
        owned = list(self.processes)
        await self.engine.aclose()
        self.assertTrue(all(p.returncode is not None for p in owned))
        self.assertEqual(self.engine._tasks, [])

    async def test_bounded_capture_evicts_old_frames(self):
        await self.start()
        self.engine._capture.stdout.feed_data(bytes(640 * 20))
        await until(lambda: self.engine.capture_sample_clock >= 320 * 21)
        self.assertLessEqual(self.engine.async_input_queue.qsize(), 8)
        self.assertGreater(self.engine.capture_dropped_frames, 0)


class RouteTests(unittest.IsolatedAsyncioTestCase):
    async def test_explicit_voice_check_works_without_skills(self):
        engine = PipeWireProcessEngine()
        voice = LiveVoice(engine)
        session = type('Session', (), {'send_client_content': AsyncMock()})()
        worker = asyncio.create_task(voice.send_voice_diagnostics(session))
        try:
            voice._diagnostic_voice_requested.set()
            await until(lambda: session.send_client_content.await_count == 1)
            prompt = session.send_client_content.call_args.kwargs['turns'].parts[0].text
            self.assertEqual(prompt, 'Diagnostic voice check. Say exactly: Jarvis is listening.')
            self.assertEqual(voice.recognized_input_events, 0)
            engine.set_muted(True)
            voice._diagnostic_voice_requested.set()
            await asyncio.sleep(.01)
            self.assertEqual(session.send_client_content.await_count, 1)
        finally:
            worker.cancel()
            await asyncio.gather(worker, return_exceptions=True)
            await engine.aclose()

    async def test_exact_graph_link_required(self):
        nodes = [
            {'id': 1, 'type': 'PipeWire:Interface:Node', 'info': {'props': {'node.name': 'private'}}},
            {'id': 3, 'type': 'PipeWire:Interface:Client', 'info': {'props': {'application.process.id': 123}}},
            {'id': 2, 'type': 'PipeWire:Interface:Node', 'info': {'props': {'client.id': 3}}},
            {'type': 'PipeWire:Interface:Link', 'info': {'props': {'link.output.node': 1, 'link.input.node': 2}}},
        ]
        proc = Process(999)
        proc.communicate = AsyncMock(return_value=(json.dumps(nodes).encode(), b''))
        with patch('audio.plugins.pipewire_backend.asyncio.create_subprocess_exec', return_value=proc):
            await verify_route(123, 'private', capture=True)
            with patch('audio.plugins.pipewire_backend.asyncio.sleep', new_callable=AsyncMock):
                with self.assertRaises(StreamLostError):
                    await verify_route(124, 'private', capture=True)

    def test_supported_config_and_invalid_format(self):
        AudioConfig(backend='pipewire').validate()
        with self.assertRaises(ValueError):
            AudioConfig(backend='pipewire', input_sample_rate=24000).validate()
