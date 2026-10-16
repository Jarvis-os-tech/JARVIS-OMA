"""Offline behavior tests. No microphone, cloud call, or running daemon needed."""
import asyncio
import json
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
            agent_path = Path(__file__).resolve().parents[2] / 'agent.py'
            result = subprocess.run(
                [sys.executable, str(agent_path.resolve()), '--help'],
                cwd=directory, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('--microphone', result.stdout)
        self.assertIn('--config', result.stdout)
        self.assertIn('--agent-name', result.stdout)


from google.genai import types
from agent import (
    LiveVoice, live_config, supervise, run,
    NativeAudioEngine, DownstreamRouter, RenewConnection,
)
from skills import DesktopSkills


def native_engine():
    """Construct the native engine without opening real audio devices."""
    return NativeAudioEngine(loop=asyncio.get_running_loop())

class VoiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_background_notice_waits_for_reply_and_playback(self):
        engine = native_engine()
        voice = LiveVoice(engine)
        sent = []

        async def send_client_content(**kwargs):
            sent.append(kwargs)

        sender = asyncio.create_task(voice.send_notifications(NS(send_client_content=send_client_content)))
        try:
            await voice.handle(types.LiveServerMessage(server_content=types.LiveServerContent(
                model_turn=types.Content(parts=[types.Part(text='reply in progress')]))))
            voice._queue_notice('background finished')
            voice._queue_notice('another update')
            await asyncio.sleep(.02)
            self.assertEqual(sent, [])
            engine.speaking = True
            await voice.handle(types.LiveServerMessage(server_content=types.LiveServerContent(
                turn_complete=True)))
            await asyncio.sleep(.02)
            self.assertEqual(sent, [])
            engine.speaking = False
            await asyncio.wait_for(voice._notice_event.wait(), .2)
            for _ in range(20):
                if sent:
                    break
                await asyncio.sleep(.01)
            self.assertEqual(len(sent), 1)
            self.assertEqual(sent[0]['turns'].parts[0].text, 'background finished')
            await asyncio.sleep(.02)
            self.assertEqual(len(sent), 1)
            await voice.handle(types.LiveServerMessage(server_content=types.LiveServerContent(
                turn_complete=True)))
            for _ in range(20):
                if len(sent) == 2:
                    break
                await asyncio.sleep(.01)
            self.assertEqual(sent[1]['turns'].parts[0].text, 'another update')
            self.assertFalse(voice._notices)
        finally:
            sender.cancel()
            await asyncio.gather(sender, return_exceptions=True)

    async def test_all_response_audio_parts_are_processed(self):
        from google.genai import types
        engine = native_engine()
        voice = LiveVoice(engine)
        event = types.LiveServerMessage(server_content=types.LiveServerContent(
            model_turn=types.Content(parts=[
                types.Part(inline_data=types.Blob(data=b'\x01\x00', mime_type='audio/pcm;rate=24000')),
                types.Part(inline_data=types.Blob(data=b'\x02\x00', mime_type='audio/pcm;rate=24000')),
            ])))
        await voice.handle(event)
        voice.router.flush()
        self.assertEqual(engine.c_output_queue.get_nowait()[1][:4], b'\x01\x00\x02\x00')

    async def test_interruption_event_cannot_requeue_its_stale_audio(self):
        from google.genai import types
        engine = native_engine()
        engine.enqueue_output(0, b'\x01\x00')
        await LiveVoice(engine).handle(types.LiveServerMessage(
            server_content=types.LiveServerContent(interrupted=True,
                model_turn=types.Content(parts=[types.Part(inline_data=types.Blob(
                    data=b'\x02\x00', mime_type='audio/pcm;rate=24000'))]))))
        self.assertTrue(engine.c_output_queue.empty())

    async def test_input_keeps_sending_while_output_is_queued(self):
        engine = native_engine()
        engine.enqueue_output(0, b'\x01\x00')
        voice = LiveVoice(engine)
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
        self.assertFalse(engine.c_output_queue.empty())

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

        player = native_engine()
        with self.assertRaises(ConnectionError):
            await LiveVoice(player).receive(NS(receive=receive))
        self.assertEqual(player.c_output_queue.qsize(), 2)

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
        voice = LiveVoice(native_engine())
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
        self.assertIn('read_file', names)
        self.assertIn('internet_search', names)
        self.assertEqual(len(config.tools), 1)
        self.assertEqual(config.session_resumption.handle, 'saved')
        self.assertFalse(config.realtime_input_config.automatic_activity_detection.disabled)
        self.assertEqual(config.realtime_input_config.activity_handling.value,
                         'START_OF_ACTIVITY_INTERRUPTS')

    async def test_live_config_can_disable_all_desktop_skills(self):
        from google.genai import types
        config = types.LiveConnectConfig.model_validate(live_config('Aoede'))
        self.assertFalse(config.tools)

    async def test_live_config_custom_agent_name_and_instruction(self):
        from config import Config, AgentConfig
        cfg = Config(agent=AgentConfig(name='Friday'))
        res = live_config('Aoede', skills=DesktopSkills(), config=cfg)
        self.assertIn('You are Friday', res['system_instruction'])

        custom_instruction = 'You are a pirate assistant. Talk like a pirate.'
        cfg_custom = Config(agent=AgentConfig(name='Blackbeard', system_instruction=custom_instruction))
        res_custom = live_config('Aoede', skills=DesktopSkills(), config=cfg_custom)
        self.assertTrue(res_custom['system_instruction'].startswith(custom_instruction))
        self.assertIn('JARVIS has persistent memory', res_custom['system_instruction'])

    async def test_live_config_includes_filesystem_autonomy(self):
        from config import Config, FilesystemConfig
        cfg_auto = Config(filesystem=FilesystemConfig(autonomous=True))
        res_auto = live_config('Aoede', skills=DesktopSkills(), config=cfg_auto)
        self.assertIn('full autonomous access', res_auto['system_instruction'])

        cfg_non_auto = Config(filesystem=FilesystemConfig(autonomous=False))
        res_non_auto = live_config('Aoede', skills=DesktopSkills(), config=cfg_non_auto)
        self.assertIn('cannot run arbitrary shell commands', res_non_auto['system_instruction'])
        self.assertNotIn('full autonomous access', res_non_auto['system_instruction'])

    async def test_live_instruction_routes_current_questions_to_search_and_files_to_tools(self):
        instruction = live_config('Aoede', skills=DesktopSkills())['system_instruction']
        self.assertIn('Use internet_search for questions requiring current internet information', instruction)
        self.assertIn('use list_files or search_files to locate', instruction)
        self.assertIn('do not claim you cannot browse', instruction)

    async def test_live_config_custom_vad_settings(self):
        from config import Config, VADConfig
        vad = VADConfig(start_sensitivity='START_SENSITIVITY_LOW', prefix_padding_ms=300)
        cfg = Config(vad=vad)
        res = live_config('Aoede', skills=DesktopSkills(), config=cfg)
        self.assertEqual(
            res['realtime_input_config']['automatic_activity_detection']['start_of_speech_sensitivity'],
            'START_SENSITIVITY_LOW')
        self.assertEqual(
            res['realtime_input_config']['automatic_activity_detection']['prefix_padding_ms'],
            300)

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

        voice = LiveVoice(native_engine(), skills=Skills())
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

    async def test_greet_sends_client_content_prompt(self):
        class Session:
            def __init__(self):
                self.contents = []

            async def send_client_content(self, *, turns, turn_complete=True):
                self.contents.append((turns, turn_complete))

        voice = LiveVoice(native_engine())
        session = Session()
        await voice.greet(session)
        self.assertEqual(len(session.contents), 1)
        turns, turn_complete = session.contents[0]
        self.assertTrue(turn_complete)
        self.assertIn('Jarvis', turns.parts[0].text)
        self.assertTrue(voice.has_greeted)

        # Subsequent call does not send again
        await voice.greet(session)
        self.assertEqual(len(session.contents), 1)

    async def test_greet_disabled_by_config(self):
        from config import Config, AgentConfig

        class Session:
            def __init__(self):
                self.contents = []

            async def send_client_content(self, *, turns, turn_complete=True):
                self.contents.append((turns, turn_complete))

        cfg = Config(agent=AgentConfig(greet_on_activation=False))
        voice = LiveVoice(native_engine(), config=cfg)
        session = Session()
        await voice.greet(session)
        self.assertEqual(len(session.contents), 0)
        self.assertFalse(voice.has_greeted)

    async def test_greet_custom_prompt_and_language(self):
        from config import Config, AgentConfig

        class Session:
            def __init__(self):
                self.contents = []

            async def send_client_content(self, *, turns, turn_complete=True):
                self.contents.append((turns, turn_complete))

        cfg = Config(agent=AgentConfig(name='Friday', greeting_prompt='Wake up Friday!'))
        voice = LiveVoice(native_engine(), config=cfg)
        session = Session()
        await voice.greet(session)
        self.assertEqual(len(session.contents), 1)
        self.assertEqual(session.contents[0][0].parts[0].text, 'Wake up Friday!')

        # Non-english language default prompt
        cfg_lang = Config(agent=AgentConfig(name='Jarvis', language='hi'))
        voice_lang = LiveVoice(native_engine(), config=cfg_lang)
        session_lang = Session()
        await voice_lang.greet(session_lang)
        self.assertEqual(len(session_lang.contents), 1)
        self.assertIn('Hindi', session_lang.contents[0][0].parts[0].text)

    async def test_greet_handles_send_error_gracefully(self):
        class FailingSession:
            async def send_client_content(self, *, turns, turn_complete=True):
                raise ConnectionError('websocket drop')

        voice = LiveVoice(native_engine())
        # Should not raise exception
        await voice.greet(FailingSession())
        self.assertTrue(voice.has_greeted)

    async def test_transcript_streaming_does_not_cut_words(self):
        import io
        from contextlib import redirect_stdout
        from google.genai import types

        voice = LiveVoice(native_engine(), transcripts=True)
        buf = io.StringIO()
        with redirect_stdout(buf):
            # First turn: Gemini streaming 3 fragments
            await voice.handle(types.LiveServerMessage(server_content=types.LiveServerContent(
                output_transcription=types.Transcription(text='Hello! '))))
            await voice.handle(types.LiveServerMessage(server_content=types.LiveServerContent(
                output_transcription=types.Transcription(text='Good morning. '))))
            await voice.handle(types.LiveServerMessage(server_content=types.LiveServerContent(
                output_transcription=types.Transcription(text='Jarvis online.'),
                turn_complete=True)))

            # Second turn: User input
            await voice.handle(types.LiveServerMessage(server_content=types.LiveServerContent(
                input_transcription=types.Transcription(text='What is the time?'),
                turn_complete=True)))

        output = buf.getvalue().splitlines()
        self.assertEqual(len(output), 2)
        self.assertEqual(output[0], 'Gemini: Hello! Good morning. Jarvis online.')
        self.assertEqual(output[1], 'You: What is the time?')

    async def test_audio_diagnostic_trace_correlates_transcripts_and_turn_end(self):
        from google.genai import types
        from core.config import Config

        config = Config()
        config.audio.diagnostic_transcripts = True
        voice = LiveVoice(native_engine(), config=config)
        event = types.LiveServerMessage(server_content=types.LiveServerContent(
            input_transcription=types.Transcription(text='I heard a crackle'),
            output_transcription=types.Transcription(text='Hello there'),
            turn_complete=True))
        with self.assertLogs('gemini_voice', level='INFO') as captured:
            await voice.handle(event)
        trace = '\n'.join(captured.output)
        self.assertIn("AUDIO_TRACE transcript you: 'I heard a crackle'", trace)
        self.assertIn("AUDIO_TRACE transcript jarvis: 'Hello there'", trace)
        self.assertIn('AUDIO_TRACE server completed response', trace)

    async def test_live_config_allows_detailed_analysis_by_default(self):
        res = live_config('Aoede', skills=DesktopSkills())
        self.assertIn('complete explanation', res['system_instruction'])
        self.assertNotIn('CRITICAL RULE', res['system_instruction'])

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

            async def start(self, microphone, **kwargs):
                pass

            async def close(self):
                cleaned.append('echo')

        async def no_wait(delay):
            pass

        class MockAudioEngine:
            def __init__(self, *args, **kwargs):
                self.muted = False
                self.output_frame_bytes = 960
                self.async_input_queue = asyncio.Queue()
                self.c_output_queue = __import__('queue').SimpleQueue()
                self.on_barge_in = None

            def start(self, source, sink):
                pass

            def handle_barge_in(self):
                pass

            def set_muted(self, state):
                self.muted = state

            async def stop_speaking(self):
                pass

            async def monitor_health(self):
                await asyncio.sleep(999999)

            def terminate(self):
                cleaned.append('audio_engine')

        args = NS(model='test-model', voice='Aoede', transcripts=False, no_ipc=True,
                  microphone=None, retries=2)
        with tempfile.TemporaryDirectory() as directory, \
             patch('google.genai.Client', return_value=Client()), \
             patch('agent.EchoCancellation', return_value=Echo()), \
             patch('agent.NativeAudioEngine', MockAudioEngine), \
             patch('agent.asyncio.sleep', side_effect=no_wait), \
             self.assertLogs('gemini_voice', level='WARNING'):
            from config import Config
            configuration = Config()
            configuration.memory.path = directory
            with self.assertRaisesRegex(RuntimeError, 'retry limit'):
                await run(args, 'fake-key', config=configuration)
        self.assertEqual(len(attempts), 3)
        self.assertEqual(cleaned, ['client', 'audio_engine', 'echo'])

    async def test_invalid_pcm_is_rejected_without_queuing_partial_audio(self):
        player = native_engine()
        with self.assertRaises(ValueError):
            DownstreamRouter(player).feed(b'abc')
        self.assertTrue(player.c_output_queue.empty())

    async def test_livevoice_with_native_engine_routes_audio_and_handles_barge_in(self):
        engine = native_engine()

        voice = LiveVoice(engine)
        self.assertIsNotNone(voice.engine)
        self.assertIsNotNone(voice.router)

        # Receive 960 bytes of audio
        event = NS(
            session_resumption_update=None,
            go_away=None,
            tool_call_cancellation=None,
            tool_call=None,
            server_content=NS(
                interrupted=False,
                model_turn=NS(parts=[NS(inline_data=NS(data=b'\x01\x00' * 480, mime_type='audio/pcm;rate=24000'))]),
                turn_complete=True,
                input_transcription=None,
                output_transcription=None,
            ),
        )
        await voice.handle(event)
        self.assertEqual(engine.c_output_queue.qsize(), 1)
        gen, chunk = engine.c_output_queue.get_nowait()
        self.assertEqual(gen, 0)
        self.assertEqual(chunk, b'\x01\x00' * 480)

        # Barge-in event
        interrupt_event = NS(
            session_resumption_update=None,
            go_away=None,
            tool_call_cancellation=None,
            tool_call=None,
            server_content=NS(
                interrupted=True,
                model_turn=None,
                turn_complete=False,
                input_transcription=None,
                output_transcription=None,
            ),
        )
        await voice.handle(interrupt_event)
        self.assertEqual(engine.active_generation, 1)
        self.assertEqual(len(voice.router.residual), 0)

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
    async def test_tool_call_fast_path_inline(self):
        class FastSkills:
            async def execute(self, name, args):
                return {'result': 'fast_done'}

        class Session:
            def __init__(self):
                self.responses = []
                self.contents = []

            async def send_tool_response(self, *, function_responses):
                self.responses.append(function_responses)

            async def send_client_content(self, *, turns, turn_complete=True):
                self.contents.append((turns, turn_complete))

        voice = LiveVoice(native_engine(), skills=FastSkills())
        session = Session()
        call = types.FunctionCall(id='fast-call-1', name='quick_action', args={'k': 'v'})
        event = types.LiveServerMessage(tool_call=types.LiveServerToolCall(function_calls=[call]))

        await voice.handle(event, session)
        for _ in range(20):
            await asyncio.sleep(0.01)
            if session.responses:
                break

        self.assertEqual(len(session.responses), 1)
        resp = session.responses[0]
        self.assertEqual(resp.id, 'fast-call-1')
        self.assertEqual(resp.response['output'], {'result': 'fast_done'})
        self.assertEqual(len(session.contents), 0)
        await voice.cancel_tools()

    async def test_slow_tool_result_returns_in_original_turn(self):
        finish_event = asyncio.Event()

        class SlowSkills:
            async def execute(self, name, args):
                await asyncio.sleep(0.200)
                finish_event.set()
                return {'data': 'slow_result'}

        class Session:
            def __init__(self):
                self.responses = []
                self.contents = []

            async def send_tool_response(self, *, function_responses):
                self.responses.append(function_responses)

            async def send_client_content(self, *, turns, turn_complete=True):
                self.contents.append((turns, turn_complete))

        voice = LiveVoice(native_engine(), skills=SlowSkills())
        session = Session()
        call = types.FunctionCall(id='slow-call-1', name='heavy_search', args={'q': 'query'})
        event = types.LiveServerMessage(tool_call=types.LiveServerToolCall(function_calls=[call]))

        await voice.handle(event, session)

        # A lookup crossing the old 150 ms gate still returns its actual data.
        for _ in range(25):
            await asyncio.sleep(0.02)
            if session.responses:
                break

        self.assertEqual(len(session.responses), 1)
        response = session.responses[0]
        self.assertEqual(response.id, 'slow-call-1')
        self.assertEqual(response.response, {'output': {'data': 'slow_result'}})
        await asyncio.wait_for(finish_event.wait(), timeout=1.0)
        self.assertEqual(session.contents, [])
        self.assertEqual(len(voice._notices), 0)
        await voice.cancel_tools()

    async def test_screen_inspection_returns_ocr_with_tool_result(self):
        class ScreenSkills:
            async def execute(self, name, args):
                return {'status': 'inspected', 'text_content': 'Editor open'}

        responses = []

        async def send_tool_response(*, function_responses):
            responses.append(function_responses)

        voice = LiveVoice(native_engine(), skills=ScreenSkills())
        session = NS(send_tool_response=send_tool_response)
        call = types.FunctionCall(id='screen-call-1', name='inspect_screen', args={})
        await voice.handle(types.LiveServerMessage(tool_call=types.LiveServerToolCall(
            function_calls=[call])), session)
        for _ in range(20):
            if responses:
                break
            await asyncio.sleep(.01)
        self.assertEqual(len(responses), 1)
        self.assertEqual(responses[0].response['output']['text_content'], 'Editor open')
        self.assertEqual(responses[0].response['output']['visual_input'], 'ocr_only')
        await voice.cancel_tools()

    async def test_screen_inspection_sends_frame_before_ocr_response(self):
        from google.genai.live import AsyncSession

        with tempfile.TemporaryDirectory() as runtime_dir:
            screen_dir = Path(runtime_dir) / 'jarvis_screen'
            screen_dir.mkdir()
            image = screen_dir / 'capture.jpg'
            image.write_bytes(b'\xff\xd8visual-frame\xff\xd9')

            class ScreenSkills:
                async def execute(self, name, args):
                    return {'status': 'inspected', 'text_content': 'Settings window',
                            'screenshot_path': str(image)}

            messages = []

            async def send(payload):
                messages.append(json.loads(payload))

            session = AsyncSession(NS(vertexai=False), NS(send=send))
            voice = LiveVoice(native_engine(), skills=ScreenSkills())
            call = types.FunctionCall(id='screen-frame-1', name='inspect_screen', args={})
            with patch.dict('os.environ', {'XDG_RUNTIME_DIR': runtime_dir}):
                await voice.handle(types.LiveServerMessage(tool_call=types.LiveServerToolCall(
                    function_calls=[call])), session)
                for _ in range(25):
                    if len(messages) == 2:
                        break
                    await asyncio.sleep(.01)

            self.assertEqual(len(messages), 2)
            self.assertIn('realtime_input', messages[0])
            self.assertIn('tool_response', messages[1])
            self.assertNotIn('client_content', messages[0])
            response = messages[1]['tool_response']['functionResponses'][0]['response']
            self.assertEqual(response['output']['visual_input'], 'frame_submitted')
            self.assertEqual(response['output']['text_content'], 'Settings window')
            with patch.dict('os.environ', {'XDG_RUNTIME_DIR': runtime_dir}):
                second = types.FunctionCall(id='screen-frame-1b', name='inspect_screen', args={})
                await voice.handle(types.LiveServerMessage(tool_call=types.LiveServerToolCall(
                    function_calls=[second])), session)
                for _ in range(25):
                    if len(messages) == 3:
                        break
                    await asyncio.sleep(.01)
            self.assertEqual(len(messages), 3)
            second_result = messages[2]['tool_response']['functionResponses'][0]['response']
            self.assertEqual(second_result['output']['visual_input'], 'ocr_only')
            await voice.cancel_tools()

    async def test_screen_inspection_keeps_ocr_when_video_send_fails(self):
        with tempfile.TemporaryDirectory() as runtime_dir:
            screen_dir = Path(runtime_dir) / 'jarvis_screen'
            screen_dir.mkdir()
            image = screen_dir / 'capture.jpg'
            image.write_bytes(b'\xff\xd8visual-frame\xff\xd9')

            class ScreenSkills:
                async def execute(self, name, args):
                    return {'status': 'inspected', 'text_content': 'Error dialog',
                            'screenshot_path': str(image)}

            responses = []

            async def reject_video(**kwargs):
                raise OSError('video transport unavailable')

            async def send_tool_response(*, function_responses):
                responses.append(function_responses)

            session = NS(send_realtime_input=reject_video,
                         send_tool_response=send_tool_response)
            voice = LiveVoice(native_engine(), skills=ScreenSkills())
            call = types.FunctionCall(id='screen-frame-2', name='inspect_screen', args={})
            with patch.dict('os.environ', {'XDG_RUNTIME_DIR': runtime_dir}):
                await voice.handle(types.LiveServerMessage(tool_call=types.LiveServerToolCall(
                    function_calls=[call])), session)
                for _ in range(25):
                    if responses:
                        break
                    await asyncio.sleep(.01)

            self.assertEqual(len(responses), 1)
            output = responses[0].response['output']
            self.assertEqual(output['visual_input'], 'ocr_only')
            self.assertEqual(output['text_content'], 'Error dialog')
            await voice.cancel_tools()

    async def test_goaway_reconnect_buffers_audio(self):
        voice = LiveVoice(native_engine())
        go_away_event = NS(
            session_resumption_update=None,
            go_away=NS(time_to_go="10s"),
            tool_call_cancellation=None,
            tool_call=None,
            server_content=None,
        )
        with self.assertRaises(RenewConnection):
            await voice.handle(go_away_event)

        reconnect_buffering_calls = []
        connect_count = 0

        class MockEngine:
            def __init__(self, *args, **kwargs):
                self.muted = False
                self.output_frame_bytes = 960
                self.async_input_queue = asyncio.Queue()
                self.c_output_queue = __import__('queue').SimpleQueue()
                self.on_barge_in = None

            def start(self, source, sink):
                pass

            def handle_barge_in(self):
                pass

            def set_muted(self, state):
                self.muted = state

            def set_reconnect_buffering(self, enabled: bool):
                reconnect_buffering_calls.append(enabled)

            async def stop_speaking(self):
                pass

            async def monitor_health(self):
                await asyncio.sleep(999999)

            def terminate(self):
                pass

        class MockLiveSession:
            def __init__(self, count):
                self.count = count

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                pass

        class MockLive:
            def connect(self, *args, **kwargs):
                nonlocal connect_count
                connect_count += 1
                return MockLiveSession(connect_count)

        async def mock_supervise(*workers):
            for w in workers:
                w.close()
            if connect_count == 1:
                raise RenewConnection()
            raise asyncio.CancelledError()

        class MockClientAio:
            def __init__(self):
                self.live = MockLive()

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                pass

        class MockClient:
            def __init__(self, *args, **kwargs):
                self.aio = MockClientAio()

        class Echo:
            sink = 'test-sink'
            source = 'test-source'

            async def start(self, microphone, **kwargs):
                pass

            async def close(self):
                pass

        async def no_wait(d):
            pass

        args = NS(model='test-model', voice='Aoede', transcripts=False, no_ipc=True,
                  microphone=None, retries=2, no_skills=True)
        with patch('google.genai.Client', MockClient), \
             patch('agent.EchoCancellation', return_value=Echo()), \
             patch('agent.NativeAudioEngine', MockEngine), \
             patch('agent.supervise', side_effect=mock_supervise), \
             patch('agent.asyncio.sleep', side_effect=no_wait):
            from config import Config
            configuration = Config()
            with self.assertRaises(asyncio.CancelledError):
                await run(args, 'fake-key', config=configuration)

        self.assertIn(True, reconnect_buffering_calls)
        self.assertIn(False, reconnect_buffering_calls)
        first_true = reconnect_buffering_calls.index(True)
        first_false_after_true = [i for i, val in enumerate(reconnect_buffering_calls) if val is False and i > first_true]
        self.assertTrue(len(first_false_after_true) > 0)


if __name__ == '__main__':
    unittest.main()


