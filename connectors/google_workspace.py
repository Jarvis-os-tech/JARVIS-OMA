"""Portable, allowlisted Gmail, Calendar, and Tasks connector."""
from __future__ import annotations

import asyncio
import base64
from datetime import datetime, timezone
from email.message import EmailMessage
from email.policy import SMTP
import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
import secrets
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser

from connectors import credentials

TOKEN_URL = "https://oauth2.googleapis.com/token"
GMAIL_BASE = "https://gmail.googleapis.com/gmail/v1/users/me"
CALENDAR_BASE = "https://www.googleapis.com/calendar/v3"
TASKS_BASE = "https://tasks.googleapis.com/tasks/v1"
SCOPES = (
    "https://mail.google.com/",
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/tasks",
)
TOOLS = frozenset({
    "gmail_search", "gmail_read", "gmail_create_draft", "gmail_send_draft",
    "gmail_list_labels", "calendar_list_events", "calendar_get_event",
    "calendar_create_event", "calendar_list_calendars", "tasks_list_lists",
    "tasks_list_tasks", "tasks_create_task", "tasks_complete_task",
    "google_authorize", "google_connection_status",
})
_refresh_lock = threading.Lock()
_auth_server = None
_auth_lock = threading.Lock()


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_opener = urllib.request.build_opener(_NoRedirect)


def _load_tokens():
    path = credentials.token_path()
    try:
        with open(path, encoding="utf-8") as stream:
            tokens = json.load(stream)
        if not isinstance(tokens, dict):
            raise ValueError
        if not tokens.get('access_token') and tokens.get('token'):
            tokens['access_token'] = tokens['token']
        return tokens
    except (OSError, ValueError, json.JSONDecodeError):
        raise RuntimeError("Google tokens are not configured; complete Google authorization setup.") from None


def _expiry(tokens):
    value = tokens.get("expires_at", tokens.get("expiry"))
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
        except ValueError:
            return 0.0
    return 0.0


def _http_json(url, method="GET", body=None, headers=None, timeout=15):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    try:
        with _opener.open(request, timeout=timeout) as response:
            raw = response.read(2_000_001)
            if len(raw) > 2_000_000:
                return {"error": "Response too large"}
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        return {"error": f"HTTP {exc.code}"}
    except Exception:
        return {"error": "Google request failed"}


def _client_credentials(tokens=None):
    tokens = tokens or {}
    return (
        tokens.get("client_id") or credentials.get("GOOGLE_CLIENT_ID"),
        tokens.get("client_secret") or credentials.get("GOOGLE_CLIENT_SECRET"),
    )


def _refresh(tokens):
    client_id, client_secret = _client_credentials(tokens)
    refresh_token = tokens.get("refresh_token")
    if not (client_id and client_secret and refresh_token):
        raise RuntimeError("Google authorization setup is required.")
    form = urllib.parse.urlencode({
        "client_id": client_id, "client_secret": client_secret,
        "refresh_token": refresh_token, "grant_type": "refresh_token",
    }).encode()
    request = urllib.request.Request(TOKEN_URL, data=form, method="POST", headers={
        "Content-Type": "application/x-www-form-urlencoded",
    })
    try:
        with _opener.open(request, timeout=10) as response:
            refreshed = json.loads(response.read(100_000))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Google authorization failed (HTTP {exc.code}).") from None
    except Exception:
        raise RuntimeError("Google authorization request failed.") from None
    if not isinstance(refreshed, dict) or not refreshed.get("access_token"):
        raise RuntimeError("Google authorization response was invalid.")
    tokens.update(refreshed)
    tokens["access_token"] = refreshed["access_token"]
    expiry = time.time() + int(refreshed.get("expires_in", 3600))
    tokens["expires_at"] = expiry
    tokens["expiry"] = datetime.fromtimestamp(expiry, timezone.utc).isoformat().replace("+00:00", "Z")
    credentials.save_tokens(tokens)


def _access_token():
    with _refresh_lock:
        tokens = _load_tokens()
        if not tokens.get("access_token") or time.time() >= _expiry(tokens) - 300:
            _refresh(tokens)
        return tokens["access_token"]


def authenticated():
    """Return local setup readiness only; this intentionally performs no network call."""
    try:
        tokens = _load_tokens()
    except RuntimeError:
        return False
    client_id, client_secret = _client_credentials(tokens)
    return bool(tokens.get("refresh_token") and client_id and client_secret)


def _api(method, url, body=None, params=None):
    if not url.startswith((GMAIL_BASE, CALENDAR_BASE, TASKS_BASE)):
        return {"error": "Invalid Google API host"}
    if params:
        url += "?" + urllib.parse.urlencode(params)
    try:
        token = _access_token()
    except RuntimeError as exc:
        return {"error": str(exc), "setup_required": True}
    return _http_json(url, method, body, {
        "Authorization": f"Bearer {token}", "Content-Type": "application/json",
    })


