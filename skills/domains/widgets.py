"""Declarative view adapters; all system effects stay in existing JARVIS tools."""
import asyncio
import json
import subprocess

from skills.errors import SkillError
from ui.jarvis_widgets import backend
from ui.jarvis_widgets.view_schema import describe

ADAPTERS = {
    "widgets.show": "_adapter_show_widget",
    "widgets.canvas": "_adapter_manage_canvas",
    "widgets.manage": "_adapter_manage_widget",
    "widgets.schema": "_adapter_widget_schema",
}
ADAPTER_COMMANDS = {name: ("omarchy-shell",) for name in ADAPTERS}


class WidgetsDomain:
    async def _adapter_widget_schema(self):
        return describe()

    async def _adapter_show_widget(self, kind, title, data_json, widget_id="", presentation="floating", expires_seconds=120):
        def present():
            widget = backend.make_widget(kind, title, json.loads(data_json), widget_id=widget_id,
                                         presentation=presentation, expires_seconds=expires_seconds)
            return backend.shell_call("present", widget)
        try:
            return await asyncio.to_thread(present)
        except (ValueError, OSError, RuntimeError, subprocess.SubprocessError) as error:
            raise SkillError(str(error)) from error

    async def _adapter_manage_canvas(self, action):
        if action not in ("open", "close", "input", "clear", "clear_all", "status"):
            raise SkillError("Unsupported canvas action")
        try:
            return await asyncio.to_thread(backend.shell_call, "clearAll" if action == "clear_all" else action)
        except (OSError, RuntimeError, subprocess.SubprocessError) as error:
            raise SkillError(str(error)) from error

    async def _adapter_manage_widget(self, action, widget_id="", x=None, y=None):
        if action not in ("dismiss", "pin", "unpin", "float", "canvas", "move", "state"):
            raise SkillError("Unsupported widget action")
        try:
            payload = {"id": widget_id, "action": action}
            if action == "move":
                if type(x) is not int or type(y) is not int or not 0 <= x <= 100 or not 0 <= y <= 100:
                    raise SkillError("Move needs integer x and y percentages between 0 and 100")
                payload.update(x=x / 100, y=y / 100)
            return await asyncio.to_thread(backend.shell_call, "manage", payload)
        except (OSError, RuntimeError, subprocess.SubprocessError) as error:
            raise SkillError(str(error)) from error
