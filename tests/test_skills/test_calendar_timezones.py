"""Calendar timezone parameters survive the voice tool-to-connector pipeline."""
import unittest
from unittest.mock import patch

from connectors import google_workspace as google
from skills import DesktopSkills


class CalendarTimezoneTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        # API calls are mocked; isolate routing checks from worker scheduling.
        async def immediate(function, *args, **kwargs):
            return function(*args, **kwargs)
        worker = patch.object(google.asyncio, 'to_thread', immediate)
        worker.start()
        self.addCleanup(worker.stop)

    async def test_voice_tool_forwards_explicit_timezone_and_datetime(self):
        with patch.object(google, '_api', return_value={'id': 'synthetic-event'}) as api:
            result = await DesktopSkills().execute('calendar_create_event', {
                'summary': 'Timezone test', 'start_datetime': '2026-10-26T10:00:00+09:00',
                'end_datetime': '2026-10-26T10:15:00+09:00', 'time_zone': 'Asia/Tokyo'})
        self.assertTrue(result['success'])
        body = api.call_args.args[2]
        self.assertEqual(body['start'], {'dateTime': '2026-10-26T10:00:00+09:00', 'timeZone': 'Asia/Tokyo'})
        self.assertEqual(body['end']['timeZone'], 'Asia/Tokyo')

    def test_omitted_timezone_preserves_existing_default(self):
        with patch.object(google, '_api', return_value={'id': 'synthetic-event'}) as api:
            google.calendar_create_event('Default', '2026-10-26T10:00:00', '2026-10-26T11:00:00')
        body = api.call_args.args[2]
        self.assertEqual(body['start']['timeZone'], 'Asia/Kolkata')
        self.assertEqual(body['end']['timeZone'], 'Asia/Kolkata')

    async def test_invalid_timezone_is_rejected_before_network(self):
        with patch.object(google, '_api', side_effect=AssertionError('unexpected network')):
            result = await google.dispatch('calendar_create_event', {
                'summary': 'Invalid', 'start_datetime': '2026-10-26T10:00:00',
                'end_datetime': '2026-10-26T11:00:00', 'time_zone': 'Not/AZone'})
        self.assertFalse(result['success'])
        self.assertIn('timezone', result['error'].lower())