def _bounded(value, default=10):
    try:
        return max(1, min(int(value), 50))
    except (ValueError, TypeError):
        return default


def _extract_body(payload):
    if payload.get("mimeType") == "text/plain":
        data = payload.get("body", {}).get("data", "")
        if data:
            try:
                return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)).decode("utf-8", errors="replace")
            except Exception:
                return ""
    for part in payload.get("parts", []):
        result = _extract_body(part)
        if result:
            return result
    return payload.get("snippet", "")


def _headers(response):
    return {h.get("name", ""): h.get("value", "") for h in response.get("payload", {}).get("headers", [])}


def gmail_search(query="", max_results=10):
    limit = _bounded(max_results)
    res = _api("GET", f"{GMAIL_BASE}/messages", params={"q": query, "maxResults": limit})
    if "error" in res: return {"success": False, "error": res["error"], **({"setup_required": True} if res.get("setup_required") else {})}
    results = []
    for msg in res.get("messages", [])[:limit]:
        detail = _api("GET", f"{GMAIL_BASE}/messages/{urllib.parse.quote(str(msg['id']), safe='')}", params={"format": "metadata", "metadataHeaders": "From,Subject,Date"})
        if "error" not in detail:
            h = _headers(detail)
            results.append({"id": msg["id"], "subject": h.get("Subject", "(no subject)"), "from": h.get("From", ""), "date": h.get("Date", ""), "snippet": detail.get("snippet", "")})
    return {"success": True, "count": len(results), "messages": results}


def gmail_read(message_id):
    res = _api("GET", f"{GMAIL_BASE}/messages/{urllib.parse.quote(str(message_id), safe='')}", params={"format": "full"})
    if "error" in res: return {"success": False, "error": res["error"], **({"setup_required": True} if res.get("setup_required") else {})}
    h = _headers(res)
    return {"success": True, "id": message_id, "subject": h.get("Subject", ""), "from": h.get("From", ""), "to": h.get("To", ""), "date": h.get("Date", ""), "snippet": res.get("snippet", ""), "body": _extract_body(res.get("payload", {}))[:4000]}


def gmail_create_draft(to, subject, body, cc=""):
    try:
        message = EmailMessage(policy=SMTP)
        message["To"] = to
        message["Subject"] = subject
        if cc: message["Cc"] = cc
        message.set_content(body)
    except (ValueError, TypeError):
        return {"success": False, "error": "Invalid email headers"}
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")
    res = _api("POST", f"{GMAIL_BASE}/drafts", {"message": {"raw": raw}})
    if "error" in res: return {"success": False, "error": res["error"]}
    return {"success": True, "draft_id": res.get("id"), "message": "Draft created."}


def gmail_send_draft(draft_id):
    res = _api("POST", f"{GMAIL_BASE}/drafts/send", {"id": draft_id})
    if "error" in res: return {"success": False, "error": res["error"]}
    return {"success": True, "message_id": res.get("id"), "message": "Email sent."}


def gmail_list_labels():
    res = _api("GET", f"{GMAIL_BASE}/labels")
    if "error" in res: return {"success": False, "error": res["error"]}
    return {"success": True, "labels": [{"id": x["id"], "name": x["name"]} for x in res.get("labels", [])]}


