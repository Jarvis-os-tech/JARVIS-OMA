"""Local resource observation never invents unknown readings or repeats alerts."""
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from proactive.system_watch import SystemWatch, sample_system


class SystemWatchTests(unittest.TestCase):
    def test_unknown_or_invalid_values_do_not_create_alerts(self):
        watch = SystemWatch()
        self.assertEqual(watch.observe({}, 0), [])
        for index, value in enumerate((None, True, '2', -1, 101, 10**1000, float('nan'), float('inf')), 1):
            self.assertEqual(watch.observe({'battery_percent': value,
                'battery_charging': False, 'disk_free_percent': value,
                'memory_available_percent': value}, index), [])
        self.assertEqual(watch.observe({'battery_percent': 1}, 10), [])

    def test_battery_alerts_once_and_requires_recovery_or_charging(self):
        watch = SystemWatch()
        low = {'battery_percent': 15, 'battery_charging': False}
        first = watch.observe(low, 0)
        self.assertEqual(first[0]['kind'], 'battery')
        self.assertIn('15%', first[0]['text'])
        self.assertEqual(watch.observe(low, 1), [])
        self.assertEqual(watch.observe({}, 2), [])
        self.assertEqual(watch.observe({'battery_percent': 20}, 3), [])
        self.assertEqual(watch.observe(low, 4), [])  # Strictly above 20 is recovery.
        watch.observe({'battery_percent': 21}, 5)
        second = watch.observe(low, 6)
        self.assertNotEqual(first[0]['key'], second[0]['key'])
        watch.observe({'battery_charging': True}, 7)
        self.assertEqual(len(watch.observe(low, 8)), 1)

    def test_charging_battery_stays_silent(self):
        watch = SystemWatch()
        self.assertEqual(watch.observe({'battery_percent': 2, 'battery_charging': True}, 0), [])
        self.assertEqual(watch.observe({'battery_percent': 2, 'battery_charging': 'false'}, 1), [])

    def test_disk_alert_requires_confirmed_recovery_before_repeating(self):
        watch = SystemWatch()
        low = {'disk_free_percent': 5}
        first = watch.observe(low, 0)
        self.assertEqual(first[0]['kind'], 'disk')
        self.assertEqual(watch.observe({'disk_free_percent': 1}, 1), [])
        watch.observe({'disk_free_percent': 7.99}, 2)
        self.assertEqual(watch.observe(low, 3), [])
        watch.observe({'disk_free_percent': 8}, 4)
        self.assertNotEqual(watch.observe(low, 5)[0]['key'], first[0]['key'])

    def test_memory_requires_two_consecutive_low_samples(self):
        watch = SystemWatch()
        low = {'memory_available_percent': 5}
        self.assertEqual(watch.observe(low, 0), [])
        self.assertEqual(watch.observe({}, 1), [])  # Missing breaks the streak.
        self.assertEqual(watch.observe(low, 2), [])
        first = watch.observe(low, 3)
        self.assertEqual(first[0]['kind'], 'memory')
        self.assertEqual(watch.observe(low, 4), [])
        watch.observe({'memory_available_percent': 10}, 5)
        self.assertEqual(watch.observe(low, 6), [])
        self.assertEqual(len(watch.observe(low, 7)), 1)

    def test_distinct_resource_transitions_are_independent(self):
        watch = SystemWatch()
        snapshot = {'battery_percent': 10, 'battery_charging': False,
                    'disk_free_percent': 1, 'memory_available_percent': 1}
        self.assertEqual({item['kind'] for item in watch.observe(snapshot, 0)}, {'battery', 'disk'})
        self.assertEqual({item['kind'] for item in watch.observe(snapshot, 1)}, {'memory'})
        self.assertEqual(watch.observe(snapshot, 2), [])

    def test_only_the_current_active_episode_remains_deliverable(self):
        watch = SystemWatch()
        self.assertFalse(watch.is_current('system:disk:1'))
        first = watch.observe({'disk_free_percent': 1}, 0)[0]['key']
        self.assertTrue(watch.is_current(first))
        self.assertFalse(watch.is_current('unknown'))
        self.assertFalse(watch.is_current(None))
        watch.observe({}, 1)
        self.assertTrue(watch.is_current(first))  # Unknown cannot establish recovery.
        watch.observe({'disk_free_percent': 8}, 2)
        self.assertFalse(watch.is_current(first))
        second = watch.observe({'disk_free_percent': 1}, 3)[0]['key']
        self.assertNotEqual(second, first)
        self.assertFalse(watch.is_current(first))
        self.assertTrue(watch.is_current(second))

    def test_threshold_and_clock_validation(self):
        for kwargs in ({'battery_low': True}, {'disk_low': 8, 'disk_recover': 5},
                       {'memory_recover': float('nan')}):
            with self.assertRaises(ValueError):
                SystemWatch(**kwargs)
        watch = SystemWatch()
        watch.observe({}, 1)
        for value in (0, None, True, float('nan')):
            with self.assertRaises(ValueError):
                watch.observe({}, value)


class SystemSamplerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.power = self.root / 'power'
        self.power.mkdir()
        self.meminfo = self.root / 'meminfo'

    def sample(self):
        return sample_system(home=self.root, power_supply_root=self.power,
                             meminfo_path=self.meminfo)

    def battery(self, name, **values):
        folder = self.power / name
        folder.mkdir()
        for key, value in values.items():
            (folder / key).write_text(str(value))

    @patch('proactive.system_watch.shutil.disk_usage', return_value=SimpleNamespace(total=1000, free=40))
    def test_known_local_measurements_and_peripheral_exclusion(self, usage):
        self.battery('A-mouse', type='Battery', scope='Device', capacity=1, status='Discharging')
        self.battery('BAT0', type='Battery', present=1, capacity=14, status='Discharging')
        self.meminfo.write_text('MemTotal: 2000 kB\nMemAvailable: 100 kB\nMemFree: 1 kB\n')
        self.assertEqual(self.sample(), {'battery_percent': 14., 'battery_charging': False,
                                       'disk_free_percent': 4., 'memory_available_percent': 5.})
        usage.assert_called_once_with(self.root)

    @patch('proactive.system_watch.shutil.disk_usage', side_effect=OSError('unavailable'))
    def test_missing_sources_remain_unknown(self, usage):
        self.assertEqual(self.sample(), {'battery_percent': None, 'battery_charging': None,
                                       'disk_free_percent': None, 'memory_available_percent': None})

    @patch('proactive.system_watch.shutil.disk_usage', return_value=SimpleNamespace(total=0, free=0))
    def test_invalid_readings_are_not_coerced_to_zero(self, usage):
        self.battery('BAT0', type='Battery', capacity='NaN', status='Unknown')
        self.meminfo.write_text('MemTotal: invalid kB\nMemAvailable: 50 kB\n')
        self.assertEqual(self.sample(), {'battery_percent': None, 'battery_charging': None,
                                       'disk_free_percent': None, 'memory_available_percent': None})
        self.meminfo.write_text('MemTotal: 100 kB\nMemFree: 1 kB\n')
        self.assertIsNone(self.sample()['memory_available_percent'])

    @patch('proactive.system_watch.shutil.disk_usage', return_value=SimpleNamespace(total=1000, free=900))
    def test_absent_battery_is_skipped_and_charging_is_observed(self, usage):
        self.battery('BAT0', type='Battery', present=0, capacity=1, status='Discharging')
        self.battery('BAT1', type='Battery', present=1, capacity=12, status='Charging')
        self.meminfo.write_text('MemTotal: 100 kB\nMemAvailable: -1 kB\n')
        sample = self.sample()
        self.assertEqual(sample['battery_percent'], 12)
        self.assertTrue(sample['battery_charging'])
        self.assertIsNone(sample['memory_available_percent'])
