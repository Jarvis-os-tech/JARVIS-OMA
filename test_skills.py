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
                    'grim', 'systemctl', 'nmcli', 'rfkill', 'wl-paste', 'wl-copy',
                    'omarchy-reminder'):
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

    async def test_native_todo_lifecycle_and_duplicate_title(self):
        skills = self.make_desktop_skills()
        with tempfile.TemporaryDirectory() as directory, patch.object(skills, '_todo_path', return_value=Path(directory) / 'omarchy/todos.json'):
            first = await skills.execute('create_todo', {'title': 'Plan trip', 'priority': 'high'})
            second = await skills.execute('create_todo', {'title': 'Plan trip'})
            self.assertNotEqual(first['todo']['id'], second['todo']['id'])
            with self.assertRaisesRegex(SkillError, 'multiple todos'):
                await skills.execute('complete_todo', {'task': 'Plan trip'})
            task_id = first['todo']['id']
            await skills.execute('move_todo', {'task': task_id, 'status': 'backlog'})
            listed = await skills.execute('list_todos', {'query': 'trip', 'status': 'backlog'})
            self.assertEqual(listed['count'], 1)
            await skills.execute('update_todo', {'task': task_id, 'priority': 'critical'})
            await skills.execute('complete_todo', {'task': task_id})
            cleared = await skills.execute('clear_completed_todos', {})
            self.assertEqual(cleared['count'], 1)
            remaining = await skills.execute('list_todos', {})
            self.assertEqual(remaining['count'], 1)

    async def test_reminder_list_is_not_truncated_and_cancel_uses_native_id(self):
        skills = self.make_desktop_skills()
        skills._commands['omarchy-reminder'] = '/usr/bin/omarchy-reminder'
        skills._commands['systemctl'] = '/usr/bin/systemctl'
        timer = 'omarchy-reminder-30m-123456.timer'
        payload = json.dumps({'reminders': [{'timer': timer, 'message': 'x' * 700}]})
        skills._run = AsyncMock(side_effect=[payload, payload, ''])
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {'XDG_RUNTIME_DIR': directory}):
            listed = await skills.execute('list_reminders', {})
            self.assertEqual(len(listed['reminders'][0]['message']), 700)
            cancelled = await skills.execute('cancel_reminder', {'timer': timer})
            self.assertEqual(cancelled['status'], 'cancelled')

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

    async def test_reminder_adapters(self):
        skills = self.make_desktop_skills()
        skills._run = AsyncMock(return_value='')

        # Test create_reminder
        res = await skills.execute('create_reminder', {'minutes': 15, 'message': 'Take a break'})
        self.assertEqual(res, {'status': 'created', 'minutes': 15, 'message': 'Take a break', 'system': 'omarchy'})
        skills._run.assert_awaited_with(skills._commands['omarchy-reminder'], '15', 'Take a break')

        # Test default message
        skills._run.reset_mock()
        res = await skills.execute('create_reminder', {'minutes': 5})
        self.assertEqual(res['message'], 'Reminder')
        skills._run.assert_awaited_with(skills._commands['omarchy-reminder'], '5', 'Reminder')

        # Test invalid minutes
        with self.assertRaises(SkillError):
            await skills.execute('create_reminder', {'minutes': 0})
        with self.assertRaises(SkillError):
            await skills.execute('create_reminder', {'minutes': 10081})
        with self.assertRaises(SkillError):
            await skills.execute('create_reminder', {'minutes': True})

        # Test list_reminders
        sample_json = json.dumps({'count': 1, 'active': True, 'tooltip': '1 reminder', 'reminders': [{'unit': 'u1', 'timer': 'omarchy-reminder-5m-1.timer'}]})
        skills._run = AsyncMock(return_value=sample_json)
        list_res = await skills.execute('list_reminders', {})
        self.assertEqual(list_res['count'], 1)
        skills._run.assert_awaited_with(skills._commands['omarchy-reminder'], 'show', '--json', max_output=65536)

        # Test list_reminders invalid JSON
        skills._run = AsyncMock(return_value='not-json')
        with self.assertRaises(SkillError):
            await skills.execute('list_reminders', {})

        # Test clear_reminders
        skills._run = AsyncMock(return_value='')
        clear_res = await skills.execute('clear_reminders', {})
        self.assertEqual(clear_res, {'status': 'cleared', 'system': 'omarchy'})
        skills._run.assert_awaited_with(skills._commands['omarchy-reminder'], 'clear')

        # Test cancel_reminder
        sample_list = json.dumps({'count': 1, 'active': True, 'reminders': [{'timer': 'omarchy-reminder-5m-123.timer'}]})
        skills._run = AsyncMock(side_effect=[sample_list, ''])
        cancel_res = await skills.execute('cancel_reminder', {'timer': 'omarchy-reminder-5m-123.timer'})
        self.assertEqual(cancel_res['status'], 'cancelled')

    async def test_desktop_context_returns_structured_snapshot(self):
        skills = self.make_desktop_skills()
        for command in ('pactl', 'omarchy-battery-status', 'omarchy-network-status',
                        'omarchy-brightness-display', 'omarchy-hyprland-monitor-focused'):
            skills._commands[command] = f'/usr/bin/{command}'
        skills._run = AsyncMock(side_effect=[
            json.dumps({'title': 'Editor', 'class': 'code', 'workspace': {'id': 2, 'name': '2'}}),
            json.dumps({'id': 2, 'name': '2'}), 'wifi\tHome\t80', 'Mute: no',
            'front-left: 0% / 42% / 0%', 'alsa_output.test', 'percentage=75\nstate=charging',
            '55%', 'eDP-1'])
        context = await skills.execute('get_desktop_context', {})
        self.assertEqual(context['active_window']['class'], 'code')
        self.assertEqual(context['workspace']['id'], 2)
        self.assertFalse(context['audio']['muted'])
        self.assertTrue(context['battery']['available'])

    async def test_todo_adapters(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        with patch.dict(os.environ, {'XDG_STATE_HOME': temporary.name}):
            skills = self.make_desktop_skills()

            # Test initial list is empty
            initial = await skills.execute('list_todos', {})
            self.assertEqual(initial['count'], 0)
            self.assertEqual(initial['tasks'], [])

            # Test create_todo
            created = await skills.execute('create_todo', {
                'title': 'Test Task',
                'description': 'Details here',
                'priority': 'high'
            })
            self.assertEqual(created['status'], 'created')
            task = created['todo']
            self.assertEqual(task['title'], 'Test Task')
            self.assertEqual(task['description'], 'Details here')
            self.assertEqual(task['priority'], 'high')
            self.assertEqual(task['status'], 'ongoing')
            self.assertFalse(task['completed'])
            task_id = task['id']

            # Test list_todos with task
            listed = await skills.execute('list_todos', {})
            self.assertEqual(listed['count'], 1)
            self.assertEqual(listed['tasks'][0]['id'], task_id)

            # Test search query in list_todos
            found = await skills.execute('list_todos', {'query': 'details'})
            self.assertEqual(found['count'], 1)
            not_found = await skills.execute('list_todos', {'query': 'nonexistent'})
            self.assertEqual(not_found['count'], 0)

            # Test update_todo
            updated = await skills.execute('update_todo', {
                'task': task_id,
                'title': 'Updated Title',
                'priority': 'critical'
            })
            self.assertEqual(updated['todo']['title'], 'Updated Title')
            self.assertEqual(updated['todo']['priority'], 'critical')

            # Test complete_todo
            completed = await skills.execute('complete_todo', {'task': 'Updated Title', 'completed': True})
            self.assertEqual(completed['status'], 'completed')
            self.assertTrue(completed['todo']['completed'])
            self.assertEqual(completed['todo']['status'], 'complete')

            # Filter by status
            ongoing = await skills.execute('list_todos', {'status': 'ongoing'})
            self.assertEqual(ongoing['count'], 0)
            comp = await skills.execute('list_todos', {'status': 'complete'})
            self.assertEqual(comp['count'], 1)

            # Test move_todo
            moved = await skills.execute('move_todo', {'task': task_id, 'status': 'backlog'})
            self.assertEqual(moved['todo']['status'], 'backlog')
            self.assertFalse(moved['todo']['completed'])

            # Move back to complete to test clear_completed_todos
            await skills.execute('move_todo', {'task': task_id, 'status': 'complete'})
            cleared = await skills.execute('clear_completed_todos', {})
            self.assertEqual(cleared['count'], 1)
            after_clear = await skills.execute('list_todos', {})
            self.assertEqual(after_clear['count'], 0)

            # Test delete_todo
            created2 = await skills.execute('create_todo', {'title': 'To Delete'})
            del_res = await skills.execute('delete_todo', {'task': created2['todo']['id']})
            self.assertEqual(del_res['status'], 'deleted')
            self.assertEqual((await skills.execute('list_todos', {}))['count'], 0)

            # Validation errors
            with self.assertRaises(SkillError):
                await skills.execute('create_todo', {'title': ''})
            with self.assertRaises(SkillError):
                await skills.execute('create_todo', {'title': 'A' * 201})
            with self.assertRaises(SkillError):
                await skills.execute('create_todo', {'title': 'Bad', 'priority': 'invalid'})
            with self.assertRaises(SkillError):
                await skills.execute('delete_todo', {'task': 'does-not-exist'})


if __name__ == '__main__':
    unittest.main()
