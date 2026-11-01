"""Cold-start dependencies must recover without weakening configured exclusions."""
from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import subprocess
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from core.config import Config
from skills import DesktopSkills, SkillError


def spec(name, adapter, properties=None, required=None):
    return {
        'name': name, 'description': 'Startup recovery fixture ' + name,
        'adapter': adapter,
        'parameters_json_schema': {
            'type': 'object', 'properties': properties or {},
            'required': required or [], 'additionalProperties': False,
        },
    }


class CapabilityStartupRecoveryTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='jarvis-capability-recovery-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.commands = {}
        which = patch('skills.skills.shutil.which', side_effect=self.commands.get)
        which.start()
        self.addCleanup(which.stop)
        self.specs = [
            spec('list_capabilities', 'capabilities.list', {
                'query': {'type': 'string'},
                'limit': {'type': 'integer', 'minimum': 1, 'maximum': 50},
            }),
            spec('gui_list_windows', 'gui.windows'),
            spec('open_application', 'applications.open', {'name': {'type': 'string'}}, ['name']),
            spec('remember_memory', 'memory.remember', {'text': {'type': 'string'}}, ['text']),
            spec('memory_status', 'memory.status'),
            spec('check_vision_hardware', 'vision.check_hardware'),
        ]

    def executable(self, name, *, mode=0o755):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('#!/bin/sh\nexit 0\n')
        path.chmod(mode)
        return str(path)

    def skills(self, *, exclude=False, memory=True, overrides=None):
        directory = self.root / 'manifests'
        directory.mkdir(exist_ok=True)
        (directory / 'startup.json').write_text(json.dumps({'version': 1, 'skills': self.specs}))
        config = Config()
        config.memory.enabled = memory
        config.skills.exclude_unavailable = exclude
        config.commands = overrides or {}
        return DesktopSkills([directory], config=config)

    @staticmethod
    async def catalog(skills, name):
        response = await skills.execute('list_capabilities', {'query': name, 'limit': 50})
        return next(item for item in response['capabilities'] if item['name'] == name)

    async def test_command_missing_at_startup_is_resolved_on_later_use(self):
        skills = self.skills()
        self.assertIsNone(skills._commands['cua-driver'])
        path = self.executable('late-driver')
        self.commands['cua-driver'] = path

        self.assertEqual(skills._command('cua-driver'), path)
        self.assertEqual(skills._commands['cua-driver'], path)

    async def test_readiness_and_execution_agree_after_late_dependency_arrives(self):
        skills = self.skills()
        path = self.executable('driver-ready-later')
        self.commands['cua-driver'] = path
        row = await self.catalog(skills, 'gui_list_windows')
        self.assertTrue(row['available'])

        self.assertEqual(skills._command('cua-driver'), path)
        self.assertEqual(skills._commands['cua-driver'], path)

    async def test_replaced_command_path_does_not_keep_stale_cached_executable(self):
        first = self.executable('driver-first')
        self.commands['cua-driver'] = first
        skills = self.skills()
        self.assertEqual(skills._command('cua-driver'), first)
        Path(first).unlink()
        second = self.executable('driver-after-replacement')
        self.commands['cua-driver'] = second

        self.assertEqual(skills._command('cua-driver'), second)
        self.assertEqual(skills._commands['cua-driver'], second)

    async def test_catalog_restores_only_dependency_excluded_tool_when_ready(self):
        skills = self.skills(exclude=True)
        self.assertNotIn('gui_list_windows', skills._skills)
        row = await self.catalog(skills, 'gui_list_windows')
        self.assertFalse(row['available'])
        self.commands['cua-driver'] = self.executable('late-catalog-driver')

        row = await self.catalog(skills, 'gui_list_windows')

        self.assertTrue(row['available'])
        self.assertTrue(row['exposed'])
        self.assertEqual(row['missing_commands'], [])
        self.assertIn('gui_list_windows', skills._skills)

    async def test_domain_discovery_restores_dependency_excluded_tool(self):
        skills = self.skills(exclude=True)
        self.assertNotIn('gui_list_windows', skills._skills)
        self.commands['cua-driver'] = self.executable('late-discovery-driver')

        result = await skills.execute('discover_domain_tools', {'domain': 'gui'})

        self.assertIn('gui_list_windows', {item['name'] for item in result['tools']})
        self.assertIn('gui_list_windows', skills._skills)

    async def test_direct_execution_restores_dependency_excluded_tool(self):
        skills = self.skills(exclude=True)
        self.commands['cua-driver'] = self.executable('late-direct-driver')
        handler = AsyncMock(return_value={'status': 'success', 'windows': []})
        skills._adapter_gui_list_windows = handler

        result = await skills.execute('gui_list_windows', {})

        self.assertEqual(result['windows'], [])
        handler.assert_awaited_once_with()

    async def test_domain_execution_restores_dependency_excluded_leaf(self):
        skills = self.skills(exclude=True)
        self.commands['cua-driver'] = self.executable('late-domain-driver')
        handler = AsyncMock(return_value={'status': 'success', 'windows': []})
        skills._adapter_gui_list_windows = handler

        result = await skills.execute('execute_domain_tool', {
            'domain': 'gui', 'tool_name': 'gui_list_windows', 'arguments_json': '{}',
        })

        self.assertEqual(result['windows'], [])
        handler.assert_awaited_once_with()

    async def test_memory_configuration_exclusion_is_never_restored(self):
        skills = self.skills(exclude=True, memory=False)
        self.commands['cua-driver'] = self.executable('memory-policy-driver')
        await self.catalog(skills, 'gui_list_windows')

        row = await self.catalog(skills, 'remember_memory')
        self.assertFalse(row['exposed'])
        self.assertFalse(row['available'])
        self.assertNotIn('remember_memory', skills._skills)
        with self.assertRaises(SkillError):
            await skills.execute('remember_memory', {'text': 'Do not store this'})

    async def test_capability_results_provide_exact_domains_for_first_turn_routing(self):
        self.commands['cua-driver'] = self.executable('domain-driver')
        self.commands['gtk-launch'] = self.executable('domain-launcher')
        skills = self.skills()

        gui = await self.catalog(skills, 'gui_list_windows')
        core = await self.catalog(skills, 'open_application')

        self.assertEqual(gui.get('domain'), 'gui')
        self.assertEqual(core.get('domain'), 'core')
        name, args = skills.resolve_domain_call(gui['domain'], gui['name'], '{}')
        self.assertEqual((name, args), ('gui_list_windows', {}))

    async def test_override_that_becomes_executable_later_is_recovered(self):
        override = self.executable('configured-driver', mode=0o644)
        skills = self.skills(overrides={'cua-driver': override})
        self.assertIsNone(skills._commands['cua-driver'])
        Path(override).chmod(0o755)

        self.assertEqual(skills._command('cua-driver'), override)
        self.assertEqual(skills._commands['cua-driver'], override)

    async def test_local_vision_binary_appearing_later_uses_special_resolution(self):
        # Redirect the module-relative install root into the fixture; no installed
        # binary or source tree is changed by this test.
        module_file = self.root / 'isolated-skills' / 'skills.py'
        local = module_file.parent / 'native' / 'bin' / 'vision_ctrl'
        with patch('skills.skills.__file__', str(module_file)):
            skills = self.skills()
            self.assertIsNone(skills._commands['vision_ctrl'])
            local.parent.mkdir(parents=True)
            local.write_text('#!/bin/sh\nexit 0\n')
            local.chmod(0o755)

            self.assertEqual(skills._command('vision_ctrl'), str(local))
            self.assertTrue(os.access(skills._commands['vision_ctrl'], os.X_OK))

    async def test_groq_router_refreshes_schemas_before_selecting_a_command(self):
        from core.agent import LiveVoice

        skills = self.skills()
        voice = LiveVoice(None, skills=skills, config=Config())
        voice.tool_router = SimpleNamespace(declarations=[], route=AsyncMock(return_value=[
            {'name': 'gui_list_windows', 'arguments': {}},
        ]))
        self.commands['cua-driver'] = self.executable('late-router-driver')
        voice._run_skill_call = AsyncMock(return_value={'status': 'success', 'windows': []})
        voice._send_tool_response = AsyncMock()

        await voice._execute_tool(SimpleNamespace(), SimpleNamespace(
            id='late-command', name='route_local_command', args={'command': 'list desktop windows'}))

        self.assertIn('gui_list_windows', {row['name'] for row in voice.tool_router.declarations})
        voice._run_skill_call.assert_awaited_once_with('gui_list_windows', {})
        voice._send_tool_response.assert_awaited_once()


