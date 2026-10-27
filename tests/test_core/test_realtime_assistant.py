"""Integrated assistant observations, quiet delivery, memory and timing."""
import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace as NS
import unittest
from unittest.mock import AsyncMock, patch

from google.genai import types
from core.agent import LiveVoice
from core.config import Config, load_config
from proactive.runtime import ProactiveRuntime
from tests.test_proactive.test_proactive_runtime import FakeOrchestrator


class RealtimeAssistantTests(unittest.IsolatedAsyncioTestCase):
    def voice(self, **settings):
        config = Config()
        config.proactive.system_alerts = False
        for name, value in settings.items():
            setattr(config.proactive, name, value)
        skills = NS(_adapter_google_calendar_list_events=AsyncMock(return_value={'success': True, 'events': []}),
                    _adapter_list_reminders=AsyncMock(return_value={'reminders': []}),
                    _adapter_list_todos=AsyncMock(return_value={'tasks': []}))
        return LiveVoice(None, config=config, skills=skills)

    async def test_cached_calendar_event_enters_reminder_window_without_cloud_refresh(self):
        voice = self.voice()
        origin = datetime.now(timezone.utc).replace(microsecond=0)
        current = [origin]

        class Clock(datetime):
            @classmethod
            def now(cls, zone=None):
                return current[0].astimezone(zone) if zone else current[0]

        event = {'id': 'meeting', 'summary': 'Review', 'start': (origin + timedelta(minutes=11)).isoformat()}
        voice.skills._adapter_google_calendar_list_events.return_value = {'success': True, 'events': [event]}
        with tempfile.TemporaryDirectory() as root:
            runtime = ProactiveRuntime(root, FakeOrchestrator())
            try:
                with patch('core.agent.datetime', Clock), patch('core.agent.time.monotonic', return_value=100):
                    await voice._observe_proactive_once(runtime)
                self.assertFalse(voice._notices)
                current[0] += timedelta(seconds=90)
                with patch('core.agent.datetime', Clock), patch('core.agent.time.monotonic', return_value=190):
                    await voice._observe_proactive_once(runtime)
                voice.skills._adapter_google_calendar_list_events.assert_awaited_once()
                self.assertEqual(len(voice._notices), 1)
                self.assertIn('Review', voice._notices[0]['text'])
                self.assertEqual(runtime.orchestrator.calls, [])
            finally:
                await runtime.close()

    async def test_refresh_discards_cancelled_or_rescheduled_calendar_notice(self):
        voice = self.voice()
        now = datetime.now(timezone.utc)
        event = {'id': 'meeting', 'start': (now + timedelta(minutes=5)).isoformat()}
        voice._queue_notice('Meeting', expires_at=event['start'], calendar_event=event)
        voice._calendar_fetched_at = time.monotonic()
        voice._calendar_events = [{'id': 'meeting', 'status': 'cancelled', 'start': event['start']}]
        self.assertFalse(voice._notice_is_current(voice._notices[0]))
        voice._calendar_events = [{**event, 'start': (now + timedelta(hours=1)).isoformat()}]
        self.assertFalse(voice._notice_is_current(voice._notices[0]))
        voice._calendar_events = [event]
        self.assertTrue(voice._notice_is_current(voice._notices[0]))

    async def test_pause_skips_calendar_system_and_reminder_observations(self):
        voice = self.voice(system_alerts=True)
        with tempfile.TemporaryDirectory() as root:
            runtime = ProactiveRuntime(root, FakeOrchestrator())
            try:
                await runtime.call('pause')
                with patch('core.agent.sample_system') as sample:
                    await voice._observe_proactive_once(runtime)
                sample.assert_not_called()
                voice.skills._adapter_google_calendar_list_events.assert_not_awaited()
                voice.skills._adapter_list_reminders.assert_not_awaited()
                self.assertFalse(voice._notices)
            finally:
                await runtime.close()

    async def test_already_queued_focus_summary_waits_for_resume(self):
        voice = self.voice(daily_focus=True, quiet_seconds=0, notice_cooldown_seconds=0)
        with tempfile.TemporaryDirectory() as root:
            runtime = ProactiveRuntime(root, FakeOrchestrator())
            voice.skills.get_proactive = AsyncMock(return_value=runtime)
            voice.skills._adapter_list_todos.return_value = {'tasks': [
                {'title': 'Prepare report', 'priority': 'high', 'status': 'ongoing'}]}
            await voice._observe_proactive_once(runtime)
            self.assertEqual(len(voice._notices), 1)
            await runtime.call('pause')
            session = NS(send_client_content=AsyncMock())
            sender = asyncio.create_task(voice.send_notifications(session))
            try:
                await asyncio.sleep(.12)
                session.send_client_content.assert_not_awaited()
                await runtime.call('resume')
                async with asyncio.timeout(1):
                    while session.send_client_content.await_count == 0:
                        await asyncio.sleep(.01)
                session.send_client_content.assert_awaited_once()
            finally:
                sender.cancel()
                await asyncio.gather(sender, return_exceptions=True)
                await runtime.close()

    async def test_proactive_disable_keeps_explicit_runtime_work_separate(self):
        voice = self.voice(enabled=False)
        runtime = NS(control=NS(get_state=lambda: NS(can_run=True)),
                     call=AsyncMock(return_value=NS(can_run=True)), tick=AsyncMock())
        await voice._observe_proactive_once(runtime)
        runtime.tick.assert_awaited_once()
        voice.skills._adapter_google_calendar_list_events.assert_not_awaited()
        voice.skills._adapter_list_reminders.assert_not_awaited()

    async def test_continuous_mode_keeps_checking_after_startup(self):
        voice = self.voice()
        requested = asyncio.Event()  # Configuration enables background observation independently.
        voice.skills.proactive_service_requested = requested
        runtime = object()
        voice.skills.get_proactive = AsyncMock(return_value=runtime)
        voice._observe_proactive_once = AsyncMock()
        sleeps = 0

        async def sleep(seconds):
            nonlocal sleeps
            self.assertEqual(seconds, 30)
            sleeps += 1
            if sleeps == 3:
                raise asyncio.CancelledError

        with patch('core.agent.asyncio.sleep', side_effect=sleep):
            with self.assertRaises(asyncio.CancelledError):
                await voice.run_proactive(None)
        self.assertEqual(voice._observe_proactive_once.await_count, 3)
        voice.skills.get_proactive.assert_awaited_with(activate=False)

    async def test_observer_is_single_owned_task_across_provider_reconnects(self):
        from core.agent import supervise
        voice = self.voice()
        started, stopped = asyncio.Event(), asyncio.Event()

        async def observe(session):
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                stopped.set()

        async def failed_connection():
            raise ConnectionError('provider disconnected')

        voice.run_proactive = observe
        voice.start_observers()
        await asyncio.wait_for(started.wait(), 1)
        owned = voice._observer_task
        try:
            for _ in range(2):
                with self.assertRaises(ConnectionError):
                    await supervise(failed_connection())
                voice.start_observers()
                self.assertIs(voice._observer_task, owned)
                self.assertFalse(stopped.is_set())
        finally:
            await voice.stop_observers()
        self.assertTrue(stopped.is_set())
        self.assertIsNone(voice._observer_task)

    async def test_future_native_timer_does_not_trigger_an_action_or_early_alert(self):
        voice = self.voice(calendar=False)
        now = datetime.now(timezone.utc)
        reminder = {'timer': 'one', 'message': 'Take a break', 'at': (now + timedelta(hours=1)).timestamp()}
        voice.skills._adapter_list_reminders.return_value = {'reminders': [reminder]}
        with tempfile.TemporaryDirectory() as root:
            runtime = ProactiveRuntime(root, FakeOrchestrator())
            try:
                await voice._observe_proactive_once(runtime)
                self.assertFalse(voice._notices)
                reminder['at'] = (now + timedelta(seconds=40)).timestamp()
                await voice._observe_proactive_once(runtime)
                await voice._observe_proactive_once(runtime)
                self.assertEqual(len(voice._notices), 1)
                self.assertIn('Take a break', voice._notices[0]['text'])
                self.assertEqual(runtime.orchestrator.calls, [])
            finally:
                await runtime.close()

    async def test_pending_system_alert_disappears_after_confirmed_recovery(self):
        voice = self.voice()
        alert = voice.system_watch.observe({'battery_percent': 10, 'battery_charging': False}, 1)[0]
        voice._queue_notice(alert['text'], system_key=alert['key'],
                            expires_at=(datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat())
        self.assertTrue(voice._notice_is_current(voice._notices[0]))
        voice.system_watch.observe({'battery_percent': 12, 'battery_charging': True}, 2)
        self.assertFalse(voice._notice_is_current(voice._notices[0]))

    async def test_first_session_memory_preload_is_used_by_session_prompt(self):
        from core.harness_config import live_config
        voice = self.voice()
        voice.skills.memory_call = AsyncMock(return_value='User preference: concise English.')
        await voice.preload_memory_context()
        config = live_config('Aoede', config=voice.config, memory_context=voice._memory_context,
                             skills=NS(declarations=[], memory_context=lambda: ''))
        self.assertIn('User preference: concise English.', config['system_instruction'])

    async def test_memory_preload_failure_never_prevents_voice_startup(self):
        voice = self.voice()
        voice.skills.memory_call = AsyncMock(side_effect=OSError('unavailable'))
        await voice.preload_memory_context()
        self.assertEqual(voice._memory_context, '')

    async def test_real_provider_events_feed_timing_without_transcript_storage(self):
        voice = self.voice()
        voice.config.memory.enabled = False
        with patch('core.response_metrics.time.monotonic', return_value=10):
            voice.response_metrics._clock = lambda: 10
            await voice.handle(types.LiveServerMessage(server_content=types.LiveServerContent(
                input_transcription=types.Transcription(text='Hello'))))
        voice.response_metrics._clock = lambda: 10.25
        await voice.handle(types.LiveServerMessage(server_content=types.LiveServerContent(
            model_turn=types.Content(parts=[types.Part(inline_data=types.Blob(data=bytes(960), mime_type='audio/pcm'))]))))
        self.assertEqual(voice.response_metrics.snapshot()['response_first_audio_ms'], 250)

    async def test_notice_waits_for_quiet_and_spaces_out_task_updates(self):
        voice = self.voice(quiet_seconds=.03, notice_cooldown_seconds=.06)
        session = NS(send_client_content=AsyncMock())
        voice.attention.note_activity(time.monotonic())
        voice._queue_notice('Task one completed')
        voice._queue_notice('Task two completed')
        sender = asyncio.create_task(voice.send_notifications(session))
        try:
            await asyncio.sleep(.01)
            session.send_client_content.assert_not_awaited()
            async with asyncio.timeout(1):
                while session.send_client_content.await_count < 1:
                    await asyncio.sleep(.005)
            voice._response_active = False
            voice._response_idle.set()
            await asyncio.sleep(.01)
            self.assertEqual(session.send_client_content.await_count, 1)
            async with asyncio.timeout(1):
                while session.send_client_content.await_count < 2:
                    await asyncio.sleep(.005)
        finally:
            sender.cancel()
            await asyncio.gather(sender, return_exceptions=True)

    async def test_assistant_status_tool_is_wired_and_never_exposes_speech(self):
        from skills import DesktopSkills
        skills = DesktopSkills(config=Config())
        self.assertIn('get_assistant_status', {item['name'] for item in skills.declarations})
        self.assertFalse((await skills.execute('get_assistant_status', {}))['available'])
        voice = self.voice()
        skills.assistant_status_provider = voice.assistant_status
        result = await skills.execute('get_assistant_status', {})
        self.assertTrue(result['available'])
        self.assertIn('response_timing_scope', result)
        self.assertNotIn('transcript', result)
        self.assertNotIn('api_key', result)
        await skills.close_agent_jobs()

    async def test_proactive_status_does_not_request_continuous_work(self):
        from skills import DesktopSkills
        runtime = NS(call=AsyncMock(return_value={'status': 'paused'}))
        owner = NS(get_proactive=AsyncMock(return_value=runtime))
        result = await DesktopSkills._adapter_proactive_status(owner)
        self.assertEqual(result['status'], 'paused')
        owner.get_proactive.assert_awaited_once_with(activate=False)

    def test_proactive_configuration_loads_validates_and_defaults_to_balanced(self):
        config = Config()
        self.assertTrue(config.proactive.enabled)
        self.assertFalse(config.proactive.daily_focus)
        for name, value in (('enabled', 1), ('quiet_seconds', -1),
                            ('calendar_refresh_seconds', 0), ('poll_interval_seconds', True)):
            candidate = Config()
            setattr(candidate.proactive, name, value)
            with self.assertRaisesRegex(ValueError, 'proactive'):
                candidate.validate()
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / 'config.toml'
            path.write_text('[proactive]\nenabled = false\nquiet_seconds = 3.5\n')
            config = load_config(path)
            self.assertFalse(config.proactive.enabled)
            self.assertEqual(config.proactive.quiet_seconds, 3.5)
