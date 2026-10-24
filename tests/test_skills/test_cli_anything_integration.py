"""Integration tests for the CLI-Anything skills against a real cli-hub.

These need the `cli-hub` executable and network access to the registry, so they
are skipped when either is unavailable. Nothing here installs or removes a CLI:
the mutating paths are exercised through their dry-run variants only.
"""
import json
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

import pytest

from skills.skills import DesktopSkills, SkillError

pytestmark = pytest.mark.live_desktop


def _find_cli_hub():
    """Locate the real cli-hub executable, if this environment has one."""
    local = Path(sys.executable).parent / 'cli-hub'
    if local.is_file() and os.access(local, os.X_OK):
        return str(local)
    return shutil.which('cli-hub')


class CLIAnythingIntegrationTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.binary = _find_cli_hub()
        if not cls.binary:
            raise unittest.SkipTest('cli-hub is not installed')
        # setUpClass runs before the per-test PATH fixture, so make the
        # executable discoverable through shutil.which() explicitly.
        binary_dir = str(Path(cls.binary).parent)
        if binary_dir not in os.environ.get('PATH', '').split(os.pathsep):
            os.environ['PATH'] = binary_dir + os.pathsep + os.environ.get('PATH', '')
        cls.skills = DesktopSkills()
        if not cls.skills._commands.get('cli-hub'):
            raise unittest.SkipTest('cli-hub is not on PATH')

    async def _skip_if_offline(self, coro):
        """Run an adapter call, skipping the test when the registry is unreachable."""
        try:
            return await coro
        except SkillError as error:
            message = str(error).lower()
            if any(token in message for token in
                   ('failed to fetch', 'network', 'connection', 'resolve', 'timeout')):
                self.skipTest(f'cli-hub registry unreachable: {error}')
            raise

    async def test_list_returns_categorized_registry(self):
        result = await self._skip_if_offline(self.skills.execute('cli_hub_list', {}))
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 3)
        categories = {entry.get('category') for entry in result}
        self.assertGreaterEqual(len(categories), 3)
        for entry in result:
            self.assertIn('name', entry)
            self.assertIn('category', entry)
        # Harness entries carry a pip install command; public entries carry an
        # install strategy instead. Every entry must describe one or the other.
        for entry in result:
            self.assertTrue(entry.get('install_cmd') or entry.get('install_strategy'),
                            f"{entry.get('name')} has no install instructions")
        self.assertTrue(any(entry.get('install_cmd') for entry in result))

    async def test_search_returns_relevant_results(self):
        result = await self._skip_if_offline(self.skills.execute('cli_hub_search', {'query': 'video'}))
        self.assertIsInstance(result, list)
        self.assertTrue(result)
        self.assertTrue(any('video' in (entry.get('name', '') + entry.get('description', '')).lower()
                            for entry in result))

    async def test_info_shows_harness_details(self):
        result = await self._skip_if_offline(self.skills.execute('cli_hub_info', {'name': 'gimp'}))
        self.assertEqual(result['name'], 'gimp')
        self.assertIn('entry_point', result)
        self.assertIn('requires', result)
        self.assertIn('install_cmd', result)

    async def test_install_dry_run_shows_plan_without_installing(self):
        result = await self._skip_if_offline(
            self.skills.execute('cli_hub_install', {'name': 'gimp', 'dry_run': True}))
        self.assertEqual(result['status'], 'dry_run')
        self.assertTrue(result['install_cmd'])
        self.assertEqual(result['entry_point'], 'cli-anything-gimp')

    async def test_matrix_list_returns_available_matrices(self):
        result = await self._skip_if_offline(self.skills.execute('cli_hub_matrix_list', {}))
        self.assertIsInstance(result, list)
        self.assertTrue(result)
        self.assertIn('video-creation', {matrix.get('name') for matrix in result})

    async def test_matrix_preflight_returns_capability_status(self):
        result = await self._skip_if_offline(
            self.skills.execute('cli_hub_matrix_preflight', {'matrix': 'video-creation'}))
        self.assertIn(result['status'], ('partial', 'complete'))
        self.assertIn('summary', result)
        self.assertIn('capabilities', result)

    async def test_matrix_install_dry_run_returns_plan(self):
        result = await self._skip_if_offline(self.skills.execute('cli_hub_matrix_install', {
            'matrix': 'video-creation', 'dry_run': True}))
        self.assertEqual(result['status'], 'dry_run')
        self.assertIn('plan', result)

    async def test_launch_uses_registry_entry_point(self):
        """The harness binary must come from the registry, not a guessed name."""
        with self.assertRaises(SkillError) as caught:
            await self.skills.execute('cli_hub_launch', {'name': 'feishu'})
        self.assertIn('lark-cli', str(caught.exception))

    async def test_launch_missing_binary_is_a_skill_error(self):
        with self.assertRaises(SkillError):
            await self.skills.execute('cli_hub_launch', {'name': 'gimp'})


if __name__ == '__main__':
    unittest.main()
