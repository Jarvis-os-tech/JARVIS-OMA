import asyncio
import base64
from email import message_from_bytes
from email.policy import default
import json
import time
import unittest
from urllib.parse import parse_qs, urlsplit
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

    def test_gmail_search_requests_each_header_and_preserves_api_errors(self):
        listing = {"messages": [{"id": "message-id"}]}
        detail = {"payload": {"headers": [
            {"name": "subject", "value": "Hello"},
            {"name": "FROM", "value": "friend@example.com"},
        ]}, "snippet": "A preview"}
        with patch.object(google, "_api", side_effect=[listing, detail]) as api:
            result = google.gmail_search("is:unread")
        self.assertTrue(result["success"])
        self.assertEqual(result["messages"][0]["subject"], "Hello")
        self.assertEqual(result["messages"][0]["from"], "friend@example.com")
        self.assertEqual(api.call_args.kwargs["params"]["metadataHeaders"],
                         ["From", "Subject", "Date"])

        with patch.object(google, "_api", side_effect=[listing, {"error": "HTTP 401"}]):
            result = google.gmail_search("is:unread")
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "HTTP 401")

    def test_api_serializes_repeated_gmail_headers(self):
        with patch.object(google, "_access_token", return_value="test-token"), \
             patch.object(google, "_http_json", return_value={}) as request:
            google._api("GET", f"{google.GMAIL_BASE}/messages/x", params={
                "format": "metadata", "metadataHeaders": ["From", "Subject"]})
        url = request.call_args.args[0]
        self.assertIn("metadataHeaders=From&metadataHeaders=Subject", url)

    def test_gmail_read_uses_preview_when_plain_text_is_absent(self):
        with patch.object(google, "_api", return_value={"snippet": "Readable preview",
                                                      "payload": {"mimeType": "text/html"}}):
            result = google.gmail_read("message-id")
        self.assertEqual(result["body"], "Readable preview")

    def test_gmail_read_skips_plain_text_attachments(self):
        attachment = base64.urlsafe_b64encode(b"Attachment contents").decode()
        message = base64.urlsafe_b64encode(b"Actual message").decode()
        payload = {"mimeType": "multipart/mixed", "parts": [
            {"mimeType": "text/plain", "filename": "notes.txt",
             "headers": [{"name": "Content-Disposition", "value": "attachment; filename=notes.txt"}],
             "body": {"data": attachment}},
            {"mimeType": "text/plain", "body": {"data": message}},
        ]}
        with patch.object(google, "_api", return_value={"snippet": "Preview", "payload": payload}):
            result = google.gmail_read("message-id")
        self.assertEqual(result["body"], "Actual message")

    def test_oauth_listener_survives_unrelated_request(self):
        completed = __import__("threading").Event()
        class Server:
            timeout = None
            calls = 0
            def handle_request(self):
                self.calls += 1
                if self.calls == 2:
                    completed.set()
        server = Server()
        google._serve_auth_callbacks(server, completed, timeout=2)
        self.assertEqual(server.calls, 2)
        self.assertLessEqual(server.timeout, 1)

    def test_tasks_resolve_default_list_and_preserve_explicit_list(self):
        with patch.object(google, "_api", side_effect=[
            {"items": [{"id": "account-list", "title": "My Tasks"}]},
            {"items": [{"id": "task-1"}]},
        ]) as api:
            result = google.tasks_list_tasks()
        self.assertTrue(result["success"])
        self.assertIn("/lists/account-list/tasks", api.call_args.args[1])

        with patch.object(google, "_api", return_value={"id": "created"}) as api:
            result = google.tasks_create_task("Buy milk", "other/list")
        self.assertTrue(result["success"])
        self.assertEqual(api.call_count, 1)
        self.assertIn("/lists/other%2Flist/tasks", api.call_args.args[1])

    def test_tasks_report_missing_list_instead_of_using_literal_default(self):
        with patch.object(google, "_api", return_value={"items": []}) as api:
            result = google.tasks_complete_task("task-1")
        self.assertFalse(result["success"])
        self.assertIn("No Google Task list", result["error"])
        self.assertEqual(api.call_count, 1)

    def test_dispatch_is_async_allowlisted_and_returns_success_shape(self):
        async def immediate(function, arguments):
            return function(arguments)
        with patch.object(google, "gmail_list_labels", return_value={"success": True, "labels": []}), \
             patch.object(google.asyncio, "to_thread", immediate):
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
             patch.object(google, "_auth_server", None), \
             patch("connectors.google_workspace.threading.Thread") as mock_thread, \
             patch("connectors.google_workspace.open_url", return_value=True) as mock_open:
            mock_server.return_value = unittest.mock.MagicMock()
            result = google.google_authorize()
            self.assertTrue(result["success"])
            self.assertIn("auth_url", result)
            self.assertIn("test-id", result["auth_url"])
            self.assertIn("code_challenge", result["auth_url"])
            self.assertIn("localhost%3A8085%2Fcallback", result["auth_url"])
            self.assertIn(google.DRIVE_READ_SCOPE,
                          parse_qs(urlsplit(result["auth_url"]).query)["scope"][0].split())
            mock_open.assert_called_once()
            # This test checks launch wiring. A real thread around a mocked
            # HTTPServer spins for the entire OAuth deadline (five minutes).
            # Callback-loop behavior is exercised separately above.
            mock_thread.return_value.start.assert_called_once()
            self.assertTrue(mock_thread.call_args.kwargs["daemon"])

    def test_drive_scope_is_separate_from_existing_google_connection(self):
        old = {"scope": "https://mail.google.com/ https://www.googleapis.com/auth/calendar"}
        with patch.object(google, "_load_tokens", return_value=old), patch.object(google, "authenticated", return_value=True), patch.object(google, "_api", side_effect=AssertionError("no API call")):
            self.assertFalse(google.google_connection_status()["drive_connected"])
            result = google.drive_search_files("budget")
            self.assertTrue(result["setup_required"])
            self.assertIn("read-only permission", result["error"])

    def test_drive_search_escapes_query_and_bounds_result(self):
        token = {"scope": google.DRIVE_READ_SCOPE}
        files = [{"id": "a", "name": "Budget", "mimeType": "application/vnd.google-apps.spreadsheet"}]
        with patch.object(google, "_load_tokens", return_value=token), patch.object(google, "_api", return_value={"files": files, "nextPageToken": "next"}) as api:
            result = google.drive_search_files("Bob's plan", max_results=999)
        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 1)
        self.assertTrue(result["has_more"])
        self.assertEqual(api.call_args.kwargs["params"]["pageSize"], 50)
        self.assertIn("Bob\\'s plan", api.call_args.kwargs["params"]["q"])

    def test_drive_text_read_rejects_binary_and_limits_text(self):
        with patch.object(google, "drive_get_file", return_value={"success": True, "file": {"mimeType": "application/pdf", "id": "x"}}), patch.object(google, "_api_text", side_effect=AssertionError("no download")):
            self.assertFalse(google.drive_read_text_file("x")["success"])
        with patch.object(google, "drive_get_file", return_value={"success": True, "file": {"mimeType": "text/plain", "id": "x"}}), patch.object(google, "_api_text", return_value={"text": "hello", "truncated": False}) as api:
            self.assertEqual(google.drive_read_text_file("x")["content"], "hello")
        self.assertIn("alt=media", api.call_args.args[0])

    def test_docs_read_collects_nested_tabs_and_table_text(self):
        doc = {"documentId": "d", "title": "Plan", "tabs": [{"tabProperties": {"title": "First"}, "documentTab": {"body": {"content": [{"paragraph": {"elements": [{"textRun": {"content": "Hello\n"}}]}}]}}, "childTabs": [{"tabProperties": {"title": "Nested"}, "documentTab": {"body": {"content": [{"table": {"tableRows": [{"tableCells": [{"content": [{"paragraph": {"elements": [{"textRun": {"content": "Cell"}}]}}]}]}]}}]}}}]}]}
        with patch.object(google, "_load_tokens", return_value={"scope": google.DRIVE_READ_SCOPE}), patch.object(google, "_api", return_value=doc) as api:
            result = google.docs_read_document("d/x")
        self.assertIn("Hello", result["text"])
        self.assertIn("Cell", result["text"])
        self.assertIn("d%2Fx", api.call_args.args[1])
        self.assertEqual(api.call_args.kwargs["params"], {"includeTabsContent": "true"})

    def test_sheets_ranges_are_bounded_and_escaped(self):
        with patch.object(google, "_load_tokens", return_value={"scope": google.DRIVE_READ_SCOPE}), patch.object(google, "_api", return_value={"range": "Sheet 1!A1:B2", "values": [["A", "B"], ["1", "2"]]}) as api:
            self.assertFalse(google.sheets_read_range("id", "A1:U1")["success"])
            self.assertFalse(google.sheets_read_range("id", "A1:J101")["success"])
            result = google.sheets_read_range("s/id", "'Sheet 1'!A1:B2")
        self.assertTrue(result["success"])
        self.assertEqual(result["rows"], 2)
        self.assertIn("s%2Fid", api.call_args.args[1])
        self.assertIn("%27Sheet%201%27%21A1%3AB2", api.call_args.args[1])
        self.assertEqual(api.call_count, 1)

        large = {"values": [["x" * 1000 for _ in range(20)] for _ in range(100)]}
        with patch.object(google, "_load_tokens", return_value={"scope": google.DRIVE_READ_SCOPE}), patch.object(google, "_api", return_value=large):
            result = google.sheets_read_range("id", "A1:T100")
        self.assertTrue(result["truncated"])
        self.assertLessEqual(sum(len(cell) for row in result["values"] for cell in row), 20_000)

    def test_new_tools_dispatch_and_oauth_scope(self):
        self.assertIn(google.DRIVE_READ_SCOPE, google.SCOPES)
        async def immediate(function, arguments):
            return function(arguments)
        with patch.object(google, "drive_get_file", return_value={"success": True, "file": {"id": "f"}}), \
             patch.object(google.asyncio, "to_thread", immediate):
            result = asyncio.run(google.dispatch("drive_get_file", {"file_id": "f"}))
        self.assertEqual(result["file"]["id"], "f")


if __name__ == "__main__":
    unittest.main()
