"""Action dispatcher for 3D widget interactions."""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import webbrowser


def handle_widget_action(action_str: str) -> dict:
    """Handle widget action string (e.g. export_glb:<path>, inspect_3d:<path>)."""
    if action_str.startswith("export_glb:"):
        source = Path(action_str.split(":", 1)[1]).resolve()
        if not source.is_file():
            return {"ok": False, "error": "Model file not found"}
        downloads = Path.home() / "Downloads"
        downloads.mkdir(parents=True, exist_ok=True)
        dest = downloads / source.name
        shutil.copy2(source, dest)
        return {"ok": True, "exported_path": str(dest)}

    if action_str.startswith("inspect_3d:"):
        model_path = Path(action_str.split(":", 1)[1]).resolve()
        if not model_path.is_file():
            return {"ok": False, "error": "Model file not found"}
        viewer_html = (Path(__file__).parent / "inspector" / "viewer.html").resolve()
        file_url = f"{viewer_html.as_uri()}?model={model_path.as_uri()}"
        webbrowser.open(file_url)
        return {"ok": True, "url": file_url}

    return {"ok": False, "error": f"Unknown action: {action_str}"}
