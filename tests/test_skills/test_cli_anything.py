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
            mock_run.assert_called_once_with('/usr/bin/cli-hub', 'list', '--json', max_output=10000)

        with patch.object(self.skills, '_run', new_callable=AsyncMock) as mock_run:
            mock_run.return_value = json.dumps({'categories': ['image']})
            result = await self.skills.execute('cli_hub_list', {'category': 'image'})
            self.assertEqual(result, {'categories': ['image']})
            mock_run.assert_called_once_with('/usr/bin/cli-hub', 'list', '-c', 'image', '--json', max_output=10000)

    async def test_cli_hub_search_validates_query(self):
        with patch.object(self.skills, '_run', new_callable=AsyncMock) as mock_run:
            mock_run.return_value = json.dumps({'results': [{'name': 'gimp'}]})
            result = await self.skills.execute('cli_hub_search', {'query': 'photo'})
            self.assertEqual(result, {'results': [{'name': 'gimp'}]})
            mock_run.assert_called_once_with('/usr/bin/cli-hub', 'search', 'photo', '--json', max_output=10000)

        with self.assertRaises(SkillError):
            await self.skills.execute('cli_hub_search', {'query': '   '})

    async def test_cli_hub_info_validates_name(self):
        with patch.object(self.skills, '_run', new_callable=AsyncMock) as mock_run:
            mock_run.return_value = json.dumps({'name': 'gimp', 'version': '1.0'})
            result = await self.skills.execute('cli_hub_info', {'name': 'gimp'})
            self.assertEqual(result, {'name': 'gimp', 'version': '1.0'})
            mock_run.assert_called_once_with('/usr/bin/cli-hub', 'info', 'gimp', '--json', max_output=10000)

        with self.assertRaises(SkillError):
            await self.skills.execute('cli_hub_info', {'name': ''})

    async def test_cli_hub_install_validates_name_and_dry_run(self):
        with patch.object(self.skills, '_run', new_callable=AsyncMock) as mock_run:
            mock_run.return_value = json.dumps({'status': 'installed'})
            result = await self.skills.execute('cli_hub_install', {'name': 'gimp', 'dry_run': True})
            self.assertEqual(result, {'status': 'installed'})
            mock_run.assert_called_once_with('/usr/bin/cli-hub', 'install', 'gimp', '--dry-run', '--json', timeout=120, max_output=10000)

    async def test_cli_hub_uninstall_validates_name(self):
        with patch.object(self.skills, '_run', new_callable=AsyncMock) as mock_run:
            mock_run.return_value = json.dumps({'status': 'uninstalled'})
            result = await self.skills.execute('cli_hub_uninstall', {'name': 'gimp'})
            self.assertEqual(result, {'status': 'uninstalled'})
            mock_run.assert_called_once_with('/usr/bin/cli-hub', 'uninstall', 'gimp', '--json', timeout=60, max_output=10000)

    async def test_cli_hub_launch_validates_name(self):
        with patch.object(self.skills, '_run', new_callable=AsyncMock) as mock_run:
            mock_run.return_value = json.dumps({'res': 'ok'})
            result = await self.skills.execute('cli_hub_launch', {'name': 'gimp', 'args': ['--json'], 'json_output': True})
            self.assertEqual(result, {'res': 'ok'})
            mock_run.assert_called_once_with('cli-anything-gimp', '--json', '--json', timeout=60, max_output=10000)

        with patch.object(self.skills, '_launch', new_callable=AsyncMock) as mock_launch:
            result = await self.skills.execute('cli_hub_launch', {'name': 'gimp', 'args': ['file.png']})
            self.assertEqual(result, {'status': 'launched', 'cli': 'cli-anything-gimp'})
            mock_launch.assert_called_once_with('cli-anything-gimp', 'file.png')

    async def test_cli_hub_matrix_list_returns_parsed_json(self):
        with patch.object(self.skills, '_run', new_callable=AsyncMock) as mock_run:
            mock_run.return_value = json.dumps({'matrices': ['video-creation']})
            result = await self.skills.execute('cli_hub_matrix_list', {})
            self.assertEqual(result, {'matrices': ['video-creation']})
            mock_run.assert_called_once_with('/usr/bin/cli-hub', 'matrix', 'list', '--json', max_output=10000)

    async def test_cli_hub_matrix_preflight_handles_exit_3(self):
        with patch.object(self.skills, '_run', new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = SkillError('Exit code 3: partial support')
            result = await self.skills.execute('cli_hub_matrix_preflight', {'matrix': 'video-creation'})
            self.assertEqual(result['status'], 'partial')

    async def test_cli_hub_matrix_install_validates_params(self):
        with patch.object(self.skills, '_run', new_callable=AsyncMock) as mock_run:
            mock_run.return_value = json.dumps({'status': 'installed'})
            result = await self.skills.execute('cli_hub_matrix_install', {
                'matrix': 'video-creation',
                'capability': 'video.edit',
                'dry_run': True
            })
            self.assertEqual(result, {'status': 'installed'})
            mock_run.assert_called_once_with(
                '/usr/bin/cli-hub', 'matrix', 'install', 'video-creation',
                '--capability', 'video.edit', '--dry-run', '--json',
                timeout=300, max_output=20000
            )

    def test_skills_excluded_when_cli_hub_missing(self):
        """Verify graceful degradation when cli-hub is not installed."""
        with patch.object(DesktopSkills, '_discover_commands', return_value={'cli-hub': None}):
            skills = DesktopSkills(exclude_unavailable=True)
            for skill_name, spec in skills._skills.items():
                self.assertFalse(spec['adapter'].startswith('cli_hub.'))


if __name__ == '__main__':
    unittest.main()
