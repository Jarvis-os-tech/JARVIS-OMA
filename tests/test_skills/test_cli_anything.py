import asyncio
import json
import unittest
from unittest.mock import AsyncMock, patch

from skills.skills import DesktopSkills, SkillError


class CLIAnythingSkillTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        # Instantiate skills with mock commands so cli-hub is considered present
        with patch.object(DesktopSkills, '_discover_commands', return_value={'cli-hub': '/usr/bin/cli-hub'}):
            self.skills = DesktopSkills()
            self.skills._commands['cli-hub'] = '/usr/bin/cli-hub'
        self.hub = self.skills._command('cli-hub')
        self.max_out = self.skills._CLI_HUB_MAX_OUTPUT

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

    async def test_cli_hub_list_returns_parsed_json(self):
        with patch.object(self.skills, '_run', new_callable=AsyncMock) as mock_run:
            mock_run.return_value = json.dumps({'categories': ['image', 'video']})
            result = await self.skills.execute('cli_hub_list', {})
            self.assertEqual(result, {'categories': ['image', 'video']})
            mock_run.assert_called_once_with(self.hub, 'list', '--json', max_output=self.max_out)

        with patch.object(self.skills, '_run', new_callable=AsyncMock) as mock_run:
            mock_run.return_value = json.dumps({'categories': ['image']})
            result = await self.skills.execute('cli_hub_list', {'category': 'image'})
            self.assertEqual(result, {'categories': ['image']})
            mock_run.assert_called_once_with(self.hub, 'list', '-c', 'image', '--json', max_output=self.max_out)

    async def test_cli_hub_search_validates_query(self):
        with patch.object(self.skills, '_run', new_callable=AsyncMock) as mock_run:
            mock_run.return_value = json.dumps([{'name': 'gimp'}])
            result = await self.skills.execute('cli_hub_search', {'query': 'photo'})
            self.assertEqual(result, [{'name': 'gimp'}])
            mock_run.assert_called_once_with(self.hub, 'search', 'photo', '--json', max_output=self.max_out)

        with self.assertRaises(SkillError):
            await self.skills.execute('cli_hub_search', {'query': '   '})

    async def test_cli_hub_info_validates_name(self):
        with patch.object(self.skills, '_run', new_callable=AsyncMock) as mock_run:
            mock_run.return_value = json.dumps([{'name': 'gimp', 'version': '1.0'}])
            result = await self.skills.execute('cli_hub_info', {'name': 'gimp'})
            self.assertEqual(result, {'name': 'gimp', 'version': '1.0'})
            mock_run.assert_called_once_with(self.hub, 'search', 'gimp', '--json', max_output=self.max_out)

        with self.assertRaises(SkillError):
            await self.skills.execute('cli_hub_info', {'name': ''})

    async def test_cli_hub_install_validates_name_and_dry_run(self):
        with patch.object(self.skills, '_run', new_callable=AsyncMock) as mock_run:
            mock_run.return_value = json.dumps([{'name': 'gimp', 'install_cmd': 'pip install gimp', 'entry_point': 'cli-anything-gimp', 'requires': None, 'version': '1.0'}])
            result = await self.skills.execute('cli_hub_install', {'name': 'gimp', 'dry_run': True})
            self.assertEqual(result['status'], 'dry_run')
            self.assertEqual(result['name'], 'gimp')
            self.assertEqual(result['install_cmd'], 'pip install gimp')

        with patch.object(self.skills, '_run', new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = [
                json.dumps([{'name': 'gimp', 'install_cmd': 'pip install gimp'}]),
                'installed output'
            ]
            result = await self.skills.execute('cli_hub_install', {'name': 'gimp', 'dry_run': False})
            self.assertEqual(result['status'], 'installed')
            self.assertEqual(result['name'], 'gimp')

    async def test_cli_hub_uninstall_validates_name(self):
        with patch.object(self.skills, '_run', new_callable=AsyncMock) as mock_run:
            mock_run.return_value = 'uninstalled output'
            result = await self.skills.execute('cli_hub_uninstall', {'name': 'gimp'})
            self.assertEqual(result['status'], 'uninstalled')
            self.assertEqual(result['name'], 'gimp')
            mock_run.assert_called_once_with(self.hub, 'uninstall', 'gimp', timeout=60, max_output=10000)

    async def test_cli_hub_launch_validates_name(self):
        with patch.object(self.skills, '_run', new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = [
                json.dumps([{'name': 'gimp', 'entry_point': 'cli-anything-gimp'}]),
                json.dumps({'res': 'ok'})
            ]
            result = await self.skills.execute('cli_hub_launch', {'name': 'gimp', 'args': ['--json'], 'json_output': True})
            self.assertEqual(result, {'res': 'ok'})

        with patch.object(self.skills, '_run', new_callable=AsyncMock) as mock_run, \
             patch.object(self.skills, '_launch', new_callable=AsyncMock) as mock_launch:
            mock_run.return_value = json.dumps([{'name': 'gimp', 'entry_point': 'cli-anything-gimp'}])
            result = await self.skills.execute('cli_hub_launch', {'name': 'gimp', 'args': ['file.png']})
            self.assertEqual(result, {'status': 'launched', 'cli': 'cli-anything-gimp'})
            mock_launch.assert_called_once_with('cli-anything-gimp', 'file.png')

    async def test_cli_hub_matrix_list_returns_parsed_json(self):
        with patch.object(self.skills, '_run', new_callable=AsyncMock) as mock_run:
            mock_run.return_value = json.dumps({'matrices': ['video-creation']})
            result = await self.skills.execute('cli_hub_matrix_list', {})
            self.assertEqual(result, {'matrices': ['video-creation']})
            mock_run.assert_called_once_with(self.hub, 'matrix', 'list', '--json', max_output=self.max_out)

    async def test_cli_hub_matrix_preflight_handles_exit_3(self):
        with patch.object(self.skills, '_run', new_callable=AsyncMock) as mock_run:
            mock_run.return_value = json.dumps({'summary': {'gaps': ['ffmpeg']}})
            result = await self.skills.execute('cli_hub_matrix_preflight', {'matrix': 'video-creation'})
            self.assertEqual(result['status'], 'partial')

    async def test_cli_hub_matrix_install_validates_params(self):
        with patch.object(self.skills, '_run', new_callable=AsyncMock) as mock_run:
            mock_run.return_value = json.dumps({'summary': {}})
            result = await self.skills.execute('cli_hub_matrix_install', {
                'matrix': 'video-creation',
                'capability': 'video.edit',
                'dry_run': True
            })
            self.assertEqual(result['status'], 'dry_run')
            mock_run.assert_called_once_with(
                self.hub, 'matrix', 'install', 'video-creation',
                '--capability', 'video.edit', '--dry-run', '--json',
                timeout=300, max_output=self.max_out, ok_codes=(0, 3)
            )

    def test_skills_excluded_when_cli_hub_missing(self):
        """Verify graceful degradation when cli-hub is not installed."""
        with patch.object(DesktopSkills, '_discover_commands', return_value={'cli-hub': None}):
            skills = DesktopSkills(exclude_unavailable=True)
            for skill_name, spec in skills._skills.items():
                self.assertFalse(spec['adapter'].startswith('cli_hub.'))


if __name__ == '__main__':
    unittest.main()
