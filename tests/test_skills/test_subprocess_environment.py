"""Explicit child environments must not inherit desktop variables implicitly."""
import os
import sys
import unittest
from unittest.mock import patch

from skills import system_control


class SubprocessEnvironmentTests(unittest.IsolatedAsyncioTestCase):
    async def test_empty_environment_excludes_parent_variables(self):
        with patch.dict(os.environ, {'JARVIS_TEST_PARENT': 'synthetic'}):
            code, out, _ = await system_control._run_command(
                sys.executable, '-c',
                "import os; print(os.getenv('JARVIS_TEST_PARENT', 'absent'))", env={})
        self.assertEqual(code, 0)
        self.assertEqual(out, 'absent')

    async def test_none_uses_desktop_default(self):
        with patch.object(system_control, '_desktop_env', return_value={'JARVIS_TEST_CHILD': 'default'}) as default:
            code, out, _ = await system_control._run_command(
                sys.executable, '-c', "import os; print(os.getenv('JARVIS_TEST_CHILD'))")
        default.assert_called_once_with()
        self.assertEqual((code, out), (0, 'default'))

    async def test_explicit_environment_is_preserved(self):
        with patch.object(system_control, '_desktop_env', side_effect=AssertionError('unexpected default')):
            code, out, _ = await system_control._run_command(
                sys.executable, '-c', "import os; print(os.getenv('JARVIS_TEST_CHILD'))",
                env={'JARVIS_TEST_CHILD': 'explicit'})
        self.assertEqual((code, out), (0, 'explicit'))
