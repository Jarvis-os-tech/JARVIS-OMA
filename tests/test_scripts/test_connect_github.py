import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch
import urllib.parse


SCRIPT = Path(__file__).resolve().parents[2] / 'scripts' / 'connect_github.py'
SPEC = importlib.util.spec_from_file_location('connect_github', SCRIPT)
connect_github = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(connect_github)


class ConnectGithubTests(unittest.TestCase):
    def test_authorization_url_uses_callback_scopes_state_and_pkce(self):
        url = connect_github._authorization_url('client-id', 'state-value', 'challenge-value')
        parsed = urllib.parse.urlsplit(url)
        values = urllib.parse.parse_qs(parsed.query)
        self.assertEqual(parsed.netloc, 'github.com')
        self.assertEqual(values['redirect_uri'], [connect_github.REGISTERED_REDIRECT_URI])
        self.assertEqual(values['state'], ['state-value'])
        self.assertEqual(values['code_challenge'], ['challenge-value'])
        self.assertEqual(set(values['scope'][0].split()), set(connect_github.SCOPES))

    def test_client_credentials_fall_back_to_project_env(self):
        with patch.object(connect_github.credentials, 'get', return_value=''), \
                patch.object(connect_github.credentials, 'read_env', return_value={
                    'GITHUB_CLIENT_ID': 'id', 'GITHUB_CLIENT_SECRET': 'secret'}):
            self.assertEqual(connect_github._client_credentials(), ('id', 'secret'))


if __name__ == '__main__':
    unittest.main()
