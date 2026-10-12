"""Offline behavior tests. No microphone, cloud call, or running daemon needed."""
import asyncio
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace as NS


class StandaloneTests(unittest.TestCase):
    def test_cli_runs_from_an_unrelated_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(
                [sys.executable, str(Path(__file__).with_name('agent.py').resolve()), '--help'],
                cwd=directory, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('--microphone', result.stdout)


from google.genai import types
from agent import Playback, LiveVoice, live_config, supervise, stop_process, run
from skills import DesktopSkills

class Process:
    def __init__(self):
        self.returncode = None
        self.written = []
        self.stdin = self
        self.finished = asyncio.Event()

    def write(self, data):
        if self.returncode is not None:
            raise BrokenPipeError()
        self.written.append(data)

    async def drain(self):
        await asyncio.sleep(0)

    def close(self):
        pass

    def terminate(self):
        self.returncode = -15
        self.finished.set()

    def kill(self):
        self.returncode = -9
        self.finished.set()

    async def wait(self):
        await self.finished.wait()
        return self.returncode

class VoiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_interrupt_stops_output_discards_queued_audio_and_allows_new_turn(self):
        processes = []

        async def spawn(*args, **kwargs):
            p = Process()
            processes.append(p)
            return p

        player = Playback('test-sink')
        with patch('agent.asyncio.create_subprocess_exec', side_effect=spawn):
            worker = asyncio.create_task(player.run())
            try:
                player.enqueue(b'\x01\x00' * 240)
                for _ in range(20):
                    await asyncio.sleep(0)
                    if processes and processes[0].written:
                        break
                self.assertEqual(processes[0].written, [b'\x01\x00' * 240])
                player.enqueue(b'\x02\x00' * 240)
                await player.interrupt()
                self.assertIsNotNone(processes[0].returncode)
                self.assertTrue(player.queue.empty())
                player.enqueue(b'\x03\x00' * 240)
                for _ in range(30):
                    await asyncio.sleep(0)
                    if len(processes) > 1 and processes[1].written:
                        break
                self.assertEqual(processes[1].written, [b'\x03\x00' * 240])
            finally:
                worker.cancel()
                await asyncio.gather(worker, return_exceptions=True)
                await player.interrupt()

    async def test_interruption_during_player_creation_never_plays_stale_audio(self):
        entered, release = asyncio.Event(), asyncio.Event()
        process = Process()

        async def spawn(*args, **kwargs):
            entered.set()
            await release.wait()
            return process

        player = Playback('test-sink')
        with patch('agent.asyncio.create_subprocess_exec', side_effect=spawn):
            worker = asyncio.create_task(player.run())
            try:
                player.enqueue(b'\x01\x00' * 240)
                await asyncio.wait_for(entered.wait(), 1)
                await player.interrupt()
                release.set()
                for _ in range(20):
                    await asyncio.sleep(0)
                self.assertEqual(process.written, [])
                self.assertIsNotNone(process.returncode)
            finally:
                worker.cancel()
                await asyncio.gather(worker, return_exceptions=True)
                await player.interrupt()

    async def test_output_backlog_is_bounded_without_blocking_receive(self):
        player = Playback('sink')
        with self.assertRaises(BufferError):
            player.enqueue(bytes(48000 * 11))

    async def test_all_response_audio_parts_are_processed(self):
        from google.genai import types
        player = Playback('sink')
        voice = LiveVoice(player)
        event = types.LiveServerMessage(server_content=types.LiveServerContent(
            model_turn=types.Content(parts=[
                types.Part(inline_data=types.Blob(data=b'\x01\x00', mime_type='audio/pcm;rate=24000')),
                types.Part(inline_data=types.Blob(data=b'\x02\x00', mime_type='audio/pcm;rate=24000')),
            ])))
        await voice.handle(event)
        self.assertEqual(player.queue.get_nowait()[1], b'\x01\x00')
        self.assertEqual(player.queue.get_nowait()[1], b'\x02\x00')

    async def test_interruption_event_cannot_requeue_its_stale_audio(self):
        from google.genai import types
        player = Playback('sink')
        player.enqueue(b'\x01\x00')
        await LiveVoice(player).handle(types.LiveServerMessage(
            server_content=types.LiveServerContent(interrupted=True,
                model_turn=types.Content(parts=[types.Part(inline_data=types.Blob(
                    data=b'\x02\x00', mime_type='audio/pcm;rate=24000'))]))))
        self.assertTrue(player.queue.empty())

    async def test_input_keeps_sending_while_output_is_queued(self):
        player = Playback('sink')
        player.enqueue(b'\x01\x00')
        voice = LiveVoice(player)
        reader = asyncio.StreamReader()
        reader.feed_data(bytes(1280))
        reader.feed_eof()
        sent = []

        async def send(**kwargs):
            sent.append(kwargs['audio'])

        with self.assertRaises(EOFError):
            await voice.send_audio(NS(send_realtime_input=send), reader)
        self.assertEqual([len(blob.data) for blob in sent], [640, 640])
        self.assertTrue(all(blob.mime_type == 'audio/pcm;rate=16000' for blob in sent))
        self.assertFalse(player.queue.empty())

    async def test_receive_continues_across_turns_and_rejects_empty_closed_stream(self):
        from google.genai import types
        count = 0

        def receive():
            nonlocal count
            count += 1

            async def events():
                if count <= 2:
                    yield types.LiveServerMessage(server_content=types.LiveServerContent(
                        model_turn=types.Content(parts=[types.Part(inline_data=types.Blob(
                            data=b'\x01\x00', mime_type='audio/pcm;rate=24000'))]),
                        turn_complete=True))
            return events()

        player = Playback('sink')
        with self.assertRaises(ConnectionError):
            await LiveVoice(player).receive(NS(receive=receive))
        self.assertEqual(player.queue.qsize(), 2)

    async def test_worker_failure_cancels_other_audio_workers(self):
        stopped = asyncio.Event()

        async def pending():
            try:
                await asyncio.Future()
            finally:
                stopped.set()

        async def fail():
            await asyncio.sleep(0)
            raise EOFError('microphone closed')

        with self.assertRaises(EOFError):
            await supervise(pending(), fail())
        self.assertTrue(stopped.is_set())

    async def test_resume_handle_is_saved_only_when_server_marks_resumable(self):
        from google.genai import types
        voice = LiveVoice(Playback('sink'))
        await voice.handle(types.LiveServerMessage(session_resumption_update=
            types.LiveServerSessionResumptionUpdate(resumable=True, new_handle='handle-a')))
        self.assertEqual(voice.resume_handle, 'handle-a')
        await voice.handle(types.LiveServerMessage(session_resumption_update=
            types.LiveServerSessionResumptionUpdate(resumable=False)))
        self.assertIsNone(voice.resume_handle)

    async def test_live_config_validates_with_dynamic_desktop_skills(self):
        from google.genai import types
        config = types.LiveConnectConfig.model_validate(
            live_config('Aoede', 'saved', DesktopSkills()))
        self.assertTrue(config.tools)
        names = {item.name for item in config.tools[0].function_declarations}
        self.assertIn('open_application', names)
        self.assertEqual(config.session_resumption.handle, 'saved')
        self.assertFalse(config.realtime_input_config.automatic_activity_detection.disabled)
        self.assertEqual(config.realtime_input_config.activity_handling.value,
                         'START_OF_ACTIVITY_INTERRUPTS')

    async def test_live_config_can_disable_all_desktop_skills(self):
        from google.genai import types
        config = types.LiveConnectConfig.model_validate(live_config('Aoede'))
        self.assertFalse(config.tools)

    async def test_tool_call_runs_in_background_and_returns_matching_id(self):
        class Skills:
            async def execute(self, name, args):
                await asyncio.sleep(0)
                return {'name': name, 'args': args}

        class Session:
            def __init__(self):
                self.responses = []

            async def send_tool_response(self, *, function_responses):
                self.responses.append(function_responses)

        voice = LiveVoice(Playback('sink'), skills=Skills())
        session = Session()
        event = types.LiveServerMessage(tool_call=types.LiveServerToolCall(function_calls=[
            types.FunctionCall(id='call-1', name='test_skill', args={'value': 3})]))
        await voice.handle(event, session)
        for _ in range(20):
            await asyncio.sleep(0)
            if session.responses:
                break
        self.assertEqual(session.responses[0].id, 'call-1')
        self.assertEqual(session.responses[0].name, 'test_skill')
        self.assertEqual(session.responses[0].response['output']['args'], {'value': 3})
        await voice.cancel_tools()

    async def test_stopping_process_is_idempotent(self):
        process = Process()
        await stop_process(process)
        await stop_process(process)
        self.assertIsNotNone(process.returncode)

    async def test_failed_connections_have_a_retry_budget_and_release_echo_routes(self):
        attempts = []
        cleaned = []

        class Connection:
            async def __aenter__(self):
                attempts.append('attempt')
                raise ConnectionError('simulated network outage')

            async def __aexit__(self, *args):
                pass

        class Client:
            def __init__(self):
                self.live = self
                self.aio = self

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                cleaned.append('client')

            def connect(self, **kwargs):
                return Connection()

        class Echo:
            sink = 'test-sink'
            source = 'test-source'

            async def start(self, microphone):
                pass

            async def close(self):
                cleaned.append('echo')

        async def no_wait(delay):
            pass

        args = NS(model='test-model', voice='Aoede', transcripts=False,
                  microphone=None, retries=2)
        with patch('google.genai.Client', return_value=Client()), \
             patch('agent.EchoCancellation', return_value=Echo()), \
             patch('agent.asyncio.sleep', side_effect=no_wait), \
             self.assertLogs('gemini_voice', level='WARNING'):
            with self.assertRaisesRegex(RuntimeError, 'retry limit'):
                await run(args, 'fake-key')
        self.assertEqual(len(attempts), 3)
        self.assertEqual(cleaned, ['client', 'echo'])

    async def test_invalid_pcm_is_rejected_without_queuing_partial_audio(self):
        player = Playback('sink')
        with self.assertRaises(ValueError):
            player.enqueue(b'abc')
        self.assertTrue(player.queue.empty())

    async def test_cancellation_reaps_all_supervised_workers(self):
        started = asyncio.Event()
        ended = asyncio.Event()

        async def child():
            try:
                started.set()
                await asyncio.Future()
            finally:
                ended.set()

        task = asyncio.create_task(supervise(child()))
        await started.wait()
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertTrue(ended.is_set())


if __name__ == '__main__':
    unittest.main()