def calendar_list_events(calendar_id="primary", max_results=10, time_min=None, time_max=None, query=None):
    params = {"maxResults": _bounded(max_results), "orderBy": "startTime", "singleEvents": "true", "timeMin": time_min or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
    if time_max: params["timeMax"] = time_max
    if query: params["q"] = query
    cid = urllib.parse.quote(str(calendar_id), safe="")
    res = _api("GET", f"{CALENDAR_BASE}/calendars/{cid}/events", params=params)
    if "error" in res: return {"success": False, "error": res["error"]}
    events = []
    for e in res.get("items", [])[:params["maxResults"]]:
        start, end = e.get("start", {}), e.get("end", {})
        events.append({"id": e.get("id"), "summary": e.get("summary", "(no title)"), "start": start.get("dateTime", start.get("date", "")), "end": end.get("dateTime", end.get("date", "")), "location": e.get("location", ""), "status": e.get("status", ""), "link": e.get("htmlLink", "")})
    return {"success": True, "count": len(events), "events": events}


def calendar_get_event(event_id, calendar_id="primary"):
    cid, eid = urllib.parse.quote(str(calendar_id), safe=""), urllib.parse.quote(str(event_id), safe="")
    res = _api("GET", f"{CALENDAR_BASE}/calendars/{cid}/events/{eid}")
    if "error" in res: return {"success": False, "error": res["error"]}
    start, end = res.get("start", {}), res.get("end", {})
    return {"success": True, "id": res.get("id"), "summary": res.get("summary", ""), "description": res.get("description", ""), "start": start.get("dateTime", start.get("date", "")), "end": end.get("dateTime", end.get("date", "")), "location": res.get("location", ""), "attendees": [a.get("email") for a in res.get("attendees", [])], "link": res.get("htmlLink", "")}


def calendar_create_event(summary, start_datetime, end_datetime, description="", location="", attendees=None, calendar_id="primary"):
    body = {"summary": summary, "description": description, "location": location, "start": {"dateTime": start_datetime, "timeZone": "Asia/Kolkata"}, "end": {"dateTime": end_datetime, "timeZone": "Asia/Kolkata"}}
    if attendees: body["attendees"] = [{"email": x} for x in attendees]
    cid = urllib.parse.quote(str(calendar_id), safe="")
    res = _api("POST", f"{CALENDAR_BASE}/calendars/{cid}/events", body)
    if "error" in res: return {"success": False, "error": res["error"]}
    return {"success": True, "id": res.get("id"), "link": res.get("htmlLink", ""), "message": f"Event '{summary}' created."}


def calendar_list_calendars():
    res = _api("GET", f"{CALENDAR_BASE}/users/me/calendarList")
    if "error" in res: return {"success": False, "error": res["error"]}
    return {"success": True, "calendars": [{"id": x["id"], "summary": x.get("summary", ""), "primary": x.get("primary", False)} for x in res.get("items", [])[:50]]}


def tasks_list_lists():
    res = _api("GET", f"{TASKS_BASE}/users/@me/lists", params={"maxResults": 50})
    if "error" in res: return {"success": False, "error": res["error"]}
    return {"success": True, "lists": res.get("items", [])[:50]}


def tasks_list_tasks(list_id="@default"):
    lid = urllib.parse.quote(str(list_id), safe="")
    res = _api("GET", f"{TASKS_BASE}/lists/{lid}/tasks", params={"maxResults": 50})
    if "error" in res: return {"success": False, "error": res["error"]}
    return {"success": True, "tasks": res.get("items", [])[:50]}


def tasks_create_task(title, list_id="@default"):
    lid = urllib.parse.quote(str(list_id), safe="")
    res = _api("POST", f"{TASKS_BASE}/lists/{lid}/tasks", {"title": title})
    if "error" in res: return {"success": False, "error": res["error"]}
    return {"success": True, "task": res}


def tasks_complete_task(task_id, list_id="@default"):
    lid, tid = urllib.parse.quote(str(list_id), safe=""), urllib.parse.quote(str(task_id), safe="")
    res = _api("PATCH", f"{TASKS_BASE}/lists/{lid}/tasks/{tid}", {"status": "completed"})
    if "error" in res: return {"success": False, "error": res["error"]}
    return {"success": True, "task": res}


def google_connection_status():
    is_auth = authenticated()
    if is_auth:
        return {
            "success": True,
            "connected": True,
            "message": "Google Workspace is connected and authorized.",
        }
    return {
        "success": True,
        "connected": False,
        "setup_required": True,
        "message": "Google Workspace is not connected yet. Say 'open Google authorization' to connect.",
    }


def _find_free_oauth_port():
    env_port = os.environ.get("GOOGLE_OAUTH_PORT") or credentials.get("GOOGLE_OAUTH_PORT")
    if env_port:
        try:
            return int(env_port)
        except ValueError:
            pass
    for p in (8080, 8085, 8088):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("127.0.0.1", p))
                return p
        except OSError:
            continue
    return 8085


