"""Offline tests for JARVIS Desktop Awareness skills."""
import json
import unittest
from unittest.mock import AsyncMock, patch

from skills import DesktopSkills, SkillError


SAMPLE_CLIENTS = [
    {
        "address": "0x589612947f90",
        "workspace": {"id": 1, "name": "1"},
        "class": "foot",
        "title": "terminal: bash",
        "focusHistoryID": 0,
        "floating": False,
        "fullscreen": 0,
        "at": [20, 40],
        "size": [800, 600],
    },
    {
        "address": "0x589612948abc",
        "workspace": {"id": 2, "name": "2"},
        "class": "firefox",
        "title": "GitHub - Pull Requests",
        "focusHistoryID": 1,
        "floating": False,
        "fullscreen": 1,
        "at": [0, 0],
        "size": [1920, 1080],
    },
]

SAMPLE_WORKSPACES = [
    {"id": 1, "name": "1", "windows": 1},
    {"id": 2, "name": "2", "windows": 1},
]


class DesktopAwarenessTests(unittest.IsolatedAsyncioTestCase):
    def make_desktop_skills(self):
        skills = DesktopSkills()
        for cmd in (
            'hyprctl', 'grim', 'tesseract', 'ps', 'loginctl',
            'omarchy-brightness-display', 'omarchy-audio-output-volume',
            'notify-send', 'systemctl', 'nmcli', 'rfkill', 'wl-paste', 'wl-copy',
            'omarchy-reminder', 'pactl', 'omarchy-battery-status',
            'omarchy-network-status', 'omarchy-hyprland-monitor-focused',
        ):
            if not skills._commands.get(cmd):
                skills._commands[cmd] = f'/usr/bin/{cmd}'
        return skills

    async def test_list_windows(self):
        skills = self.make_desktop_skills()
        skills._run = AsyncMock(return_value=json.dumps(SAMPLE_CLIENTS))

        # List all windows
        result = await skills.execute('list_windows', {})
        self.assertEqual(result['count'], 2)
        first = result['windows'][0]
        self.assertEqual(first['class'], 'foot')
        self.assertEqual(first['title'], 'terminal: bash')
        self.assertEqual(first['workspace'], 1)
        self.assertTrue(first['focused'])
        self.assertFalse(first['fullscreen'])

        second = result['windows'][1]
        self.assertEqual(second['class'], 'firefox')
        self.assertTrue(second['fullscreen'])

        # Filter by workspace
        filtered = await skills.execute('list_windows', {'workspace': 2})
        self.assertEqual(filtered['count'], 1)
        self.assertEqual(filtered['windows'][0]['class'], 'firefox')

        # Invalid workspace argument
        with self.assertRaises(SkillError):
            await skills.execute('list_windows', {'workspace': 0})

    async def test_focus_window(self):
        skills = self.make_desktop_skills()
        skills._run = AsyncMock(side_effect=[
            json.dumps(SAMPLE_CLIENTS),  # for list_windows inside focus_window
            'ok',                         # for hyprctl dispatch
        ])

        # Match by class
        res = await skills.execute('focus_window', {'query': 'foot'})
        self.assertEqual(res['status'], 'focused')
        self.assertEqual(res['window']['class'], 'foot')
        skills._run.assert_awaited_with(
            skills._commands['hyprctl'], 'dispatch', 'hl.dsp.focus({ window = "address:0x589612947f90" })'
        )

        # Match by title substring
        skills._run = AsyncMock(side_effect=[
            json.dumps(SAMPLE_CLIENTS),
            'ok',
        ])
        res2 = await skills.execute('focus_window', {'query': 'Pull Requests'})
        self.assertEqual(res2['status'], 'focused')
        self.assertEqual(res2['window']['class'], 'firefox')

        # No match error
        skills._run = AsyncMock(return_value=json.dumps(SAMPLE_CLIENTS))
        with self.assertRaisesRegex(SkillError, 'no open window found'):
            await skills.execute('focus_window', {'query': 'nonexistent_app'})

    async def test_list_workspaces(self):
        skills = self.make_desktop_skills()
        skills._run = AsyncMock(side_effect=[
            json.dumps(SAMPLE_WORKSPACES),
            json.dumps({"id": 1, "name": "1"}),
        ])

        res = await skills.execute('list_workspaces', {})
        self.assertEqual(res['active_workspace'], 1)
        self.assertEqual(res['count'], 2)
        self.assertEqual(res['workspaces'][0]['id'], 1)
        self.assertEqual(res['workspaces'][1]['id'], 2)

    async def test_inspect_screen_full_and_active(self):
        skills = self.make_desktop_skills()
        active_window_json = json.dumps({
            "title": "Code Editor",
            "class": "code",
            "workspace": {"id": 1, "name": "1"},
            "at": [100, 200],
            "size": [1200, 800],
        })

        # Test active window inspection with OCR text
        skills._run = AsyncMock(side_effect=[
            active_window_json,  # hyprctl activewindow
            '',                  # grim
            'Error: module not found\nat app.py line 42',  # tesseract OCR
        ])

        with patch.dict('os.environ', {'XDG_RUNTIME_DIR': '/tmp'}):
            res = await skills.execute('inspect_screen', {'region': 'active', 'extract_text': True})
        self.assertEqual(res['status'], 'inspected')
        self.assertEqual(res['region'], 'active')
        self.assertEqual(res['active_window']['class'], 'code')
        self.assertIn('Error: module not found', res['text_content'])
        self.assertTrue(res['screenshot_path'].endswith('.jpg'))

        # Test full screen inspection without text extraction
        skills._run = AsyncMock(side_effect=[
            active_window_json,
            '',  # grim
        ])
        with patch.dict('os.environ', {'XDG_RUNTIME_DIR': '/tmp'}):
            res_full = await skills.execute('inspect_screen', {'region': 'full', 'extract_text': False})
        self.assertEqual(res_full['region'], 'full')
        self.assertIsNone(res_full['text_content'])

    async def test_get_system_resources(self):
        skills = self.make_desktop_skills()
        ps_output = "node 15.2 3.1\ncode 10.1 5.4\nfoot 2.0 0.5\n"
        skills._run = AsyncMock(return_value=ps_output)

        with patch('os.getloadavg', return_value=(1.5, 1.2, 1.0)), \
             patch('os.cpu_count', return_value=8), \
             patch('shutil.disk_usage', return_value=(100 * 1024**3, 40 * 1024**3, 60 * 1024**3)):
            res = await skills.execute('get_system_resources', {})

        self.assertIn('cpu_load_percent', res)
        self.assertEqual(res['cpu_cores'], 8)
        self.assertIn('ram_total_gb', res)
        self.assertIn('ram_used_percent', res)
        self.assertIn('disk_total_gb', res)
        self.assertIsInstance(res['top_processes'], list)
        self.assertEqual(res['top_processes'][0]['name'], 'node')
        self.assertEqual(res['top_processes'][0]['cpu_percent'], 15.2)

    async def test_desktop_context_includes_open_windows_count(self):
        skills = self.make_desktop_skills()
        skills._run = AsyncMock(side_effect=[
            json.dumps({'title': 'Terminal', 'class': 'foot', 'workspace': {'id': 1}}),
            json.dumps({'id': 1, 'name': '1'}),
            'wifi\tHome\t80',
            'Mute: no',
            'front-left: 0% / 50% / 0%',
            'alsa_output.pci',
            'percentage=90\nstate=charging',
            '60%',
            'eDP-1',
            json.dumps(SAMPLE_CLIENTS),  # clients for open_windows_count
        ])

        ctx = await skills.execute('get_desktop_context', {})
        self.assertEqual(ctx['open_windows_count'], 2)


if __name__ == '__main__':
    unittest.main()
