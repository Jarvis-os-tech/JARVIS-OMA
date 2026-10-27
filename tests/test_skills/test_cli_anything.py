"""Offline unit tests for the CLI-Anything skills.

The adapters drive the real `cli-hub` executable, whose option surface is
narrower than it looks: `info`, `install` and `uninstall` accept no options
at all. The regression tests below pin the exact argv each adapter builds so
a future edit cannot reintroduce an unsupported flag.
"""
import json
import os
import re
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from skills.skills import DesktopSkills, SkillError

pytestmark = pytest.mark.offline

CLI_HUB_BINARY = Path(sys.executable).parent / 'cli-hub'


def _find_cli_hub():
    """Locate the real cli-hub executable, if this environment has one."""
    if CLI_HUB_BINARY.is_file() and os.access(CLI_HUB_BINARY, os.X_OK):
        return str(CLI_HUB_BINARY)
    from shutil import which
    return which('cli-hub')


class CLIAnythingSkillTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        # Instantiate skills with mock commands so cli-hub is considered present
        with patch.object(DesktopSkills, '_discover_commands', return_value={'cli-hub': '/usr/bin/cli-hub'}):
            self.skills = DesktopSkills()

    # ── manifest ───────────────────────────────────────────────────

    def test_manifest_loads_valid_schema(self):
        """Ensure all 9 cli-anything skills are loaded."""
        expected_skills = [
            'cli_hub_list',
            'cli_hub_search',
            'cli_hub_info',
            'cli_hub_install',
            'cli_hub_uninstall',
            'cli_hub_launch',
            'cli_hub_matrix_list',
            'cli_hub_matrix_preflight',
            'cli_hub_matrix_install',
        ]
        for skill in expected_skills:
            self.assertIn(skill, self.skills._skills)
            spec = self.skills._skills[skill]
            self.assertTrue(spec['adapter'].startswith('cli_hub.'))

    def test_all_adapters_approved(self):
        """Verify that all adapters for cli-anything skills are declared in ADAPTERS."""
        for skill_name, spec in self.skills._skills.items():
            if spec['adapter'].startswith('cli_hub.'):
                self.assertIn(spec['adapter'], DesktopSkills.ADAPTERS)
                adapter_method = DesktopSkills.ADAPTERS[spec['adapter']]
                self.assertTrue(hasattr(self.skills, adapter_method))

    def test_skills_excluded_when_cli_hub_missing(self):
        """Verify graceful degradation when cli-hub is not installed."""
        with patch.object(DesktopSkills, '_discover_commands', return_value={'cli-hub': None}):
            skills = DesktopSkills(exclude_unavailable=True)
            for skill_name, spec in skills._skills.items():
                self.assertFalse(spec['adapter'].startswith('cli_hub.'))

    def test_capability_context_lists_cli_hub_group(self):
        """The compact context names the domain; schemas remain discoverable."""
        context = self.skills.capability_context()
        self.assertIn('cli_anything (', context)
        self.assertNotIn('cli_hub_matrix_preflight', context)
        self.assertIn('cli_hub_matrix_preflight', {item['name'] for item in self.skills.declarations})

    # ── list / search ──────────────────────────────────────────────

    async def test_cli_hub_list_returns_parsed_json(self):
        with patch.object(self.skills, '_run', new_callable=AsyncMock) as mock_run:
            mock_run.return_value = json.dumps([{'name': 'gimp', 'category': 'image'}])
            result = await self.skills.execute('cli_hub_list', {})
            self.assertEqual(result, [{'name': 'gimp', 'category': 'image'}])
            mock_run.assert_called_once_with(
                '/usr/bin/cli-hub', 'list', '--json',
                max_output=DesktopSkills._CLI_HUB_MAX_OUTPUT)

        with patch.object(self.skills, '_run', new_callable=AsyncMock) as mock_run:
            mock_run.return_value = json.dumps([{'name': 'gimp', 'category': 'image'}])
            result = await self.skills.execute('cli_hub_list', {'category': 'image'})
            self.assertEqual(result, [{'name': 'gimp', 'category': 'image'}])
            mock_run.assert_called_once_with(
                '/usr/bin/cli-hub', 'list', '-c', 'image', '--json',
                max_output=DesktopSkills._CLI_HUB_MAX_OUTPUT)

    async def test_cli_hub_list_reports_invalid_json_as_skill_error(self):
        """A truncated payload must surface as SkillError, not a raw JSONDecodeError."""
        with patch.object(self.skills, '_run', new_callable=AsyncMock) as mock_run:
            mock_run.return_value = '[{"name": "gimp", "descri'
            with self.assertRaisesRegex(SkillError, 'invalid JSON'):
                await self.skills.execute('cli_hub_list', {})

    async def test_cli_hub_search_validates_query(self):
        with patch.object(self.skills, '_run', new_callable=AsyncMock) as mock_run:
            mock_run.return_value = json.dumps([{'name': 'gimp'}])
            result = await self.skills.execute('cli_hub_search', {'query': 'photo'})
            self.assertEqual(result, [{'name': 'gimp'}])
            mock_run.assert_called_once_with(
                '/usr/bin/cli-hub', 'search', 'photo', '--json',
                max_output=DesktopSkills._CLI_HUB_MAX_OUTPUT)

        with self.assertRaises(SkillError):
            await self.skills.execute('cli_hub_search', {'query': '   '})
        with self.assertRaises(SkillError):
            await self.skills.execute('cli_hub_search', {'query': 'x' * 201})

    # ── info ───────────────────────────────────────────────────────

    async def test_cli_hub_info_returns_registry_record(self):
        """`cli-hub info` has no --json, so the record comes from `search --json`."""
        record = {'name': 'gimp', 'display_name': 'GIMP', 'requires': 'gimp',
                  'entry_point': 'cli-anything-gimp', 'install_cmd': 'pip install ...'}
        with patch.object(self.skills, '_run', new_callable=AsyncMock) as mock_run:
            mock_run.return_value = json.dumps([record])
            result = await self.skills.execute('cli_hub_info', {'name': 'gimp'})
            self.assertEqual(result, record)
            mock_run.assert_called_once_with(
                '/usr/bin/cli-hub', 'search', 'gimp', '--json',
                max_output=DesktopSkills._CLI_HUB_MAX_OUTPUT)

    async def test_cli_hub_info_rejects_unknown_cli(self):
        """A fuzzy search hit must not be mistaken for the requested CLI."""
        with patch.object(self.skills, '_run', new_callable=AsyncMock) as mock_run:
            mock_run.return_value = json.dumps([{'name': 'gimp-batch'}])
            with self.assertRaisesRegex(SkillError, 'not found in registry'):
                await self.skills.execute('cli_hub_info', {'name': 'gimp'})

    async def test_cli_hub_info_validates_name(self):
        with self.assertRaises(SkillError):
            await self.skills.execute('cli_hub_info', {'name': ''})
        with self.assertRaises(SkillError):
            await self.skills.execute('cli_hub_info', {'name': 'x' * 101})

    async def test_cli_hub_name_rejects_shell_metacharacters(self):
        """Names are passed as argv, but the registry lookup must stay well-typed."""
        for hostile in ('gimp; rm -rf /', '$(whoami)', 'a b', '../etc/passwd'):
            with self.assertRaises(SkillError):
                await self.skills.execute('cli_hub_info', {'name': hostile})

    # ── install / uninstall ────────────────────────────────────────

    async def test_cli_hub_install_dry_run_returns_plan_without_installing(self):
        """`cli-hub install` has no --dry-run; the plan comes from the registry."""
        record = {'name': 'gimp', 'install_cmd': 'pip install git+...',
                  'entry_point': 'cli-anything-gimp', 'requires': 'gimp', 'version': '1.0.0'}
        with patch.object(self.skills, '_run', new_callable=AsyncMock) as mock_run:
            mock_run.return_value = json.dumps([record])
            result = await self.skills.execute('cli_hub_install', {'name': 'gimp', 'dry_run': True})
            self.assertEqual(result['status'], 'dry_run')
            self.assertEqual(result['install_cmd'], 'pip install git+...')
            self.assertEqual(result['entry_point'], 'cli-anything-gimp')
            # Only the registry lookup may run; nothing may be installed.
            mock_run.assert_called_once_with(
                '/usr/bin/cli-hub', 'search', 'gimp', '--json',
                max_output=DesktopSkills._CLI_HUB_MAX_OUTPUT)

    async def test_cli_hub_install_runs_plain_cli_hub_install(self):
        """The install command must not carry --json or --dry-run."""
        record = {'name': 'gimp', 'install_cmd': 'pip install git+...', 'entry_point': 'cli-anything-gimp'}
        with patch.object(self.skills, '_run', new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = [json.dumps([record]), 'installed gimp']
            result = await self.skills.execute('cli_hub_install', {'name': 'gimp'})
            self.assertEqual(result['status'], 'installed')
            self.assertEqual(result['name'], 'gimp')
            self.assertEqual(mock_run.call_args_list[1],
                             unittest.mock.call('/usr/bin/cli-hub', 'install', 'gimp',
                                                 timeout=120, max_output=10000))

    async def test_cli_hub_install_validates_name(self):
        with self.assertRaises(SkillError):
            await self.skills.execute('cli_hub_install', {'name': ''})
        with self.assertRaises(SkillError):
            await self.skills.execute('cli_hub_install', {'name': 'x' * 101})

    async def test_cli_hub_uninstall_runs_plain_cli_hub_uninstall(self):
        """`cli-hub uninstall` accepts no options, so no --json may be passed."""
        with patch.object(self.skills, '_run', new_callable=AsyncMock) as mock_run:
            mock_run.return_value = 'uninstalled gimp'
            result = await self.skills.execute('cli_hub_uninstall', {'name': 'gimp'})
            self.assertEqual(result['status'], 'uninstalled')
            mock_run.assert_called_once_with('/usr/bin/cli-hub', 'uninstall', 'gimp',
                                              timeout=60, max_output=10000)

    async def test_cli_hub_uninstall_validates_name(self):
        with self.assertRaises(SkillError):
            await self.skills.execute('cli_hub_uninstall', {'name': ''})

    # ── launch ─────────────────────────────────────────────────────

    async def test_cli_hub_launch_uses_registry_entry_point(self):
        """26 of 103 registry CLIs have an entry point that is not cli-anything-<name>."""
        record = {'name': 'feishu', 'entry_point': 'lark-cli'}
        with patch.object(self.skills, '_run', new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = [json.dumps([record]), '{"ok": true}']
            result = await self.skills.execute(
                'cli_hub_launch', {'name': 'feishu', 'args': ['--json'], 'json_output': True})
            self.assertEqual(result, {'ok': True})
            self.assertEqual(mock_run.call_args_list[1],
                             unittest.mock.call('lark-cli', '--json', timeout=60,
                                                 max_output=DesktopSkills._CLI_HUB_MAX_OUTPUT))

    async def test_cli_hub_launch_does_not_duplicate_json_flag(self):
        record = {'name': 'gimp', 'entry_point': 'cli-anything-gimp'}
        with patch.object(self.skills, '_run', new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = [json.dumps([record]), '{"ok": true}']
            await self.skills.execute(
                'cli_hub_launch', {'name': 'gimp', 'args': ['--json'], 'json_output': True})
            argv = mock_run.call_args_list[1].args
            self.assertEqual(argv.count('--json'), 1)

    async def test_cli_hub_launch_json_output_is_honoured_with_other_args(self):
        """json_output=True must not be silently dropped when args lack --json."""
        record = {'name': 'gimp', 'entry_point': 'cli-anything-gimp'}
        with patch.object(self.skills, '_run', new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = [json.dumps([record]), '{"ok": true}']
            result = await self.skills.execute(
                'cli_hub_launch', {'name': 'gimp', 'args': ['project', 'list'], 'json_output': True})
            self.assertEqual(result, {'ok': True})
            self.assertEqual(mock_run.call_args_list[1].args,
                             ('cli-anything-gimp', 'project', 'list', '--json'))

    async def test_cli_hub_launch_without_args_runs_one_shot(self):
        """No args pins the spec's current routing: `_run` with a 60s budget.

        Upstream treats a bare `cli-anything-<name>` as an interactive REPL
        session, so this path blocks for the CLI's lifetime (60s cap) instead
        of detaching. Left as-is because it matches the agreed spec contract;
        see the launch-routing note in the handover.
        """
        record = {'name': 'gimp', 'entry_point': 'cli-anything-gimp'}
        with patch.object(self.skills, '_run', new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = [json.dumps([record]), 'plain text']
            result = await self.skills.execute('cli_hub_launch', {'name': 'gimp'})
            self.assertEqual(result, {'output': 'plain text'})

    async def test_cli_hub_launch_with_args_launches_detached(self):
        record = {'name': 'gimp', 'entry_point': 'cli-anything-gimp'}
        with patch.object(self.skills, '_run', new_callable=AsyncMock) as mock_run, \
                patch.object(self.skills, '_launch', new_callable=AsyncMock) as mock_launch:
            mock_run.return_value = json.dumps([record])
            result = await self.skills.execute('cli_hub_launch', {'name': 'gimp', 'args': ['file.png']})
            self.assertEqual(result, {'status': 'launched', 'cli': 'cli-anything-gimp'})
            mock_launch.assert_called_once_with('cli-anything-gimp', 'file.png')

    async def test_cli_hub_launch_validates_name(self):
        with self.assertRaises(SkillError):
            await self.skills.execute('cli_hub_launch', {'name': ''})

    async def test_cli_hub_launch_missing_binary_is_a_skill_error(self):
        """A missing harness binary must be a SkillError, never a raw FileNotFoundError."""
        record = {'name': 'gimp', 'entry_point': 'cli-anything-gimp'}
        with patch.object(self.skills, '_run', new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = [json.dumps([record]),
                                    SkillError('cli-anything-gimp is not installed on this desktop')]
            with self.assertRaises(SkillError):
                await self.skills.execute('cli_hub_launch', {'name': 'gimp'})

    async def test_run_reports_missing_binary_as_skill_error(self):
        """The shared runner must not leak FileNotFoundError to skill callers."""
        with self.assertRaisesRegex(SkillError, 'is not installed on this desktop'):
            await self.skills._run('cli-anything-definitely-not-installed')

    async def test_launch_reports_missing_binary_as_skill_error(self):
        with self.assertRaisesRegex(SkillError, 'is not installed on this desktop'):
            await self.skills._launch('cli-anything-definitely-not-installed')

    # ── matrix ─────────────────────────────────────────────────────

    async def test_cli_hub_matrix_list_returns_parsed_json(self):
        with patch.object(self.skills, '_run', new_callable=AsyncMock) as mock_run:
            mock_run.return_value = json.dumps([{'name': 'video-creation'}])
            result = await self.skills.execute('cli_hub_matrix_list', {})
            self.assertEqual(result, [{'name': 'video-creation'}])
            mock_run.assert_called_once_with(
                '/usr/bin/cli-hub', 'matrix', 'list', '--json',
                max_output=DesktopSkills._CLI_HUB_MAX_OUTPUT)

    async def test_cli_hub_matrix_preflight_accepts_exit_3(self):
        """cli-hub exits 3 for capability gaps but still prints the JSON report."""
        payload = {'matrix': {'name': 'video-creation'},
                   'summary': {'capabilities': 19, 'gaps': 5}}
        with patch.object(self.skills, '_run', new_callable=AsyncMock) as mock_run:
            mock_run.return_value = json.dumps(payload)
            result = await self.skills.execute('cli_hub_matrix_preflight',
                                                {'matrix': 'video-creation'})
            self.assertEqual(result['status'], 'partial')
            self.assertEqual(result['summary']['gaps'], 5)
            self.assertEqual(mock_run.call_args.kwargs.get('ok_codes'), (0, 3))

    async def test_cli_hub_matrix_preflight_status_complete_without_gaps(self):
        payload = {'matrix': {'name': 'video-creation'}, 'summary': {'gaps': 0}}
        with patch.object(self.skills, '_run', new_callable=AsyncMock) as mock_run:
            mock_run.return_value = json.dumps(payload)
            result = await self.skills.execute('cli_hub_matrix_preflight',
                                                {'matrix': 'video-creation'})
            self.assertEqual(result['status'], 'complete')

    async def test_cli_hub_matrix_preflight_builds_expected_argv(self):
        with patch.object(self.skills, '_run', new_callable=AsyncMock) as mock_run:
            mock_run.return_value = json.dumps({'summary': {'gaps': 0}})
            await self.skills.execute('cli_hub_matrix_preflight',
                                       {'matrix': 'video-creation',
                                        'capability': 'text.transcribe',
                                        'fix_hints': True})
            self.assertEqual(mock_run.call_args.args,
                             ('/usr/bin/cli-hub', 'matrix', 'preflight', 'video-creation',
                              '-c', 'text.transcribe', '--fix-hints', '--json'))

    async def test_cli_hub_matrix_preflight_validates_matrix(self):
        with self.assertRaises(SkillError):
            await self.skills.execute('cli_hub_matrix_preflight', {'matrix': ''})

    async def test_cli_hub_matrix_install_validates_params(self):
        with patch.object(self.skills, '_run', new_callable=AsyncMock) as mock_run:
            mock_run.return_value = json.dumps({'summary': {'failed': 0}})
            result = await self.skills.execute('cli_hub_matrix_install', {
                'matrix': 'video-creation',
                'capability': 'video.edit',
                'dry_run': True
            })
            self.assertEqual(result['status'], 'dry_run')
            self.assertEqual(mock_run.call_args.args,
                             ('/usr/bin/cli-hub', 'matrix', 'install', 'video-creation',
                              '--capability', 'video.edit', '--dry-run', '--json'))
            self.assertEqual(mock_run.call_args.kwargs.get('ok_codes'), (0, 3))

    async def test_cli_hub_matrix_install_reports_partial_failure(self):
        with patch.object(self.skills, '_run', new_callable=AsyncMock) as mock_run:
            mock_run.return_value = json.dumps({'summary': {'installed': 3, 'failed': 1}})
            result = await self.skills.execute('cli_hub_matrix_install',
                                                {'matrix': 'video-creation'})
            self.assertEqual(result['status'], 'partial')

    async def test_cli_hub_matrix_install_validates_matrix(self):
        with self.assertRaises(SkillError):
            await self.skills.execute('cli_hub_matrix_install', {'matrix': ''})


class CLIAnythingOptionSurfaceTests(unittest.TestCase):
    """Guard the adapters against flags the real cli-hub does not declare.

    `cli-hub info`, `install` and `uninstall` accept no options at all, and
    `--dry-run` exists only on `matrix install`. Asking for `--help` needs no
    network access, so this check stays offline and drift-proof.
    """

    @classmethod
    def setUpClass(cls):
        cls.binary = _find_cli_hub()
        if not cls.binary:
            raise unittest.SkipTest('cli-hub is not installed')
        cls.help_text = {}

    def _declared_options(self, command):
        """Return the option names a cli-hub subcommand declares."""
        key = tuple(command)
        if key not in self.help_text:
            result = subprocess.run([self.binary, *command, '--help'],
                                    capture_output=True, text=True, timeout=60)
            self.help_text[key] = result.stdout
        return set(re.findall(r'(?<![\w-])(--?[A-Za-z][A-Za-z0-9-]*)', self.help_text[key]))

    def _assert_options_declared(self, command, argv):
        declared = self._declared_options(command)
        for token in argv:
            if token.startswith('-') and token != '-':
                self.assertIn(token, declared,
                              f'cli-hub {" ".join(command)} does not declare {token}')

    def test_cli_hub_info_declares_no_options(self):
        """`cli-hub info --json` fails with exit 2 on the real executable."""
        declared = self._declared_options(['info'])
        self.assertNotIn('--json', declared)
        self.assertNotIn('--dry-run', declared)

    def test_cli_hub_install_declares_no_options(self):
        declared = self._declared_options(['install'])
        self.assertNotIn('--json', declared)
        self.assertNotIn('--dry-run', declared)

    def test_cli_hub_uninstall_declares_no_options(self):
        declared = self._declared_options(['uninstall'])
        self.assertNotIn('--json', declared)

    def test_cli_hub_list_and_search_declare_json(self):
        for command in (['list'], ['search'], ['matrix', 'list']):
            self.assertIn('--json', self._declared_options(command))

    def test_matrix_install_declares_dry_run(self):
        declared = self._declared_options(['matrix', 'install'])
        self.assertIn('--dry-run', declared)
        self.assertIn('--json', declared)


if __name__ == '__main__':
    unittest.main()