def google_authorize():
    global _auth_server
    client_id, client_secret = _client_credentials({})
    if not client_id or not client_secret:
        return {
            "success": False,
            "error": "Google client credentials are missing. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in .env.",
            "setup_required": True,
        }

    port = _find_free_oauth_port()
    state = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    redirect_uri = f"http://localhost:{port}/callback"

    class CallbackHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            url = urllib.parse.urlsplit(self.path)
            values = urllib.parse.parse_qs(url.query)
            valid = url.path == "/callback" and secrets.compare_digest(values.get("state", [""])[0], state)
            if not valid:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"Invalid authorization callback.")
                return

            code = values.get("code", [""])[0]
            if not code:
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(b"<html><body><h3>Google authorization was declined.</h3></body></html>")
                return

            request = urllib.request.Request(
                TOKEN_URL,
                data=urllib.parse.urlencode({
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": redirect_uri,
                    "code_verifier": verifier,
                }).encode(),
                method="POST",
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            success = False
            try:
                with _opener.open(request, timeout=15) as resp:
                    tokens = json.loads(resp.read(100_000))
                if tokens.get("access_token") and tokens.get("refresh_token"):
                    tokens["expires_at"] = time.time() + int(tokens.get("expires_in", 3600))
                    tokens["expiry"] = datetime.fromtimestamp(tokens["expires_at"], timezone.utc).isoformat().replace("+00:00", "Z")
                    tokens["client_id"] = client_id
                    tokens["client_secret"] = client_secret
                    credentials.save_tokens(tokens)
                    success = True
            except Exception:
                success = False

            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            if success:
                self.wfile.write(
                    b"<html><body style='font-family: sans-serif; text-align: center; padding-top: 50px;'>"
                    b"<h2 style='color: #4CAF50;'>Authorization Successful!</h2>"
                    b"<p>JARVIS is now connected to your Google Workspace account (Gmail, Calendar, Tasks).</p>"
                    b"<p>You may close this tab and return to JARVIS.</p>"
                    b"</body></html>"
                )
                try:
                    subprocess.run(
                        ["notify-send", "JARVIS", "Google Workspace connected successfully!"],
                        capture_output=True,
                        timeout=5,
                    )
                except Exception:
                    pass
            else:
                self.wfile.write(
                    b"<html><body style='font-family: sans-serif; text-align: center; padding-top: 50px;'>"
                    b"<h2 style='color: #F44336;'>Authorization Failed</h2>"
                    b"<p>Could not exchange authorization code with Google. Please try again.</p>"
                    b"</body></html>"
                )

        def log_message(self, *args):
            pass

    with _auth_lock:
        if _auth_server is not None:
            try:
                _auth_server.server_close()
            except Exception:
                pass
            _auth_server = None

        try:
            server = HTTPServer(("127.0.0.1", port), CallbackHandler)
            _auth_server = server
        except OSError as exc:
            return {
                "success": False,
                "error": f"Port {port} is currently busy ({exc}). Close the conflicting process and try again.",
            }

        def _run_server():
            global _auth_server
            try:
                server.timeout = 300
                server.handle_request()
            finally:
                with _auth_lock:
                    if _auth_server == server:
                        try:
                            server.server_close()
                        except Exception:
                            pass
                        _auth_server = None

        thread = threading.Thread(target=_run_server, daemon=True)
        thread.start()

    auth_url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode({
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "state": state,
        "access_type": "offline",
        "prompt": "consent",
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    })

    opened = False
    try:
        opened = webbrowser.open(auth_url)
    except Exception:
        pass
    if not opened:
        try:
            subprocess.Popen(["xdg-open", auth_url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            opened = True
        except Exception:
            pass

    return {
        "success": True,
        "message": "Opened Google authorization in your browser. Please approve access to connect your account.",
        "auth_url": auth_url,
    }


_DISPATCH = {
    "gmail_search": lambda a: gmail_search(a.get("query", ""), a.get("max_results", 10)),
    "gmail_read": lambda a: gmail_read(a["message_id"]),
    "gmail_create_draft": lambda a: gmail_create_draft(a["to"], a["subject"], a["body"], a.get("cc", "")),
    "gmail_send_draft": lambda a: gmail_send_draft(a["draft_id"]),
    "gmail_list_labels": lambda a: gmail_list_labels(),
    "calendar_list_events": lambda a: calendar_list_events(a.get("calendar_id", "primary"), a.get("max_results", 10), a.get("time_min"), a.get("time_max"), a.get("query")),
    "calendar_get_event": lambda a: calendar_get_event(a["event_id"], a.get("calendar_id", "primary")),
    "calendar_create_event": lambda a: calendar_create_event(a["summary"], a["start_datetime"], a["end_datetime"], a.get("description", ""), a.get("location", ""), a.get("attendees"), a.get("calendar_id", "primary")),
    "calendar_list_calendars": lambda a: calendar_list_calendars(),
    "tasks_list_lists": lambda a: tasks_list_lists(),
    "tasks_list_tasks": lambda a: tasks_list_tasks(a.get("list_id", "@default")),
    "tasks_create_task": lambda a: tasks_create_task(a["title"], a.get("list_id", "@default")),
    "tasks_complete_task": lambda a: tasks_complete_task(a["task_id"], a.get("list_id", "@default")),
    "google_authorize": lambda a: google_authorize(),
    "google_connection_status": lambda a: google_connection_status(),
}


async def dispatch(tool, arguments):
    if tool not in TOOLS:
        raise ValueError(f"Google tool is not allowlisted: {tool}")
    try:
        result = await asyncio.to_thread(_DISPATCH[tool], arguments)
        if "error" in result and "success" not in result:
            result = {"success": False, **result}
        if result.get('success') is False:
            error = result.get('error', '')
            if 'authorization setup' in error or 'tokens are not configured' in error or error == 'HTTP 401':
                result['setup_required'] = True
        return result
    except KeyError as exc:
        return {"success": False, "error": f"Missing required argument: {exc.args[0]}"}
    except Exception:
        return {"success": False, "error": "Google connector request failed"}
