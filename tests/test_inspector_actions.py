import pytest
from pathlib import Path
from unittest.mock import MagicMock


def test_handle_export_glb_success(tmp_path, monkeypatch):
    from ui.jarvis_widgets.inspector_launcher import handle_widget_action

    source_model = tmp_path / "model.glb"
    source_model.write_bytes(b"glTFfakebinary")
    dest_dir = tmp_path / "Downloads"
    dest_dir.mkdir()
    monkeypatch.setenv("HOME", str(tmp_path))

    result = handle_widget_action(f"export_glb:{source_model}")
    assert result["ok"] is True
    exported = Path(result["exported_path"])
    assert exported.is_file()
    assert exported.read_bytes() == b"glTFfakebinary"
    assert exported.parent == dest_dir


def test_handle_export_glb_missing_file(tmp_path, monkeypatch):
    from ui.jarvis_widgets.inspector_launcher import handle_widget_action

    monkeypatch.setenv("HOME", str(tmp_path))
    missing_file = tmp_path / "nonexistent.glb"

    result = handle_widget_action(f"export_glb:{missing_file}")
    assert result["ok"] is False
    assert result["error"] == "Model file not found"


def test_handle_inspect_3d_success(tmp_path, monkeypatch):
    import webbrowser
    from ui.jarvis_widgets.inspector_launcher import handle_widget_action

    source_model = tmp_path / "model.glb"
    source_model.write_bytes(b"glTFfakebinary")

    opened_urls = []
    monkeypatch.setattr(webbrowser, "open", lambda url: opened_urls.append(url) or True)

    result = handle_widget_action(f"inspect_3d:{source_model}")
    assert result["ok"] is True
    assert "url" in result
    url = result["url"]
    assert url.startswith("file://")
    assert "viewer.html?model=" in url
    assert source_model.as_uri() in url
    assert opened_urls == [url]

    # Verify viewer.html actually exists at the resolved path
    viewer_path = Path(__file__).resolve().parent.parent / "ui" / "jarvis_widgets" / "inspector" / "viewer.html"
    assert viewer_path.is_file()


def test_handle_inspect_3d_missing_file(tmp_path):
    from ui.jarvis_widgets.inspector_launcher import handle_widget_action

    missing_file = tmp_path / "nonexistent.glb"
    result = handle_widget_action(f"inspect_3d:{missing_file}")
    assert result["ok"] is False
    assert result["error"] == "Model file not found"


def test_handle_unknown_action():
    from ui.jarvis_widgets.inspector_launcher import handle_widget_action

    result = handle_widget_action("unknown_action:foo")
    assert result["ok"] is False
    assert result["error"] == "Unknown action: unknown_action:foo"


def test_viewer_html_structure():
    viewer_path = Path(__file__).resolve().parent.parent / "ui" / "jarvis_widgets" / "inspector" / "viewer.html"
    assert viewer_path.is_file()
    content = viewer_path.read_text(encoding="utf-8")

    # Dark-themed colors
    assert "#0b1118" in content.lower()
    assert "#55ddea" in content.lower()

    # 3D model-viewer and controls
    assert "<model-viewer" in content
    assert "camera-controls" in content
    assert "Reset View" in content
    assert "Toggle Auto-Rotate" in content

    # Query param loader
    assert "URLSearchParams" in content
    assert "model" in content
