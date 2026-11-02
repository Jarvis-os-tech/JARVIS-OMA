# Connector dependency notes

These are unchanged source copies in feature folders. They do not form a runnable replacement for the original `connectors` package. Existing imports and relative resource paths still refer to the original layout.

| Original module | Imports (including conditional imports) |
| --- | --- |
| `__init__.py` |  |
| `browser.py` | `__future__: annotations`; `core.secret_env: sanitized_subprocess_env`; `shutil`; `subprocess`; `webbrowser` |
| `calendar_time.py` | `datetime: datetime, timezone`; `zoneinfo: ZoneInfo, ZoneInfoNotFoundError` |
| `credentials.py` | `__future__: annotations`; `json`; `os`; `pathlib: Path`; `shlex`; `tempfile` |
| `github.py` | `__future__: annotations`; `asyncio`; `base64`; `binascii`; `connectors.browser: open_url`; `connectors: credentials`; `hashlib`; `http.server: BaseHTTPRequestHandler, HTTPServer`; `json`; `os`; `re`; `secrets`; `subprocess`; `threading`; `urllib.error`; `urllib.parse`; `urllib.request` |
| `google_workspace.py` | `__future__: annotations`; `asyncio`; `base64`; `connectors.browser: open_url`; `connectors.calendar_time: calendar_zone, calendar_interval`; `connectors: credentials`; `datetime: datetime, timezone`; `email.message: EmailMessage`; `email.policy: SMTP`; `hashlib`; `http.server: BaseHTTPRequestHandler, HTTPServer`; `json`; `os`; `re`; `secrets`; `subprocess`; `threading`; `time`; `urllib.error`; `urllib.parse`; `urllib.request`; `webbrowser` |
| `internet_search.py` | `__future__: annotations`; `asyncio`; `connectors: credentials`; `html: unescape`; `httpx`; `ipaddress`; `json`; `re`; `urllib.parse: quote, urlencode, urlsplit` |
| `phone.py` | `__future__: annotations`; `asyncio`; `json`; `logging`; `os`; `pathlib: Path`; `re`; `shutil`; `subprocess`; `time`; `typing: Any, Awaitable, Callable`; `unicodedata` |

The credential-store implementation is copied; actual credentials, tokens and signing keys are excluded. Adapters under `skills/domains`, setup scripts and tests retain their original application dependencies. No network connection, authentication flow, device action or connector operation was started.

See [source map](README.md) and the [existing application dependency map](../../../evidence/Oma%20Jarvis/_analysis/DEPENDENCY_MAP.md).
