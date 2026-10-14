import asyncio
import base64
from email import message_from_bytes
from email.policy import default
import json
import time
import unittest
from unittest.mock import patch

from connectors import google_workspace as google


class GoogleConnectorTests(unittest.TestCase):
    def test_authenticated_checks_configuration_without_network(self):
        tokens = {"refresh_token": "refresh", "client_id": "id", "client_secret": "secret"}
        with patch.object(google, "_load_tokens", return_value=tokens), patch.object(google, "_http_json", side_effect=AssertionError("network")):
            self.assertTrue(google.authenticated())

    def test_auth_supports_both_expiry_formats(self):
        self.assertGreater(google._expiry({"expires_at": time.time() + 500}), time.time())
        self.assertGreater(google._expiry({"expiry": "2099-01-01T00:00:00Z"}), time.time())

    def test_refresh_uses_token_client_fallback_and_saves(self):
        token_doc = {"access_token": "old", "expires_at": 0, "refresh_token": "private-refresh", "client_id": "private-id", "client_secret": "private-secret"}

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self, *args): return b'{"access_token":"new-private-token","expires_in":3600}'

        with patch.object(google, "_load_tokens", return_value=token_doc), patch.object(google._opener, "open", return_value=Response()) as opened, patch.object(google.credentials, "save_tokens") as saved:
            self.assertEqual(google._access_token(), "new-private-token")
        request = opened.call_args.args[0]
        self.assertEqual(request.full_url, google.TOKEN_URL)
        self.assertIn(b"private-refresh", request.data)
        saved.assert_called_once()
        self.assertEqual(saved.call_args.args[0]["access_token"], "new-private-token")
        self.assertIn("expiry", saved.call_args.args[0])

    def test_refresh_client_credentials_fall_back_to_credentials_module(self):
        with patch.object(google.credentials, "get", side_effect=lambda key: {"GOOGLE_CLIENT_ID": "fallback-id", "GOOGLE_CLIENT_SECRET": "fallback-secret"}[key]):
            self.assertEqual(google._client_credentials({}), ("fallback-id", "fallback-secret"))

    def test_path_ids_are_fully_escaped(self):
        with patch.object(google, "_api", return_value={"id": "ok"}) as api:
            google.calendar_get_event("x/y?z", "cal/a")
        self.assertIn("/calendars/cal%2Fa/events/x%2Fy%3Fz", api.call_args.args[1])

    def test_draft_headers_reject_injection_and_encode_valid_mail(self):
        with patch.object(google, "_api", return_value={"id": "draft"}) as api:
            result = google.gmail_create_draft("a@example.com", "Hello", "Body", "b@example.com")
        self.assertTrue(result["success"])
        raw = base64.urlsafe_b64decode(api.call_args.args[2]["message"]["raw"])
        message = message_from_bytes(raw, policy=default)
        self.assertEqual(message["To"], "a@example.com")
        self.assertEqual(message["Cc"], "b@example.com")
        self.assertEqual(message["Subject"], "Hello")
        self.assertEqual(message.get_content().strip(), "Body")
        self.assertFalse(google.gmail_create_draft("ok@example.com", "Good\nBcc: victim@example.com", "Body")["success"])

    def test_http_errors_only_expose_status(self):
        error = __import__("urllib.error", fromlist=["HTTPError"]).HTTPError(
            "https://gmail.googleapis.com/", 403, "denied private-token", {}, None
        )
        with patch.object(google, "_access_token", return_value="secret-token"), patch.object(google._opener, "open", side_effect=error):
            result = google._api("GET", f"{google.GMAIL_BASE}/labels")
        self.assertEqual(result, {"error": "HTTP 403"})
        self.assertNotIn("secret-token", json.dumps(result))
        self.assertNotIn("denied", json.dumps(result))

    def test_dispatch_is_async_allowlisted_and_returns_success_shape(self):
        with patch.object(google, "gmail_list_labels", return_value={"success": True, "labels": []}):
            self.assertEqual(asyncio.run(google.dispatch("gmail_list_labels", {})), {"success": True, "labels": []})
        with self.assertRaises(ValueError):
            asyncio.run(google.dispatch("not_a_tool", {}))

    def test_google_connection_status(self):
        with patch.object(google, "authenticated", return_value=False):
            res = google.google_connection_status()
            self.assertTrue(res["success"])
            self.assertFalse(res["connected"])
            self.assertTrue(res["setup_required"])
        with patch.object(google, "authenticated", return_value=True):
            res = google.google_connection_status()
            self.assertTrue(res["success"])
            self.assertTrue(res["connected"])

    def test_google_authorize_opens_browser(self):
        with patch.object(google, "_client_credentials", return_value=("test-id", "test-secret")), \
             patch("connectors.google_workspace.HTTPServer") as mock_server, \
             patch("connectors.google_workspace.webbrowser.open", return_value=True) as mock_open:
            mock_server.return_value = unittest.mock.MagicMock()
            result = google.google_authorize()
            self.assertTrue(result["success"])
            self.assertIn("auth_url", result)
            self.assertIn("test-id", result["auth_url"])
            self.assertIn("code_challenge", result["auth_url"])
            mock_open.assert_called_once()


if __name__ == "__main__":
    unittest.main()
