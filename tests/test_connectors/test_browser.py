import unittest
from unittest.mock import MagicMock, patch

from connectors import browser


class BrowserLauncherTests(unittest.TestCase):
    def test_prefers_visible_omarchy_launcher_with_sanitized_environment(self):
        process = MagicMock()
        with patch.object(browser.shutil, 'which', side_effect=lambda name: '/usr/bin/omarchy-launch-webapp' if name == 'omarchy-launch-webapp' else None), \
                patch.object(browser.subprocess, 'Popen', return_value=process) as popen, \
                patch.object(browser, 'sanitized_subprocess_env', return_value={'PATH': '/usr/bin'}):
            self.assertTrue(browser.open_url('https://github.com/login/oauth/authorize'))
        popen.assert_called_once()
        self.assertEqual(popen.call_args.args[0][0], '/usr/bin/omarchy-launch-webapp')
        self.assertEqual(popen.call_args.kwargs['env'], {'PATH': '/usr/bin'})

    def test_rejects_non_web_urls(self):
        with patch.object(browser.subprocess, 'Popen') as popen:
            self.assertFalse(browser.open_url('file:///tmp/private'))
        popen.assert_not_called()


if __name__ == '__main__':
    unittest.main()
