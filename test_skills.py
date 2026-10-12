"""Offline tests for dynamic Omarchy skill discovery and policy adapters."""
import asyncio
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from skills import DesktopSkills, SkillError


def manifest(skills):
    return {'version': 1, 'skills': skills}


def spec(name='apps', adapter='applications.list', properties=None, required=None):
    return {
        'name': name,
        'description': 'Test dynamic skill.',
        'adapter': adapter,
        'parameters_json_schema': {
            'type': 'object', 'properties': properties or {},
            'required': required or [], 'additionalProperties': False,
        },
    }


class DynamicManifestTests(unittest.IsolatedAsyncioTestCase):
    def make_desktop_skills(self, manifest_dirs=None, **kwargs):
        skills = DesktopSkills(manifest_dirs=manifest_dirs, **kwargs)
        for cmd in ('omarchy-brightness-display', 'gtk-launch', 'hyprctl', 'notify-send',
                    'omarchy-audio-output-volume', 'omarchy-launch-webapp', 'loginctl',
                    'grim', 'systemctl', 'nmcli', 'rfkill', 'wl-paste', 'wl-copy'):
            if not skills._commands.get(cmd):
                skills._commands[cmd] = f'/usr/bin/{cmd}'
        return skills

    def make_skills(self, *documents):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        directory = Path(temporary.name)
        for index, document in enumerate(documents):
            (directory / f'{index}.json').write_text(json.dumps(document), encoding='utf-8')
        return self.make_desktop_skills([directory])

    async def test_discovers_skill_names_and_schemas_from_manifests(self):
        skills = self.make_skills(manifest([spec('second'), spec('first')]))
        self.assertEqual([item['name'] for item in skills.declarations], ['second', 'first'])
        self.assertFalse(skills.declarations[0]['parameters_json_schema']['additionalProperties'])

    async def test_duplicate_dynamic_names_fail_closed(self):
        with self.assertRaisesRegex(SkillError, 'duplicate'):
            self.make_skills(manifest([spec('same')]), manifest([spec('same')]))

    async def test_unknown_adapter_and_malformed_schema_fail_closed(self):
        with self.assertRaisesRegex(SkillError, 'unapproved adapter'):
            self.make_skills(manifest([spec(adapter='shell.command')]))
        bad = spec()
        bad['parameters_json_schema']['additionalProperties'] = True
        with self.assertRaisesRegex(SkillError, 'strict object'):
            self.make_skills(manifest([bad]))

    async def test_runtime_schema_rejects_extra_wrong_and_boolean_integer_args(self):
        integer = {'type': 'integer', 'minimum': 1, 'maximum': 10}
        skills = self.make_skills(manifest([
            spec('brightness', 'display.brightness',
                 {'direction': {'type': 'string', 'enum': ['raise', 'lower']},
                  'amount': integer}, ['direction', 'amount'])]))
        for args in (
            {'direction': 'raise'},
            {'direction': 'sideways', 'amount': 2},
            {'direction': 'raise', 'amount': True},
            {'direction': 'raise', 'amount': 11},
            {'direction': 'raise', 'amount': 2, 'extra': 'no'},
        ):
            with self.subTest(args=args), self.assertRaisesRegex(SkillError, 'invalid arguments'):
                await skills.execute('brightness', args)

    async def test_dynamic_name_routes_to_reviewed_adapter(self):
        skills = self.make_skills(manifest([
            spec('make_it_brighter', 'display.brightness',
                 {'direction': {'type': 'string', 'enum': ['raise', 'lower']},
                  'amount': {'type': 'integer', 'minimum': 1, 'maximum': 25}},
                 ['direction'])]))
        skills._run = AsyncMock(return_value='')
        result = await skills.execute('make_it_brighter', {'direction': 'raise', 'amount': 7})
        self.assertEqual(result['amount'], 7)
        skills._run.assert_awaited_once_with(
            skills._commands['omarchy-brightness-display'], '+7%')

    async def test_url_adapter_rejects_unsafe_schemes_and_credentials(self):
        skills = self.make_desktop_skills()
        for url in ('file:///etc/passwd', 'javascript:alert(1)',
                    'https://user:secret@example.com/', 'http://127.0.0.1/admin',
                    'http://[::1]/', 'https://localhost/private'):
            with self.subTest(url=url), self.assertRaises(SkillError):
                await skills.execute('open_website', {'url': url})

    async def test_application_adapter_launches_only_catalogued_exact_match(self):
        skills = self.make_desktop_skills()
        with patch.object(skills, '_applications', return_value={'firefox.desktop': 'Firefox'}), \
             patch.object(skills, '_launch', new=AsyncMock()) as launch:
            result = await skills.execute('open_application', {'name': 'Firefox'})
            self.assertEqual(result['application'], 'Firefox')
            launch.assert_awaited_once_with(skills._commands['gtk-launch'], 'firefox.desktop')
            with self.assertRaises(SkillError):
                await skills.execute('open_application', {'name': 'firefox; shutdown'})

    async def test_notification_uses_custom_app_name(self):
        skills = self.make_desktop_skills(app_name='Friday')
        skills._run = AsyncMock(return_value='')
        result = await skills.execute('show_notification', {'title': 'Alert', 'message': 'Done'})
        self.assertEqual(result['status'], 'shown')
        skills._run.assert_awaited_once_with(
            skills._commands['notify-send'], '--app-name=Friday', 'Alert', 'Done')

    async def test_lock_screen_adapter(self):
        skills = self.make_desktop_skills()
        skills._run = AsyncMock(return_value='')
        result = await skills.execute('lock_screen', {})
        self.assertEqual(result['status'], 'locked')
        skills._run.assert_awaited_once_with(skills._commands['loginctl'], 'lock-session')

    async def test_take_screenshot_adapter(self):
        skills = self.make_desktop_skills()
        skills._run = AsyncMock(return_value='')
        result = await skills.execute('take_screenshot', {'region': 'full'})
        self.assertEqual(result['status'], 'captured')
        self.assertTrue(result['path'].endswith('.png'))
        skills._run.assert_awaited_once()

    async def test_manage_window_adapter(self):
        skills = self.make_desktop_skills()
        skills._run = AsyncMock(return_value='')
        result = await skills.execute('manage_window', {'action': 'fullscreen'})
        self.assertEqual(result['status'], 'done')
        skills._run.assert_awaited_once_with(
            skills._commands['hyprctl'], 'dispatch', 'hl.dsp.window.fullscreen({ mode = "fullscreen" })')

        with self.assertRaises(SkillError):
            await skills.execute('manage_window', {'action': 'destroy_everything'})

    async def test_switch_workspace_adapter(self):
        skills = self.make_desktop_skills()
        skills._run = AsyncMock(return_value='')
        result = await skills.execute('switch_workspace', {'workspace': 2})
        self.assertEqual(result['status'], 'switched')
        skills._run.assert_awaited_once_with(
            skills._commands['hyprctl'], 'dispatch', 'hl.dsp.focus({ workspace = "2" })')

    async def test_system_power_adapter_rejects_dangerous_actions(self):
        skills = self.make_desktop_skills()
        skills._run = AsyncMock(return_value='')
        result = await skills.execute('system_power', {'action': 'sleep'})
        self.assertEqual(result['status'], 'done')
        skills._run.assert_awaited_once_with(skills._commands['systemctl'], 'suspend')

        with self.assertRaises(SkillError):
            await skills.execute('system_power', {'action': 'shutdown'})

    async def test_network_adapters(self):
        skills = self.make_desktop_skills()
        skills._run = AsyncMock(return_value='enabled\n')
        wifi = await skills.execute('toggle_wifi', {'action': 'status'})
        self.assertEqual(wifi['wifi'], 'enabled')

        skills._run = AsyncMock(return_value='Soft blocked: no\n')
        bt = await skills.execute('toggle_bluetooth', {'action': 'status'})
        self.assertEqual(bt['bluetooth'], 'on')

    async def test_clipboard_adapters(self):
        skills = self.make_desktop_skills()
        skills._run = AsyncMock(return_value='hello clipboard')
        read_res = await skills.execute('read_clipboard', {})
        self.assertEqual(read_res['content'], 'hello clipboard')

        with patch('asyncio.create_subprocess_exec') as mock_exec:
            proc = AsyncMock()
            proc.communicate = AsyncMock(return_value=(b'', b''))
            proc.returncode = 0
            mock_exec.return_value = proc
            write_res = await skills.execute('write_clipboard', {'content': 'new text'})
            self.assertEqual(write_res['status'], 'written')
            self.assertEqual(write_res['length'], 8)

    async def test_graceful_degradation_removes_missing_command_skills(self):
        # Create manifest with one app skill (no commands needed) and one fake skill requiring nonexistent cmd
        test_doc = manifest([
            spec('apps', 'applications.list'),
            spec('fake', 'system.lock'),
        ])
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        path = Path(temp_dir.name) / 'skills.json'
        path.write_text(json.dumps(test_doc), encoding='utf-8')

        with patch('shutil.which', return_value=None):
            # loginctl is missing, so fake is removed, but apps remains because it needs no commands
            skills = DesktopSkills([Path(temp_dir.name)], exclude_unavailable=True)
            self.assertIn('apps', [d['name'] for d in skills.declarations])
            self.assertNotIn('fake', [d['name'] for d in skills.declarations])

    def test_xdg_data_dirs_application_discovery(self):
        skills = DesktopSkills()
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        app_dir = Path(temp_dir.name) / 'applications'
        app_dir.mkdir(parents=True)
        desktop_file = app_dir / 'custom-app.desktop'
        desktop_file.write_text(
            "[Desktop Entry]\nType=Application\nName=Custom App\nExec=custom-app\n",
            encoding='utf-8'
        )

        with patch.dict(os.environ, {'XDG_DATA_DIRS': temp_dir.name}):
            apps = skills._applications()
            self.assertIn('custom-app.desktop', apps)
            self.assertEqual(apps['custom-app.desktop'], 'Custom App')


if __name__ == '__main__':
    unittest.main()
