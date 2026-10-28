"""Startup/configuration and audio recovery regressions without devices or network."""
import asyncio
import contextlib
import io
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from core import agent
from core.config import Config
from audio.engine import StreamLostError


class CommandLineConfigTests(unittest.TestCase):
    def check_config(self, extra_args=(), env=None):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'config.toml'
            path.write_text('[agent]\nmodel="saved-model"\nvoice="Kore"\n'
                            '[audio]\nbackend="legacy"\n'
                            '[skills]\nenabled=false\n')
            with patch.dict(os.environ, env or {}, clear=True), \
                 patch('sys.argv', ['agent', '--check', '--config', str(path), *extra_args]), \
                 patch.object(agent.shutil, 'which', return_value='/usr/bin/pactl'), \
                 patch.object(agent, 'DesktopSkills') as skills, \
                 patch.object(agent, 'live_config', wraps=agent.live_config) as live_config, \
                 contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(agent.main(), 0)
                skills.assert_not_called()
                self.assertIn('skills disabled', output.getvalue())
                return live_config.call_args.args[0], live_config.call_args.kwargs['config']

    def test_saved_settings_survive_absent_cli_overrides(self):
        voice, config = self.check_config()
        self.assertEqual(config.agent.model, 'saved-model')
        self.assertEqual(voice, 'Kore')
        self.assertFalse(config.skills.enabled)

    def test_environment_overrides_file_and_explicit_cli_wins(self):
        voice, config = self.check_config(env={'JARVIS_MODEL': 'env-model', 'JARVIS_VOICE': 'Puck'})
        self.assertEqual((config.agent.model, voice), ('env-model', 'Puck'))
        voice, config = self.check_config(('--model', 'cli-model', '--voice', 'Charon'),
                                          {'JARVIS_MODEL': 'env-model', 'JARVIS_VOICE': 'Puck'})
        self.assertEqual((config.agent.model, voice), ('cli-model', 'Charon'))

    def test_invalid_audio_is_a_configuration_error_without_opening_devices(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'config.toml'
            path.write_text('[audio]\ninput_frame_ms=0\n')
            with patch.dict(os.environ, {}, clear=True), \
                 patch('sys.argv', ['agent', '--check', '--config', str(path)]), \
                 patch.object(agent.shutil, 'which', return_value='/usr/bin/pactl'), \
                 patch.object(agent, 'EchoCancellation') as echo, \
                 contextlib.redirect_stderr(io.StringIO()) as errors:
                with self.assertRaises(SystemExit) as raised:
                    agent.main()
                self.assertEqual(raised.exception.code, 2)
                self.assertIn('audio.input_frame_ms', errors.getvalue())
                echo.assert_not_called()


class StartupTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.config = Config()
        # These fixtures mock NativeAudioEngine specifically. Production may
        # choose another backend; tests must never open a real audio companion.
        self.config.audio.backend = 'legacy'
        self.config.skills.enabled = False
        self.config.agent.greet_on_activation = False
        self.config.agent.model = 'saved-model'
        self.config.agent.voice = 'Kore'
        self.args = NS(model=None, voice=None, microphone=None, transcripts=False,
                       no_ipc=True, retries=2)
        self.echo = NS(start=AsyncMock(), close=AsyncMock(), source='source', sink='sink')
        self.engine = MagicMock()
        self.engine.async_input_queue = asyncio.Queue()
        self.engine.monitor_health = AsyncMock()
        self.connect_calls = []

        @contextlib.asynccontextmanager
        async def connect(**kwargs):
            self.connect_calls.append(kwargs)
            yield NS()

        @contextlib.asynccontextmanager
        async def client_context():
            yield NS(live=NS(connect=connect))

        self.client = NS(aio=client_context())

    async def supervise_once(self, *workers):
        for worker in workers:
            worker.close()
        raise asyncio.CancelledError()

    async def test_invalid_programmatic_config_fails_before_echo_acquisition(self):
        self.config.audio.output_sample_rate = 48000
        with patch.object(agent, 'EchoCancellation') as factory:
            with self.assertRaisesRegex(ValueError, 'output_sample_rate'):
                await agent.run(self.args, 'fake', config=self.config)
            factory.assert_not_called()

    async def test_echo_failure_preserves_error_and_cleans_up(self):
        error = TypeError('echo setup failed internally')
        self.echo.start.side_effect = error
        self.echo.close.side_effect = OSError('cleanup also failed')
        with patch.object(agent, 'EchoCancellation', return_value=self.echo), \
             patch.object(agent, 'NativeAudioEngine') as factory, \
             self.assertLogs('gemini_voice', level='WARNING'):
            with self.assertRaises(TypeError) as raised:
                await agent.run(self.args, 'fake', config=self.config)
        self.assertIs(raised.exception, error)
        self.echo.start.assert_awaited_once()
        self.echo.close.assert_awaited_once()
        factory.assert_not_called()

    async def test_stream_start_failure_releases_audio_and_echo(self):
        error = OSError('output device unavailable')
        self.engine.start.side_effect = error
        with patch.object(agent, 'EchoCancellation', return_value=self.echo), \
             patch.object(agent, 'NativeAudioEngine', return_value=self.engine):
            with self.assertRaises(OSError) as raised:
                await agent.run(self.args, 'fake', config=self.config)
        self.assertIs(raised.exception, error)
        self.engine.terminate.assert_called_once()
        self.echo.close.assert_awaited_once()

    async def test_resolved_settings_reach_connection_and_local_interruption(self):
        self.config.vad.activity_handling = 'NO_INTERRUPTION'
        with patch.object(agent, 'EchoCancellation', return_value=self.echo), \
             patch.object(agent, 'NativeAudioEngine', return_value=self.engine) as factory, \
             patch.object(agent, 'DesktopSkills') as skills, \
             patch('google.genai.Client', return_value=self.client), \
             patch.object(agent, 'supervise', side_effect=self.supervise_once):
            with self.assertRaises(asyncio.CancelledError):
                await agent.run(self.args, 'fake', config=self.config)
        skills.assert_not_called()
        self.assertFalse(factory.call_args.kwargs['allow_barge_in'])
        self.assertEqual(self.connect_calls[0]['model'], 'saved-model')
        speech = self.connect_calls[0]['config']['speech_config']
        self.assertEqual(speech['voice_config']['prebuilt_voice_config']['voice_name'], 'Kore')
        self.engine.terminate.assert_called_once()
        self.echo.close.assert_awaited_once()

    async def test_local_barge_in_is_opt_in_with_server_interruption_enabled(self):
        self.config.audio.local_barge_in = True
        with patch.object(agent, 'EchoCancellation', return_value=self.echo), \
             patch.object(agent, 'NativeAudioEngine', return_value=self.engine) as factory, \
             patch.object(agent, 'DesktopSkills'), \
             patch('google.genai.Client', return_value=self.client), \
             patch.object(agent, 'supervise', side_effect=self.supervise_once):
            with self.assertRaises(asyncio.CancelledError):
                await agent.run(self.args, 'fake', config=self.config)
        self.assertTrue(factory.call_args.kwargs['allow_barge_in'])

    async def test_native_audio_readiness_precedes_skills_and_provider_startup(self):
        self.config.audio.backend = 'native'
        self.config.skills.enabled = True
        self.config.memory.enabled = False
        events = []
        engine = self.engine
        engine.start.side_effect = lambda *_args: events.append('audio_started')
        engine.wait_ready = AsyncMock(side_effect=lambda *_args: events.append('audio_ready'))
        engine.aclose = AsyncMock()
        skills = MagicMock()
        skills.close_agent_jobs = AsyncMock()

        class NativeCompanionStub:
            def __init__(self, *_args, **_kwargs):
                events.append('native_created')

            def __getattr__(self, name):
                return getattr(engine, name)

        def skills_factory(*_args, **_kwargs):
            self.assertEqual(events[-1], 'audio_ready')
            events.append('skills_created')
            return skills

        def provider_factory(*_args, **_kwargs):
            self.assertIn('audio_ready', events)
            self.assertIn('skills_created', events)
            events.append('provider_created')
            return self.client

        with patch.object(agent, 'EchoCancellation', return_value=self.echo), \
             patch.object(agent, 'NativeCompanionEngine', new=NativeCompanionStub), \
             patch.object(agent, 'NativeAudioEngine', side_effect=AssertionError('wrong audio backend')), \
             patch.object(agent, 'DesktopSkills', side_effect=skills_factory), \
             patch.object(agent, 'live_config', return_value={}), \
             patch.object(agent.LiveVoice, 'start_observers'), \
             patch('google.genai.Client', side_effect=provider_factory), \
             patch.object(agent, 'supervise', side_effect=self.supervise_once):
            with self.assertRaises(asyncio.CancelledError):
                await agent.run(self.args, 'fake', config=self.config)

        self.assertEqual(events, ['native_created', 'audio_started', 'audio_ready',
                                  'skills_created', 'provider_created'])
        engine.wait_ready.assert_awaited_once_with('source', 'sink')
        engine.terminate.assert_called_once()
        engine.aclose.assert_awaited_once()
        skills.close_agent_jobs.assert_awaited_once()
        self.assertEqual(len(self.connect_calls), 1)
        self.echo.close.assert_awaited_once()

    async def test_cancellation_during_skill_cleanup_still_releases_audio(self):
        self.config.skills.enabled = True
        skills = MagicMock()
        skills.close_agent_jobs = AsyncMock(side_effect=asyncio.CancelledError)
        with patch.object(agent, 'EchoCancellation', return_value=self.echo), \
             patch.object(agent, 'NativeAudioEngine', return_value=self.engine), \
             patch.object(agent, 'DesktopSkills', return_value=skills), \
             patch('google.genai.Client', return_value=self.client), \
             patch.object(agent, 'supervise', side_effect=self.supervise_once):
            with self.assertRaises(asyncio.CancelledError):
                await agent.run(self.args, 'fake', config=self.config)
        self.engine.terminate.assert_called_once()
        self.echo.close.assert_awaited_once()

    async def test_failed_audio_recovery_does_not_open_another_provider_session(self):
        self.engine.start.side_effect = [None, OSError('gone'), OSError('gone'), OSError('gone')]

        async def lost_stream(*workers):
            for worker in workers:
                worker.close()
            raise StreamLostError('capture lost')

        with patch.object(agent, 'EchoCancellation', return_value=self.echo), \
             patch.object(agent, 'NativeAudioEngine', return_value=self.engine), \
             patch('google.genai.Client', return_value=self.client), \
             patch.object(agent, 'supervise', side_effect=lost_stream), \
             patch.object(agent.asyncio, 'sleep', new_callable=AsyncMock) as sleep, \
             self.assertLogs('gemini_voice', level='WARNING'):
            with self.assertRaisesRegex(StreamLostError, 'after 3 attempts'):
                await agent.run(self.args, 'fake', config=self.config)
        self.assertEqual(len(self.connect_calls), 1)
        self.assertEqual(self.engine.start.call_count, 4)
        self.assertEqual([call.args[0] for call in sleep.await_args_list], [1, 2])
        self.echo.close.assert_awaited_once()


class RecoveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_invalid_retry_budget_fails_before_touching_streams(self):
        engine = MagicMock()
        with self.assertRaisesRegex(ValueError, 'nonnegative integer'):
            await agent.recover_audio(engine, 'source', 'sink', -1)
        engine.start.assert_not_called()
        engine.terminate.assert_not_called()

    async def test_transient_device_failure_recovers_with_backoff(self):
        engine = MagicMock()
        engine.start.side_effect = [OSError('temporarily gone'), None]
        with patch.object(agent.asyncio, 'sleep', new_callable=AsyncMock) as sleep, \
             self.assertLogs('gemini_voice', level='WARNING'):
            await agent.recover_audio(engine, 'source', 'sink', 2)
        self.assertEqual(engine.start.call_count, 2)
        sleep.assert_awaited_once_with(1)

    async def test_cancellation_during_backoff_stops_retrying(self):
        engine = MagicMock()
        engine.start.side_effect = OSError('gone')
        with patch.object(agent.asyncio, 'sleep', side_effect=asyncio.CancelledError), \
             self.assertLogs('gemini_voice', level='WARNING'):
            with self.assertRaises(asyncio.CancelledError):
                await agent.recover_audio(engine, 'source', 'sink', 2)
        engine.start.assert_called_once()
