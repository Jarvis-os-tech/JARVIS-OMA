"""Regression coverage for credential-name filtering in child environments."""

import unittest

from core.secret_env import is_secret_name, sanitized_subprocess_env


class SecretEnvironmentRegressionTests(unittest.TestCase):
    def test_recognizes_key_and_bearer_credentials(self):
        for name in (
            'OPENAI_KEY',
            'PRIVATE_KEY',
            'AUTH_BEARER',
            'SERVICE_AUTH_BEARER',
            'AUTHORIZATION',
        ):
            with self.subTest(name=name):
                self.assertTrue(is_secret_name(name))

    def test_keeps_runtime_and_url_variables_while_dropping_credentials(self):
        result = sanitized_subprocess_env(
            {
                'PATH': '/usr/bin',
                'DISPLAY': ':0',
                'XDG_RUNTIME_DIR': '/run/user/1000',
                'DATABASE_URL': 'postgres://user:password@host/database',
                'REDIS_URL': 'redis://user:password@host/0',
                'OPENAI_KEY': 'credential value',
                'PRIVATE_KEY': 'credential value',
                'AUTH_BEARER': 'credential value',
            },
            AUTHORIZATION='credential value',
            GIT_TERMINAL_PROMPT='0',
        )

        for name in ('OPENAI_KEY', 'PRIVATE_KEY', 'AUTH_BEARER', 'AUTHORIZATION'):
            with self.subTest(name=name):
                self.assertNotIn(name, result)
        for name in ('PATH', 'DISPLAY', 'XDG_RUNTIME_DIR', 'DATABASE_URL',
                     'REDIS_URL', 'GIT_TERMINAL_PROMPT'):
            with self.subTest(name=name):
                self.assertIn(name, result)


if __name__ == '__main__':
    unittest.main()
