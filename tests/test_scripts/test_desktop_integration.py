"""Desktop installation against actual temporary files and a local service stub."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from scripts.desktop_integration import install


ROOT = Path(__file__).resolve().parents[2]


class DesktopIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / 'Jarvis space % $ folder'
        (self.repo / 'systemd').mkdir(parents=True)
        shutil.copy(ROOT / 'systemd/jarvis-oma.service', self.repo / 'systemd/jarvis-oma.service')
        self.config = self.root / 'config'
        self.data = self.root / 'data'
        self.bin = self.root / 'bin'

    def install(self):
        return install(self.repo, config_home=self.config, data_home=self.data, bin_home=self.bin)

    @patch('scripts.desktop_integration.subprocess.run')
    def test_portable_install_has_one_service_and_is_idempotent(self, run):
        hook = self.install()
        self.install()
        units = self.config / 'systemd/user'
        self.assertEqual((units / 'jarvis.service').resolve(), units / 'jarvis-oma.service')
        unit = (units / 'jarvis-oma.service').read_text()
        self.assertIn('WorkingDirectory=' + str(self.repo).replace('%', '%%') + '\n', unit)
        self.assertIn('%% $$ folder/run.sh"', unit)
        self.assertIn('EnvironmentFile=-' + str(self.repo / '.env').replace('%', '%%') + '\n', unit)
        self.assertEqual((self.bin / 'jarvisctl').readlink(), self.repo / 'scripts/jarvisctl')
        self.assertTrue(os.access(hook, os.X_OK))
        self.assertIn('desktop-session.sh', hook.read_text())
        desktop = (self.data / 'applications/jarvis.desktop').read_text()
        self.assertIn(' toggle\n', desktop)
        self.assertEqual(list(self.root.rglob('*.bak.*')), [])
        run.assert_any_call(['systemctl', '--user', 'enable', 'jarvis-oma.service'], check=True)

    @patch('scripts.desktop_integration.subprocess.run', side_effect=subprocess.CalledProcessError(1, 'verify'))
    def test_invalid_service_is_rejected_before_changing_installed_files(self, run):
        with self.assertRaises(subprocess.CalledProcessError):
            self.install()
        self.assertFalse(self.config.exists())
        self.assertFalse(self.bin.exists())

    @patch('scripts.desktop_integration.subprocess.run')
    def test_migrates_legacy_unit_and_preserves_existing_content(self, run):
        unit = self.config / 'systemd/user/jarvis.service'
        unit.parent.mkdir(parents=True)
        unit.write_text('old unit')
        self.install()
        self.assertTrue(unit.is_symlink())
        backups = list(unit.parent.glob('jarvis.service.bak.*'))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_text(), 'old unit')
        run.assert_any_call(['systemctl', '--user', 'stop', 'jarvis.service'], check=True)

    def test_login_hook_imports_only_desktop_variables_and_respects_disable(self):
        self.bin.mkdir()
        log = self.root / 'calls'
        stub = self.bin / 'systemctl'
        stub.write_text('#!/bin/bash\nprintf "%s\\n" "$*" >> "$JARVIS_TEST_LOG"\n'
                        'if [[ "$*" == *is-enabled* ]]; then exit "${JARVIS_TEST_DISABLED:-0}"; fi\n')
        stub.chmod(0o755)
        env = {**os.environ, 'PATH': f'{self.bin}:/usr/bin', 'JARVIS_TEST_LOG': str(log),
               'WAYLAND_DISPLAY': 'wayland-test', 'GEMINI_API_KEY': 'must-not-be-imported'}
        for disabled in (False, True):
            log.unlink(missing_ok=True)
            env['JARVIS_TEST_DISABLED'] = str(int(disabled))
            subprocess.run(['bash', str(ROOT / 'scripts/desktop-session.sh')], env=env, check=True)
            calls = log.read_text()
            self.assertIn('import-environment', calls)
            self.assertIn('WAYLAND_DISPLAY', calls)
            self.assertNotIn('GEMINI_API_KEY', calls)
            self.assertEqual('start --no-block jarvis-oma.service' in calls, not disabled)
