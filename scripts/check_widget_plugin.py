"""Bounded live check of the plugin in the existing shell, then hide test views."""
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ui.jarvis_widgets import backend


def main():
    first = backend.shell_call("status")
    if first.get("mode") != "hidden" or first.get("widgets"):
        raise RuntimeError("Close or retain existing user widgets before running the empty-state smoke check")
    ids = []
    try:
        for kind, data, presentation in (
            ("text", {"text": "JARVIS widget check: this card runs inside the existing desktop shell."}, "canvas"),
            ("chart", {"labels": ["Example A", "Example B"], "values": [2, 3], "unit": "sample values"}, "canvas"),
            ("qr", {"content": "https://example.org"}, "floating"),
        ):
            widget = backend.make_widget(kind, "Integration check · example data", data, presentation=presentation, expires_seconds=15)
            ids.append(widget["id"])
            result = backend.shell_call("present", widget)
            if result.get("id") != widget["id"]:
                raise RuntimeError("Widget identity was not acknowledged")
        time.sleep(0.5)
        status = backend.shell_call("status")
        if not status.get("canvasVisible") or len(status.get("widgets", [])) != 3:
            raise RuntimeError("Canvas did not become visible with three widgets")
        backend.shell_call("input")
        time.sleep(0.25)
        if not backend.shell_call("status").get("inputVisible"):
            raise RuntimeError("Input bar did not become visible")
        print(json.dumps({"ok": True, "widgets": 3, "canvas_verified": True, "input_verified": True}))
    finally:
        for widget_id in ids:
            backend.shell_call("manage", {"id": widget_id, "action": "dismiss"})
        backend.shell_call("close")
        status = backend.shell_call("status")
        if status.get("canvasVisible") or status.get("inputVisible") or status.get("widgets"):
            raise RuntimeError("Test surfaces were not fully dismissed")


if __name__ == "__main__": main()
