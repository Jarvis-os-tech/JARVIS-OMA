import pytest
import webbrowser
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import url2pathname
from ui.jarvis_widgets.backend import make_widget
from ui.jarvis_widgets.inspector_launcher import handle_widget_action


def test_e2e_create_and_export_3d_widget(tmp_path, monkeypatch):
    """Full lifecycle test for 3D widget: creation, compilation, export, and inspector launch."""
    # Resolve three-live-cli before isolating HOME so the cached binary remains available
    from ui.jarvis_widgets.three_compiler import find_three_live_cli
    cli_bin = find_three_live_cli()

    # 1. Isolate HOME to tmp_path
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("THREE_LIVE_CLI_BIN", str(cli_bin))

    three_script = """
    const geom = new THREE.CylinderGeometry(0.5, 0.5, 1.2, 32);
    const mat = new THREE.MeshStandardMaterial({color: 0xffaa00, metalness: 0.5});
    scene.add(new THREE.Mesh(geom, mat));
    """

    # 2. Call make_widget for 3D
    widget = make_widget(
        "3d",
        "Test Cylinder",
        {"script": three_script, "caption": "Orange Cylinder Widget"}
    )

    # 3. Validate widget kind, metadata, and telemetry
    assert widget["kind"] == "3d"
    assert widget["title"] == "Test Cylinder"
    assert widget["data"]["caption"] == "Orange Cylinder Widget"
    assert widget["data"]["triangles"] > 0
    assert widget["data"]["vertices"] > 0
    assert widget["data"]["dimensions"]["height"] == 1.2
    assert widget["data"]["dimensions"]["width"] > 0
    assert widget["data"]["dimensions"]["depth"] > 0
    assert widget["data"]["dimensions"]["unit"] == "m"

    # Validate compiled GLB model file
    model_path = Path(widget["data"]["model_path"])
    assert model_path.is_file()
    assert model_path.stat().st_size > 0

    # Validate turntable animation preview source
    turntable_uri = widget["data"]["source"]
    assert turntable_uri.startswith("file://")
    turntable_path = Path(url2pathname(urlparse(turntable_uri).path))
    assert turntable_path.is_file()
    assert turntable_path.stat().st_size > 0

    # 4. Dispatch export_glb action and verify exported file in ~/Downloads/
    export_action = next(a["action"] for a in widget["data"]["actions"] if a["label"] == "Export GLB")
    export_res = handle_widget_action(export_action)
    assert export_res["ok"] is True
    exported_file = Path(export_res["exported_path"])
    assert exported_file.is_file()
    assert exported_file.parent == tmp_path / "Downloads"
    assert exported_file.read_bytes() == model_path.read_bytes()

    # 5. Dispatch inspect_3d action with mocked webbrowser.open
    opened_urls = []
    monkeypatch.setattr(webbrowser, "open", lambda url: opened_urls.append(url) or True)

    inspect_action = next(a["action"] for a in widget["data"]["actions"] if a["label"] == "Inspect 3D")
    inspect_res = handle_widget_action(inspect_action)
    assert inspect_res["ok"] is True
    assert "url" in inspect_res
    file_url = inspect_res["url"]
    assert file_url.startswith("file://")
    assert "viewer.html?model=" in file_url
    assert model_path.as_uri() in file_url
    assert opened_urls == [file_url]

    # Verify viewer.html file exists on disk
    viewer_path = Path(url2pathname(urlparse(file_url.split("?")[0]).path))
    assert viewer_path.is_file()


def test_e2e_invalid_script_raises_diagnostic():
    """Verify broken Three.js scripts fail cleanly with a descriptive diagnostic error."""
    broken_script = "const mesh = ;; invalid js syntax"
    with pytest.raises(ValueError, match="3D script error:"):
        make_widget("3d", "Broken Cylinder", {"script": broken_script})
