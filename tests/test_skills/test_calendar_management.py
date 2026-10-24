"""Calendar voice-tool management and IST time boundaries, without live Google writes."""
from datetime import datetime, timedelta
import unittest
from unittest.mock import patch

from connectors import google_workspace as google
from connectors.calendar_time import calendar_interval
from skills import DesktopSkills


class CalendarManagementTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        async def immediate(function, *args, **kwargs):
            return function(*args, **kwargs)
        worker = patch.object(google.asyncio, 'to_thread', immediate)
        worker.start()
        self.addCleanup(worker.stop)
        self.skills = DesktopSkills()

    def test_new_calendar_tools_are_valid_voice_declarations(self):
        from google.genai import types
        from core.agent import live_config
        config = types.LiveConnectConfig.model_validate(live_config('Aoede', skills=self.skills))
        names = {item.name for item in config.tools[0].function_declarations}
        self.assertTrue({'calendar_current_time', 'calendar_update_event',
                         'calendar_delete_event', 'calendar_check_availability'} <= names)

    def test_readback_uses_provider_time_and_identifies_unverified_fallback(self):
        with patch.object(google, '_api', return_value={
                'id': 'test', 'recurringEventId': 'series-master', 'start': {'dateTime': '2026-10-26T15:00:00+05:30', 'timeZone': 'Asia/Kolkata'},
                'end': {'dateTime': '2026-10-26T15:30:00+05:30'}}):
            result = google.calendar_get_event('test')
        self.assertTrue(result['time_verified'])
        self.assertEqual(result['recurring_event_id'], 'series-master')
        self.assertEqual(result['start'], '2026-10-26T15:00:00+05:30')
        self.assertFalse(google._calendar_result({'id': 'test'}, {'start': {'dateTime': 'requested'}})['time_verified'])

    async def test_partial_reschedule_is_rejected_without_write(self):
        with patch.object(google, '_api', side_effect=AssertionError('network')):
            result = await self.skills.execute('calendar_update_event', {
                'event_id': 'test', 'start_datetime': '2026-10-26T15:00:00'})
        self.assertFalse(result['success'])

    async def test_invalid_recurrence_and_reminder_do_not_reach_api(self):
        for options in ({'recurrence_rule': 'FREQ=DAILY'}, {'recurrence_rule': 'RRULE:FREQ=DAILY\nBAD'},
                        {'reminder_minutes': -2}, {'reminder_minutes': True}):
            with self.subTest(options=options), patch.object(google, '_api', side_effect=AssertionError('network')):
                # Direct connector validation also protects callers outside the schema.
                result = google.calendar_update_event('test', **options)
                self.assertFalse(result['success'])

    async def test_clock_tool_defaults_to_fresh_ist(self):
        result = await self.skills.execute('calendar_current_time', {})
        self.assertTrue(result['success'])
        current = datetime.fromisoformat(result['now'])
        self.assertEqual(current.utcoffset(), timedelta(hours=5, minutes=30))
        self.assertLess(abs((datetime.now(current.tzinfo) - current).total_seconds()), 5)
        self.assertEqual(result['time_zone'], 'Asia/Kolkata')

    async def test_create_keeps_requested_ist_wall_time_and_returns_it(self):
        with patch.object(google, '_api', return_value={'id': 'test-id'}) as api:
            result = await self.skills.execute('calendar_create_event', {
                'summary': 'IST test', 'start_datetime': '2026-10-26T15:00:00',
                'end_datetime': '2026-10-26T15:30:00', 'reminder_minutes': 10,
                'recurrence_rule': 'RRULE:FREQ=DAILY;COUNT=2'})
        body = api.call_args.args[2]
        self.assertEqual(body['start']['dateTime'], '2026-10-26T15:00:00+05:30')
        self.assertEqual(result['start'], body['start']['dateTime'])
        self.assertEqual(result['time_zone'], 'Asia/Kolkata')
        self.assertEqual(body['recurrence'], ['RRULE:FREQ=DAILY;COUNT=2'])
        self.assertEqual(body['reminders']['overrides'], [{'method': 'popup', 'minutes': 10}])

    async def test_bad_times_rejected_before_api_call(self):
        for start, end in [('2026-10-26T15:00:00Z', '2026-10-26T15:30:00Z'),
                           ('2026-10-26T15:00:00', '2026-10-26T14:00:00'),
                           ('tomorrow afternoon', '2026-10-26T16:00:00')]:
            with self.subTest(start=start), patch.object(google, '_api', side_effect=AssertionError('network')):
                result = await self.skills.execute('calendar_create_event', {
                    'summary': 'Invalid', 'start_datetime': start, 'end_datetime': end})
                self.assertFalse(result['success'])

    async def test_reschedule_preserves_other_fields_and_escapes_ids(self):
        with patch.object(google, '_api', return_value={'id': 'a/b'}) as api:
            result = await self.skills.execute('calendar_update_event', {
                'event_id': 'a/b', 'calendar_id': 'x/y', 'start_datetime': '2026-10-26T16:00:00',
                'end_datetime': '2026-10-26T16:30:00'})
        self.assertEqual(api.call_args.args[0], 'PATCH')
        self.assertTrue(api.call_args.args[1].endswith('/x%2Fy/events/a%2Fb'))
        self.assertNotIn('summary', api.call_args.args[2])
        self.assertEqual(result['start'], '2026-10-26T16:00:00+05:30')

    async def test_update_can_disable_reminder_and_recurrence(self):
        with patch.object(google, '_api', return_value={'id': 'test'}) as api:
            result = await self.skills.execute('calendar_update_event', {
                'event_id': 'test', 'reminder_minutes': -1, 'recurrence_rule': ''})
        self.assertTrue(result['success'])
        self.assertEqual(api.call_args.args[2], {'recurrence': [], 'reminders': {'useDefault': False, 'overrides': []}})

    async def test_delete_uses_exact_id_and_preserves_api_errors(self):
        with patch.object(google, '_api', return_value={}) as api:
            result = await self.skills.execute('calendar_delete_event', {'event_id': 'a/b'})
        self.assertTrue(result['deleted'])
        self.assertEqual(api.call_args.args[0], 'DELETE')
        self.assertTrue(api.call_args.args[1].endswith('/events/a%2Fb'))
        with patch.object(google, '_api', return_value={'error': 'HTTP 403'}):
            result = await self.skills.execute('calendar_delete_event', {'event_id': 'a/b'})
        self.assertFalse(result['success'])
        self.assertNotIn('deleted', result)

    async def test_availability_errors_do_not_mean_free(self):
        args = {'start_datetime': '2026-10-26T15:00:00', 'end_datetime': '2026-10-26T16:00:00'}
        for response, expected in [({'calendars': {'primary': {'busy': []}}}, True),
                                   ({'calendars': {'primary': {'busy': [{'start': 'busy'}]}}}, False),
                                   ({'calendars': {'primary': {'errors': [{'reason': 'notFound'}]}}}, None)]:
            with self.subTest(response=response), patch.object(google, '_api', return_value=response):
                result = await self.skills.execute('calendar_check_availability', args)
                if expected is None:
                    self.assertFalse(result['success'])
                else:
                    self.assertIs(result['available'], expected)

    def test_dst_gap_and_ambiguity_are_not_guessed(self):
        for start, end in [('2026-03-08T02:30:00', '2026-03-08T03:30:00'),
                           ('2026-11-01T01:30:00', '2026-11-01T02:30:00')]:
            with self.subTest(start=start), self.assertRaises(ValueError):
                calendar_interval(start, end, 'America/New_York')
        start, end = calendar_interval('2026-10-26T15:00:00', '2026-10-26T15:30:00', 'IST')
        self.assertEqual(start['timeZone'], 'Asia/Kolkata')
