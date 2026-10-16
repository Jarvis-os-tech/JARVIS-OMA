import unittest

from core.secret_env import is_secret_name, sanitized_subprocess_env


class SecretEnvironmentTests(unittest.TestCase):
    def test_recognizes_common_credential_names(self):
        for name in ('GEMINI_API_KEY', 'GITHUB_TOKEN', 'CLIENT_SECRET',
                     'DB_PASSWORD', 'AWS_ACCESS_KEY_ID', 'GOOGLE_CREDENTIALS'):
            self.assertTrue(is_secret_name(name), name)
        for name in ('PATH', 'DISPLAY', 'XDG_RUNTIME_DIR', 'GIT_TERMINAL_PROMPT'):
            self.assertFalse(is_secret_name(name), name)

    def test_sanitized_environment_keeps_runtime_values_and_drops_secrets(self):
        result = sanitized_subprocess_env({
            'PATH': '/bin', 'GITHUB_TOKEN': 'private', 'CLIENT_SECRET': 'private',
            'DISPLAY': ':0'}, GIT_TERMINAL_PROMPT='0')
        self.assertEqual(result, {
            'PATH': '/bin', 'DISPLAY': ':0', 'GIT_TERMINAL_PROMPT': '0'})


if __name__ == '__main__':
    unittest.main()