class DesktopStartupEnvironmentTests(unittest.IsolatedAsyncioTestCase):
    async def test_late_desktop_session_is_shared_with_gui_and_verification_helpers(self):
        from skills import ground_truth, system_control

        recovered = {'WAYLAND_DISPLAY': 'wayland-late', 'HYPRLAND_INSTANCE_SIGNATURE': 'late-instance'}
        with patch.dict(os.environ, {'PATH': '/usr/bin'}, clear=True), \
                patch.object(system_control, 'recover_desktop_environment', return_value={}) as probe:
            skills = DesktopSkills()
            self.assertNotIn('WAYLAND_DISPLAY', os.environ)
            probe.return_value = recovered
            await skills.execute('list_capabilities', {'query': 'list windows'})
            self.assertEqual(os.environ['WAYLAND_DISPLAY'], 'wayland-late')
            self.assertEqual(os.environ['HYPRLAND_INSTANCE_SIGNATURE'], 'late-instance')
            self.assertEqual(ground_truth._desktop_env()['WAYLAND_DISPLAY'], 'wayland-late')
            self.assertEqual(os.environ['PATH'], '/usr/bin')

    async def test_native_desktop_env_recovers_late_identifiers_and_filters_credentials(self):
        from skills import system_control

        recovered = {'WAYLAND_DISPLAY': 'wayland-late', 'HYPRLAND_INSTANCE_SIGNATURE': 'late-instance'}
        with patch.dict(os.environ, {'PATH': '/usr/bin', 'GEMINI_API_KEY': 'private'}, clear=True), \
                patch.object(system_control, 'recover_desktop_environment', return_value=recovered):
            env = system_control._desktop_env()
        self.assertEqual(env['WAYLAND_DISPLAY'], 'wayland-late')
        self.assertEqual(env['HYPRLAND_INSTANCE_SIGNATURE'], 'late-instance')
        self.assertNotIn('GEMINI_API_KEY', env)

    async def test_registry_subprocess_uses_recovered_desktop_environment(self):
        from skills import system_control

        recovered = {'WAYLAND_DISPLAY': 'wayland-ready', 'HYPRLAND_INSTANCE_SIGNATURE': 'ready-instance'}
        process = SimpleNamespace(returncode=0, communicate=AsyncMock(return_value=(b'ok', b'')))
        with patch.dict(os.environ, {'PATH': '/usr/bin', 'GROQ_API_KEY': 'private'}, clear=True), \
                patch.object(system_control, 'recover_desktop_environment', return_value=recovered), \
                patch('asyncio.create_subprocess_exec', new=AsyncMock(return_value=process)) as spawn:
            skills = DesktopSkills()
            self.assertEqual(await skills._run('/usr/bin/example'), 'ok')
        env = spawn.call_args.kwargs['env']
        self.assertEqual(env['WAYLAND_DISPLAY'], 'wayland-ready')
        self.assertEqual(env['HYPRLAND_INSTANCE_SIGNATURE'], 'ready-instance')
        self.assertNotIn('GROQ_API_KEY', env)

    def test_desktop_wait_observes_identifiers_that_arrive_after_first_probe(self):
        from core import desktop_session

        clock = [0.0]
        recovered = {'WAYLAND_DISPLAY': 'wayland-ready', 'HYPRLAND_INSTANCE_SIGNATURE': 'ready-instance'}

        def probe(env):
            return recovered if clock[0] >= 0.5 else {}

        def advance(seconds):
            clock[0] += seconds

        with patch.object(desktop_session, 'recover_desktop_environment', side_effect=probe), \
                patch.object(desktop_session.time, 'monotonic', side_effect=lambda: clock[0]), \
                patch.object(desktop_session.time, 'sleep', side_effect=advance):
            exports, missing = desktop_session.wait_for_desktop_environment(
                {'XDG_RUNTIME_DIR': '/example/runtime'}, timeout=5)
        self.assertEqual(exports, recovered)
        self.assertEqual(missing, ())
        self.assertEqual(clock[0], 0.5)

    def test_launcher_exposes_project_clis_and_requests_bounded_desktop_wait(self):
        with tempfile.TemporaryDirectory(prefix='jarvis-launcher-fixture-') as directory:
            root = Path(directory)
            launcher = root / 'run.sh'
            launcher.write_text((Path(__file__).resolve().parents[2] / 'run.sh').read_text())
            scripts = root / '.venv/bin'
            scripts.mkdir(parents=True)
            python = scripts / 'python'
            python.write_text(f'#!{sys.executable}\n' + '''import json, os, shutil, sys
if sys.argv[1:3] == ['-m', 'core.desktop_session']:
    args = sys.argv[3:]
    wait = args[1] if len(args) == 2 and args[0] == '--wait-seconds' else '0'
    print('export JARVIS_TEST_WAIT=' + wait)
else:
    print(json.dumps({'cli': shutil.which('jarvis-project-only-fixture'),
                      'wait': os.getenv('JARVIS_TEST_WAIT')}))
''')
            python.chmod(0o755)
            cli = scripts / 'jarvis-project-only-fixture'
            cli.write_text('#!/bin/sh\nexit 0\n')
            cli.chmod(0o755)
            result = subprocess.run(['/usr/bin/bash', str(launcher), '--check'],
                env={**os.environ, 'PATH': '/usr/bin:/bin'}, capture_output=True,
                text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            output = json.loads(result.stdout)
            self.assertEqual(output['cli'], str(cli))
            self.assertEqual(output['wait'], '5')
