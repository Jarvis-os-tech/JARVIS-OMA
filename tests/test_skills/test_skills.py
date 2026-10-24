"""Offline tests for dynamic Omarchy skill discovery and policy adapters."""
import asyncio
import json
import os
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from skills import DesktopSkills, SkillError
from connectors import internet_search as web_search


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
    async def test_legacy_memory_schema_cannot_block_voice_startup(self):
        skills = DesktopSkills()

        class BrokenMemory:
            def context(self):
                raise KeyError('evidence_refs')

        skills._memory = BrokenMemory()
        self.assertEqual(skills.memory_context(), '')

    async def test_enter_standby_requests_voice_transition(self):
        skills = DesktopSkills()
        requested = []
        skills.on_standby_request = lambda: requested.append(True) or {
            'status': 'standby_requested', 'wake_phrase': 'Hey Jarvis'}
        result = await skills.execute('enter_standby', {})
        self.assertEqual(result['status'], 'standby_requested')
        self.assertEqual(requested, [True])

    async def test_microphone_mute_permission_is_blocked(self):
        skills = DesktopSkills()
        with self.assertRaisesRegex(SkillError, 'invalid arguments'):
            await skills.execute('control_microphone', {'action': 'mute'})
        with self.assertRaisesRegex(SkillError, 'not permitted'):
            await skills._adapter_control_microphone('toggle')

    async def test_brave_search_returns_bounded_public_sources(self):
        payload = {'web': {'results': [
            {'title': 'Example <b>result</b>', 'url': 'https://example.org/fact',
             'description': 'A <em>source</em> summary'},
            {'title': 'Duplicate', 'url': 'https://example.org/fact'},
            {'title': 'Bad link', 'url': 'javascript:alert(1)'},
        ]}}
        with patch.object(web_search, '_get_json', new_callable=AsyncMock,
                          return_value=payload) as get_json:
            result = await web_search.brave_search('test search', api_key='test-key')
        self.assertEqual(result['provider'], 'Brave Search')
        self.assertEqual(result['sources'], [{
            'title': 'Example result', 'url': 'https://example.org/fact',
            'snippet': 'A source summary'}])
        self.assertIn('X-Subscription-Token', get_json.call_args.kwargs['headers'])

    async def test_brave_search_uses_private_connector_credential_store(self):
        payload = {'web': {'results': [
            {'title': 'Result', 'url': 'https://example.org/result'}]}}
        with patch.object(web_search.credentials, 'get', return_value='private-key') as secret, \
                patch.object(web_search, '_get_json', new_callable=AsyncMock,
                             return_value=payload) as get_json:
            self.assertTrue(web_search.brave_available())
            await web_search.brave_search('example')
        secret.assert_called_with('BRAVE_SEARCH_API_KEY')
        self.assertEqual(get_json.call_args.kwargs['headers']['X-Subscription-Token'],
                         'private-key')

    async def test_current_query_does_not_fall_back_to_encyclopedia(self):
        self.assertFalse(web_search.encyclopedia_eligible('What is the stock price today?'))
        self.assertTrue(web_search.encyclopedia_eligible('How do stars form?'))
        with patch.object(web_search, 'brave_available', return_value=False), \
                patch('google.genai.Client') as client, \
                patch.object(web_search, 'wikipedia_search', new_callable=AsyncMock) as wiki:
            # A real exception carrying the HTTP status exercises quota fallback.
            class QuotaError(Exception):
                code = 429
            client.return_value.aio.__aenter__.return_value.models.generate_content.side_effect = QuotaError()
            with self.assertRaisesRegex(SkillError, 'BRAVE_SEARCH_API_KEY'):
                await DesktopSkills(api_key='test-key').execute(
                    'internet_search', {'query': 'stock price today'})
            wiki.assert_not_awaited()

    async def test_stable_query_uses_wikipedia_after_grounding_quota(self):
        class QuotaError(Exception):
            code = 429
        wiki_result = {'answer': 'Encyclopedia background for: stars',
                       'sources': [{'title': 'Star', 'url': 'https://en.wikipedia.org/wiki/Star',
                                    'snippet': 'Astronomical object'}],
                       'provider': 'Wikipedia'}
        with patch.object(web_search, 'brave_available', return_value=False), \
                patch('google.genai.Client') as client, \
                patch.object(web_search, 'wikipedia_search', new_callable=AsyncMock,
                             return_value=wiki_result) as wiki:
            client.return_value.aio.__aenter__.return_value.models.generate_content = AsyncMock(
                side_effect=QuotaError())
            result = await DesktopSkills(api_key='test-key').execute(
                'internet_search', {'query': 'How do stars form?'})
            self.assertEqual(result, wiki_result)
            wiki.assert_awaited_once()

    async def test_internet_search_returns_grounded_sources_to_voice(self):
        result = SimpleNamespace(
            text='Current answer',
            candidates=[SimpleNamespace(grounding_metadata=SimpleNamespace(
                grounding_chunks=[SimpleNamespace(web=SimpleNamespace(
                    title='Official source', uri='https://example.org/fact'))]))])
        generate = AsyncMock(return_value=result)

        class FakeAio:
            async def __aenter__(self):
                return SimpleNamespace(models=SimpleNamespace(generate_content=generate))

            async def __aexit__(self, *args):
                pass

        with patch('google.genai.Client', return_value=SimpleNamespace(aio=FakeAio())):
            output = await DesktopSkills(api_key='test-key').execute(
                'internet_search', {'query': 'current fact'})
        self.assertEqual(output['answer'], 'Current answer')
        self.assertEqual(output['sources'], [
            {'title': 'Official source', 'url': 'https://example.org/fact'}])
        self.assertEqual(generate.await_args.kwargs['model'], 'gemini-3.8-flash')

    async def test_grounded_search_tries_next_account_after_quota(self):
        class QuotaError(Exception):
            code = 429

        result = SimpleNamespace(text='Verified answer', candidates=[SimpleNamespace(
            grounding_metadata=SimpleNamespace(grounding_chunks=[SimpleNamespace(
                web=SimpleNamespace(title='Source', uri='https://example.org/fact'))]))])
        attempts = []

        class FakeAio:
            def __init__(self, key):
                async def generate_content(**kwargs):
                    attempts.append((key, kwargs['model']))
                    if key == 'first-key':
                        raise QuotaError()
                    return result
                self.models = SimpleNamespace(generate_content=generate_content)

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

        with patch.object(web_search, 'brave_available', return_value=False), \
                patch('google.genai.Client', side_effect=lambda api_key: SimpleNamespace(
                    aio=FakeAio(api_key))):
            skills = DesktopSkills(api_key=['first-key', 'second-key'])
            output = await skills.execute('internet_search', {'query': 'price today'})
            self.assertEqual(output['answer'], 'Verified answer')
            self.assertEqual(attempts, [('first-key', 'gemini-3.8-flash'),
                                        ('second-key', 'gemini-3.8-flash')])
            attempts.clear()
            await skills.execute('internet_search', {'query': 'price now'})
            self.assertEqual(attempts, [('second-key', 'gemini-3.8-flash')])

    async def test_grounded_search_tries_next_model_when_unavailable(self):
        class ModelUnavailable(Exception):
            code = 404

        result = SimpleNamespace(text='Verified answer', candidates=[SimpleNamespace(
            grounding_metadata=SimpleNamespace(grounding_chunks=[SimpleNamespace(
                web=SimpleNamespace(title='Source', uri='https://example.org/fact'))]))])
        attempts = []

        async def generate_content(**kwargs):
            attempts.append(kwargs['model'])
            if len(attempts) == 1:
                raise ModelUnavailable()
            return result

        class FakeAio:
            async def __aenter__(self):
                return SimpleNamespace(models=SimpleNamespace(generate_content=generate_content))

            async def __aexit__(self, *args):
                pass

        with patch.object(web_search, 'brave_available', return_value=False), \
                patch('google.genai.Client', return_value=SimpleNamespace(aio=FakeAio())):
            output = await DesktopSkills(api_key=['test-key']).execute(
                'internet_search', {'query': 'price today'})
        self.assertEqual(output['model'], 'gemini-3.7-flash')
        self.assertEqual(attempts, ['gemini-3.8-flash', 'gemini-3.7-flash'])

    async def test_grounded_search_does_not_multiply_requests_after_quota(self):
        class QuotaError(Exception):
            code = 429

        result = SimpleNamespace(text='Verified answer', candidates=[SimpleNamespace(
            grounding_metadata=SimpleNamespace(grounding_chunks=[SimpleNamespace(
                web=SimpleNamespace(title='Source', uri='https://example.org/fact'))]))])
        attempts = []

        async def generate_content(**kwargs):
            attempts.append(kwargs['model'])
            if kwargs['model'].startswith('gemini-3.'):
                raise QuotaError()
            return result

        class FakeAio:
            async def __aenter__(self):
                return SimpleNamespace(models=SimpleNamespace(generate_content=generate_content))

            async def __aexit__(self, *args):
                pass

        with patch.object(web_search, 'brave_available', return_value=False), \
                patch('google.genai.Client', return_value=SimpleNamespace(aio=FakeAio())):
            skills = DesktopSkills(api_key=['test-key'])
            with self.assertRaisesRegex(SkillError, 'quota'):
                await skills.execute('internet_search', {'query': 'price today'})
        self.assertEqual(attempts, ['gemini-3.8-flash'])
        self.assertGreater(skills._search_key_cooldown['test-key'], 0)

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
        with patch('skills.skills.system_control.set_brightness', new_callable=AsyncMock,
                   return_value={'status': 'success'}) as control:
            result = await skills.execute('make_it_brighter', {'direction': 'raise', 'amount': 7})
        self.assertEqual(result['amount'], 7)
        control.assert_awaited_once_with(percent=None, direction='raise', amount=7)
        skills._run.assert_not_awaited()

    async def test_native_todo_lifecycle_and_duplicate_title(self):
        skills = self.make_desktop_skills()
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(skills, '_todo_path', return_value=Path(directory) / 'omarchy/todos.json'), \
             patch.object(skills, '_notify_quickshell_todos', new_callable=AsyncMock) as notify:
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
            self.assertEqual(notify.await_count, 6)

    async def test_todo_refresh_uses_quickshell_ipc_and_falls_back(self):
        skills = self.make_desktop_skills()
        skills._run = AsyncMock(side_effect=[SkillError('first instance unavailable'), ''])
        with patch('skills.skills.shutil.which', return_value='/usr/bin/qs'):
            refreshed = await skills._notify_quickshell_todos()
        self.assertTrue(refreshed)
        self.assertEqual(skills._run.await_count, 2)
        first = skills._run.await_args_list[0]
        second = skills._run.await_args_list[1]
        self.assertIn('dejan94.todos', first.args)
        self.assertIn('refresh', first.args)
        self.assertIn('--any-display', second.args)

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
             patch.object(skills, '_launch', new=AsyncMock()) as launch, \
             patch('skills.ground_truth.verify_window_state', new=AsyncMock(
                 return_value={'verified': True, 'details': {'matched_window': {'class': 'firefox'}}})):
            result = await skills.execute('open_application', {'name': 'Firefox'})
            self.assertEqual(result['application'], 'Firefox')
            self.assertTrue(result['ground_truth_verified'])
            self.assertFalse(result['self_healed'])
            self.assertEqual(len(result['attempts']), 1)
            launch.assert_awaited_once_with(skills._commands['gtk-launch'], 'firefox.desktop')
            with self.assertRaises(SkillError):
                await skills.execute('open_application', {'name': 'firefox; shutdown'})

    async def test_application_adapter_rejects_unverified_launch(self):
        skills = self.make_desktop_skills()
        failed = {'verified': False, 'reason': 'not found', 'details': {}}
        with patch.object(skills, '_applications', return_value={'foot.desktop': 'Foot'}), \
             patch.object(skills, '_launch', new=AsyncMock()), \
             patch('skills.ground_truth.verify_window_state', new=AsyncMock(return_value=failed)), \
             patch('skills.ground_truth.verify_process_state', new=AsyncMock(return_value=failed)):
            with self.assertRaisesRegex(SkillError, 'failed after one self-healing retry'):
                await skills.execute('open_application', {'name': 'Foot'})

    async def test_application_launch_self_heals_desktop_session_and_retries_once(self):
        skills = self.make_desktop_skills()
        failed = {'verified': False, 'reason': 'not found', 'details': {}}
        verified = {'verified': True, 'reason': None,
                    'details': {'matched_window': {'class': 'firefox'}}}
        with patch.object(skills, '_applications', return_value={'firefox.desktop': 'Firefox'}), \
             patch.object(skills, '_launch', new=AsyncMock()) as launch, \
             patch('skills.ground_truth.verify_window_state', new=AsyncMock(
                 side_effect=[failed, verified])), \
             patch('skills.ground_truth.verify_process_state', new=AsyncMock(
                 return_value=failed)), \
             patch('core.desktop_session.recover_desktop_environment',
                   return_value={'WAYLAND_DISPLAY': 'wayland-1'}), \
             patch.dict(os.environ, {}, clear=False):
            os.environ.pop('WAYLAND_DISPLAY', None)
            result = await skills.execute('open_application', {'name': 'Firefox'})
        self.assertTrue(result['self_healed'])
        self.assertEqual(len(result['attempts']), 2)
        self.assertEqual(launch.await_count, 2)
        self.assertEqual(os.environ.get('WAYLAND_DISPLAY'), 'wayland-1')

    async def test_service_launches_desktop_apps_through_uwsm(self):
        skills = self.make_desktop_skills()
        process = SimpleNamespace(wait=AsyncMock(return_value=0))
        with patch.dict(os.environ, {'INVOCATION_ID': 'service-run'}), \
             patch('shutil.which', side_effect=lambda name: f'/usr/bin/{name}'), \
             patch('asyncio.create_subprocess_exec', new=AsyncMock(return_value=process)) as launch:
            await skills._launch('/usr/bin/example-app', '--flag')
        command = launch.await_args.args
        self.assertEqual(command, (
            '/usr/bin/uwsm', 'app', '-s', 'a', '-t', 'scope', '-S', 'both', '--',
            '/usr/bin/example-app', '--flag'))

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
        dispatched = {'status': 'unverified', 'action': 'sleep', 'verified': False}
        with patch('skills.skills.system_control.control_power',
                   new=AsyncMock(return_value=dispatched)) as control:
            result = await skills.execute('system_power', {'action': 'sleep'})
        self.assertEqual(result, dispatched)
        control.assert_awaited_once_with('sleep')

        with self.assertRaises(SkillError):
            await skills.execute('system_power', {'action': 'shutdown'})

    async def test_network_adapters(self):
        skills = self.make_desktop_skills()
        skills._run = AsyncMock(side_effect=AssertionError('legacy mock-only branch must not run'))
        with patch('skills.skills.system_control.control_wifi', new=AsyncMock(
                return_value={'status': 'success', 'wifi': {'enabled': True}})) as wifi_control:
            wifi = await skills.execute('toggle_wifi', {'action': 'status'})
        self.assertTrue(wifi['wifi']['enabled'])
        wifi_control.assert_awaited_once_with('status', ssid=None, password=None)
        with patch('skills.skills.system_control.control_bluetooth', new=AsyncMock(
                return_value={'status': 'success', 'bluetooth': {'powered': True}})) as bt_control:
            bt = await skills.execute('toggle_bluetooth', {'action': 'status'})
        self.assertTrue(bt['bluetooth']['powered'])
        bt_control.assert_awaited_once_with('status', device=None)

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
            '55%', 'eDP-1',
            json.dumps([{'class': 'code'}]),
        ])
        context = await skills.execute('get_desktop_context', {})
        self.assertEqual(context['active_window']['class'], 'code')
        self.assertEqual(context['workspace']['id'], 2)
        self.assertFalse(context['audio']['muted'])
        self.assertTrue(context['battery']['available'])
        self.assertEqual(context['open_windows_count'], 1)

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
            self.assertEqual(skills._read_todos()['activeTab'], 'ongoing')

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
            self.assertEqual(skills._read_todos()['activeTab'], 'complete')

            # Filter by status
            ongoing = await skills.execute('list_todos', {'status': 'ongoing'})
            self.assertEqual(ongoing['count'], 0)
            comp = await skills.execute('list_todos', {'status': 'complete'})
            self.assertEqual(comp['count'], 1)

            # Test move_todo
            moved = await skills.execute('move_todo', {'task': task_id, 'status': 'backlog'})
            self.assertEqual(moved['todo']['status'], 'backlog')
            self.assertFalse(moved['todo']['completed'])
            self.assertEqual(skills._read_todos()['activeTab'], 'backlog')

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

    async def test_filesystem_manifest_discovery_and_adapter_declarations(self):
        skills = self.make_desktop_skills()
        names = {item['name'] for item in skills.declarations}
        expected_fs_skills = {
            'list_files', 'read_file', 'write_file', 'append_file', 'edit_file',
            'make_directory', 'move_path', 'copy_path', 'trash_path', 'delete_path',
            'inspect_file', 'search_files', 'search_file_content',
        }
        for expected in expected_fs_skills:
            self.assertIn(expected, names)
        # Check adapter availability for filesystem skills (no external commands needed)
        avail = skills.adapter_availability()
        self.assertTrue(avail.get('filesystem.list'))
        self.assertTrue(avail.get('filesystem.read'))
        self.assertTrue(avail.get('filesystem.write'))
        self.assertTrue(avail.get('filesystem.append'))
        self.assertTrue(avail.get('filesystem.delete'))
        self.assertTrue(avail.get('filesystem.info'))
        self.assertTrue(avail.get('filesystem.grep'))

    async def test_file_discovery_defaults_to_home_when_voice_omits_path(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'voice-probe.txt').write_text('Jarvis file access works', encoding='utf-8')
            skills = self.make_desktop_skills()
            with patch('skills.skills.Path.home', return_value=root):
                listed = await skills.execute('list_files', {})
                named = await skills.execute('search_files', {'query': 'voice-probe'})
                content = await skills.execute('search_file_content', {'query': 'access works'})
            self.assertEqual(listed['path'], str(root))
            self.assertIn(str(root / 'voice-probe.txt'), named['matches'])
            self.assertTrue(content['matches'])


if __name__ == '__main__':
    unittest.main()
