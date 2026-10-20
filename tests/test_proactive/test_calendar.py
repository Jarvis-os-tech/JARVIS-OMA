import asyncio
from datetime import datetime, timedelta, timezone
import tempfile
import unittest
from zoneinfo import ZoneInfo

from proactive.calendar import calendar_agenda
from proactive.runtime import ProactiveRuntime
from tests.test_proactive.test_proactive_runtime import FakeOrchestrator


class CalendarTests(unittest.TestCase):
    def test_timezones_all_day_and_invalid_events(self):
        now = datetime(2026, 10, 18, 10, tzinfo=ZoneInfo('Asia/Kolkata'))
        events = [
            {'id': 'meeting', 'summary': 'Review', 'start': '2026-10-18T04:40:00Z'},
            {'id': 'later', 'start': '2026-10-18T11:00:00+05:30'},
            {'id': 'past', 'start': '2026-10-18T09:00:00+05:30'},
            {'id': 'day', 'summary': 'Holiday', 'start': '2026-10-18', 'end': '2026-10-19'},
            {'id': 'multi', 'start': '2026-10-17', 'end': '2026-10-20'},
            {'id': 'cancelled', 'status': 'cancelled', 'start': '2026-10-18T10:05:00+05:30'},
            {'id': 'naive', 'start': '2026-10-18T10:05:00'},
            {'id': 'bad', 'start': 'invalid'}, None]
        agenda, reminders = calendar_agenda(events, now)
        self.assertEqual(len(agenda), 5)
        self.assertEqual([e['id'] for e in reminders], ['meeting'])
        self.assertEqual(reminders[0]['minutes_until'], 10)
        self.assertEqual(reminders[0]['start'], '2026-10-18T10:10:00+05:30')
        self.assertTrue(agenda[0]['all_day'])

    def test_midnight_and_exact_boundaries(self):
        now = datetime(2026, 10, 18, 23, 55, tzinfo=timezone.utc)
        events = [{'id': str(minutes), 'start': (now + timedelta(minutes=minutes)).isoformat()}
                  for minutes in (0, 1, 10, 11)]
        agenda, reminders = calendar_agenda(events, now)
        self.assertEqual(len(agenda), 2)
        self.assertEqual([e['id'] for e in reminders], ['1', '10'])
        with self.assertRaises(ValueError):
            calendar_agenda(events, now.replace(tzinfo=None))

    def test_runtime_briefing_dedupe_reschedule_and_controls(self):
        async def scenario(root):
            now = datetime.now(timezone.utc)
            start = (now + timedelta(minutes=9)).isoformat()
            events = [{'id': 'one', 'summary': 'Review', 'start': start}]
            orchestrator = FakeOrchestrator()
            runtime = ProactiveRuntime(root, orchestrator)
            agenda = runtime.observe_calendar(events, now=now)
            runtime.observe_focus([], root, now=now, calendar=agenda)
            results = (await runtime.tick())['results']
            self.assertEqual({r['status'] for r in results}, {'calendar_reminder', 'suggested'})
            briefing = next(r for r in results if r['status'] == 'suggested')
            self.assertEqual(briefing['calendar'][0]['title'], 'Review')
            self.assertEqual(orchestrator.calls, [])
            await runtime.close()
            runtime = ProactiveRuntime(root, orchestrator)
            runtime.observe_calendar(events, now=now)
            self.assertEqual((await runtime.tick())['results'], [])
            events[0]['start'] = (now + timedelta(minutes=8)).isoformat()
            runtime.pause()
            runtime.observe_calendar(events, now=now)
            self.assertEqual(runtime.status()['pending_events'], 0)
            runtime.resume()
            runtime.observe_calendar(events, now=now)
            self.assertEqual((await runtime.tick())['results'][0]['status'], 'calendar_reminder')
            await runtime.close()
        with tempfile.TemporaryDirectory() as root:
            asyncio.run(scenario(root))

    def test_expired_reminder_is_not_announced_after_pause(self):
        async def scenario(root):
            now = datetime.now(timezone.utc)
            runtime = ProactiveRuntime(root, FakeOrchestrator())
            runtime.observe_calendar([{'id': 'old', 'start': now.isoformat()}],
                                     now=now - timedelta(minutes=5))
            self.assertEqual(runtime.status()['pending_events'], 1)
            runtime.pause()
            self.assertEqual((await runtime.tick())['status'], 'paused')
            runtime.resume()
            self.assertEqual((await runtime.tick())['results'], [])
            await runtime.close()
        with tempfile.TemporaryDirectory() as root:
            asyncio.run(scenario(root))
