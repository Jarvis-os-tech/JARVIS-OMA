"""Compatibility alias package redirecting omarchy_voice to jarvis_control."""
import sys
import jarvis_control

# Alias modules so `import omarchy_voice.tools` works identically
from jarvis_control import *
from jarvis_control import __all__

for sub in [
    "browser", "capabilities", "cli", "config", "discovery", "feedback",
    "gemini_live", "keys", "live", "network", "page_text", "persona",
    "planner", "playback", "realtime", "security", "session", "tasks",
    "task_worker", "tools", "trace", "vision", "vision_app",
    "vision_provider", "workspace_files"
]:
    try:
        mod = __import__(f"jarvis_control.{sub}", fromlist=[sub])
        sys.modules[f"omarchy_voice.{sub}"] = mod
        globals()[sub] = mod
    except ImportError:
        pass
