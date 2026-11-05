"""Typed widget controller for the existing Omarchy shell; never launches a GUI."""
from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import uuid
try:
    from ui.jarvis_widgets.view_schema import validate_view
except ModuleNotFoundError:
    from view_schema import validate_view  # Installed shell's short-lived input helper.

KINDS = {"view", "text", "qr", "image", "pip", "table", "chart", "progress"}
FIELDS = {
    "text": {"text", "actions"}, "qr": {"content"}, "image": {"path", "caption", "actions"},
    "pip": {"path", "caption", "actions"}, "table": {"columns", "rows"},
    "chart": {"labels", "values", "unit"},
    "progress": {"text", "value", "maximum", "actions"},
    "view": {"state", "computed", "layout", "width"},
}
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
VIDEO_SUFFIXES = {".mp4", ".webm", ".mkv"}


def compact(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"))


def runtime_dir():
    root = Path(os.environ.get("XDG_RUNTIME_DIR") or os.environ.get("XDG_STATE_HOME")
                or Path.home() / ".local/state") / "jarvis/widgets"
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    info = root.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise ValueError("Widget runtime must be private and owned by this user")
    return root


def text(value, maximum=8000):
    if not isinstance(value, str) or len(value) > maximum:
        raise ValueError(f"Expected text of at most {maximum} characters")
    return value


def finite_number(value):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError("Expected a finite number")
    return value


def validate(kind, data):
    if kind not in KINDS or not isinstance(data, dict):
        raise ValueError("Unsupported widget kind or data")
    if set(data) - FIELDS[kind]:
        raise ValueError("Unexpected widget fields")
    if len(compact(data).encode()) > 48000:
        raise ValueError("Widget data exceeds 48 KiB")
    if kind == "view":
        return validate_view(data)
    if kind == "text":
        out = {"text": text(data.get("text", ""))}
        if "actions" in data and isinstance(data["actions"], list):
            out["actions"] = [
                {
                    "label": text(item.get("label", ""), 40),
                    "action": text(item.get("action", ""), 40),
                    "prompt": text(item.get("prompt", item.get("action", "")), 100),
                    "primary": bool(item.get("primary", False))
                }
                for item in data["actions"] if isinstance(item, dict)
            ]
        return out
    if kind == "qr":
        return {"content": text(data.get("content"), 2000)}
    if kind in ("image", "pip"):
        path = Path(text(data.get("path"), 4096)).expanduser().resolve(strict=True)
        allowed = IMAGE_SUFFIXES | (VIDEO_SUFFIXES if kind == "pip" else set())
        if not path.is_file() or path.suffix.lower() not in allowed:
            raise ValueError("Choose a local supported image or video file")
        if path.stat().st_size > 128 * 1024 * 1024:
            raise ValueError("Media exceeds the 128 MiB widget limit")
        out = {
            "source": path.as_uri(),
            "video": path.suffix.lower() in VIDEO_SUFFIXES,
            "caption": text(data.get("caption", ""), 1000)
        }
        if "actions" in data and isinstance(data["actions"], list):
            out["actions"] = [
                {
                    "label": text(item.get("label", ""), 40),
                    "action": text(item.get("action", ""), 40),
                    "prompt": text(item.get("prompt", item.get("action", "")), 100),
                    "primary": bool(item.get("primary", False))
                }
                for item in data["actions"] if isinstance(item, dict)
            ]
        return out
    if kind == "table":
        columns, rows = data.get("columns"), data.get("rows")
        if not isinstance(columns, list) or not 1 <= len(columns) <= 8:
            raise ValueError("Tables need 1–8 columns")
        columns = [text(item, 100) for item in columns]
        if not isinstance(rows, list) or len(rows) > 100:
            raise ValueError("Tables support at most 100 rows per card")
        validated = []
        for row in rows:
            if not isinstance(row, list) or len(row) != len(columns):
                raise ValueError("Every row must match the columns")
            validated.append([text(str(item), 500) if type(item) in (str, int, float, bool) else
                              (_ for _ in ()).throw(ValueError("Invalid table cell")) for item in row])
        return {"columns": columns, "rows": validated}
    if kind == "chart":
        labels, values = data.get("labels"), data.get("values")
        if not isinstance(labels, list) or not isinstance(values, list) or not 1 <= len(labels) <= 20 or len(labels) != len(values):
            raise ValueError("Charts need 1–20 matching labels and values")
        values = [finite_number(value) for value in values]
        if any(value < 0 for value in values):
            raise ValueError("This bar-chart component supports non-negative values")
        return {"labels": [text(label, 80) for label in labels], "values": values,
                "unit": text(data.get("unit", ""), 40)}
    result = {"text": text(data.get("text", ""), 1000)}
    if "actions" in data and isinstance(data["actions"], list):
        result["actions"] = [
            {
                "label": text(item.get("label", ""), 40),
                "action": text(item.get("action", ""), 40),
                "prompt": text(item.get("prompt", item.get("action", "")), 100),
                "primary": bool(item.get("primary", False))
            }
            for item in data["actions"] if isinstance(item, dict)
        ]
    if "value" in data:
        maximum = finite_number(data.get("maximum", 100))
        value = finite_number(data["value"])
        if maximum <= 0 or not 0 <= value <= maximum:
            raise ValueError("Progress must be within a positive maximum")
        result.update(value=value, maximum=maximum)
    elif "maximum" in data:
        raise ValueError("A maximum requires measured progress")
    return result


def make_widget(kind, title, data, *, widget_id="", presentation="floating", expires_seconds=120):
    if presentation not in ("canvas", "floating"):
        raise ValueError("Presentation must be canvas or floating")
    if not isinstance(expires_seconds, int) or not 0 <= expires_seconds <= 86400:
        raise ValueError("Expiry must be 0–86400 seconds; zero retains the card")
    widget_id = widget_id or "widget-" + uuid.uuid4().hex[:16]
    if widget_id.startswith('jtask_'):
        raise ValueError('Task card IDs are reserved for task events')
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", widget_id):
        raise ValueError("Invalid widget ID")
    clean = validate(kind, data)
    if kind == "qr":
        binary = shutil.which("qrencode")
        if not binary:
            raise ValueError("QR rendering requires qrencode")
        # Input goes through stdin; neither shell expansion nor secret argv.
        descriptor, filename = tempfile.mkstemp(prefix="qr-", suffix=".png", dir=runtime_dir())
        os.close(descriptor)
        try:
            subprocess.run([binary, "-t", "PNG", "-l", "M", "-s", "8", "-o", filename],
                           input=clean["content"], text=True, check=True,
                           capture_output=True, timeout=3)
        except Exception:
            Path(filename).unlink(missing_ok=True)
            raise
        clean = {"source": Path(filename).as_uri()}
    return {"id": widget_id, "kind": kind, "title": text(title, 160), "data": clean,
            "floating": presentation == "floating", "expires_seconds": expires_seconds}


def shell_call(method, payload=None):
    command = [shutil.which("omarchy-shell") or "omarchy-shell", "jarvis-canvas", method]
    if payload is not None:
        command.append(compact(payload) if isinstance(payload, dict) else str(payload))
    process = subprocess.run(command, capture_output=True, text=True, timeout=4)
    if process.returncode:
        raise RuntimeError(process.stderr.strip() or "JARVIS widget plugin is unavailable in the existing shell")
    try:
        result = json.loads(process.stdout.strip())
    except ValueError:
        raise RuntimeError("The existing shell did not acknowledge the widget request") from None
    if not isinstance(result, dict) or result.get("ok") is not True:
        raise RuntimeError(str(result.get("error", "Widget request rejected")) if isinstance(result, dict) else "Invalid widget receipt")
    return result


async def send_text(message):
    message = " ".join(text(message, 16000).split())
    if not message:
        raise ValueError("Enter a request first")
    runtime = os.environ.get("XDG_RUNTIME_DIR") or os.environ.get("XDG_STATE_HOME") or str(Path.home() / ".local/state")
    async with asyncio.timeout(2):
        reader, writer = await asyncio.open_unix_connection(str(Path(runtime) / "jarvis/control.sock"), limit=262144)
        try:
            writer.write(("send " + message + "\n").encode())
            await writer.drain()
            result = json.loads(await reader.readline())
            if not isinstance(result, dict) or result.get("status") != "sent":
                raise RuntimeError("Voice session did not accept the request")
            return {"ok": True, "status": "sent"}
        finally:
            writer.close()
            await writer.wait_closed()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("open", "close", "input", "clear", "clearAll", "status"):
        sub.add_parser(name)
    show = sub.add_parser("show")
    show.add_argument("kind", choices=sorted(KINDS))
    show.add_argument("--title", default="JARVIS")
    data_input = show.add_mutually_exclusive_group(required=True)
    data_input.add_argument("--data", help="JSON data")
    data_input.add_argument("--data-file", type=Path, help="Read private JSON data without placing it in process arguments")
    show.add_argument("--id", default="")
    show.add_argument("--floating", action="store_true", help="Default: float over desktop")
    show.add_argument("--canvas", action="store_true", help="Group with other canvas cards")
    show.add_argument("--expires", type=int, default=120)
    manage = sub.add_parser("manage")
    manage.add_argument("id")
    manage.add_argument("action", choices=("dismiss", "pin", "unpin", "float", "canvas"))
    send = sub.add_parser("send")
    send.add_argument("message")
    args = parser.parse_args(argv)
    try:
        if args.command == "send":
            result = asyncio.run(send_text(args.message))
        elif args.command == "show":
            if args.data_file and args.data_file.stat().st_size > 48000:
                raise ValueError("Widget data exceeds 48 KiB")
            data = json.loads(args.data_file.read_text() if args.data_file else args.data)
            widget = make_widget(args.kind, args.title, data, widget_id=args.id,
                                 presentation="canvas" if args.canvas else "floating", expires_seconds=args.expires)
            result = shell_call("present", widget)
        elif args.command == "manage":
            result = shell_call("manage", {"id": args.id, "action": args.action})
        else:
            result = shell_call(args.command)
        print(compact(result))
        return 0
    except (OSError, ValueError, RuntimeError, TimeoutError, subprocess.SubprocessError) as error:
        print(compact({"ok": False, "error": str(error)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
