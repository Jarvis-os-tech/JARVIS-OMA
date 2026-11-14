import pytest
from ui.jarvis_widgets.backend import validate, make_widget, KINDS, FIELDS
from ui.jarvis_widgets.three_compiler import is_three_live_available

requires_three_live = pytest.mark.skipif(
    not is_three_live_available(),
    reason="three-live-cli not installed"
)


def test_3d_in_kinds():
    assert "3d" in KINDS
    assert "script" in FIELDS["3d"]
    assert "caption" in FIELDS["3d"]
    assert "actions" in FIELDS["3d"]


@requires_three_live
def test_make_widget_3d_valid():
    script = (
        "const mesh = new THREE.Mesh("
        "new THREE.BoxGeometry(2, 1, 0.5), "
        "new THREE.MeshStandardMaterial()); "
        "scene.add(mesh);"
    )
    widget = make_widget("3d", "Test Box", {"script": script, "caption": "A simple box"})
    assert widget["kind"] == "3d"
    assert widget["title"] == "Test Box"
    assert widget["data"]["source"].startswith("file://")
    assert widget["data"]["model_path"].endswith(".glb")
    assert widget["data"]["script_path"].endswith(".js")
    assert widget["data"]["caption"] == "A simple box"
    assert widget["data"]["dimensions"]["width"] == 2.0
    assert len(widget["data"]["actions"]) >= 2

    labels = [a["label"] for a in widget["data"]["actions"]]
    assert "Inspect 3D" in labels
    assert "Export GLB" in labels

    inspect_action = next(a for a in widget["data"]["actions"] if a["label"] == "Inspect 3D")
    assert inspect_action["action"].startswith("inspect_3d:")
    assert inspect_action["action"].endswith(widget["data"]["model_path"])
    assert inspect_action["primary"] is True

    export_action = next(a for a in widget["data"]["actions"] if a["label"] == "Export GLB")
    assert export_action["action"].startswith("export_glb:")
    assert export_action["action"].endswith(widget["data"]["model_path"])
    assert export_action["primary"] is False


@requires_three_live
def test_make_widget_3d_invalid_script():
    with pytest.raises(ValueError, match="3D script error"):
        make_widget("3d", "Broken", {"script": "const m = ;;"})


def test_make_widget_3d_empty_or_missing_script():
    with pytest.raises(ValueError, match="3D widget requires a Three.js script"):
        make_widget("3d", "Empty", {"script": "   "})

    with pytest.raises(ValueError, match="3D widget requires a Three.js script"):
        make_widget("3d", "Missing", {})


def test_make_widget_3d_unexpected_field():
    with pytest.raises(ValueError, match="Unexpected widget fields"):
        make_widget("3d", "Unexpected", {"script": "const a = 1;", "unknown": 123})


@requires_three_live
def test_make_widget_3d_custom_actions():
    script = (
        "const mesh = new THREE.Mesh("
        "new THREE.BoxGeometry(1, 1, 1), "
        "new THREE.MeshBasicMaterial()); "
        "scene.add(mesh);"
    )
    custom_action = {"label": "Reset View", "action": "reset_camera", "primary": False}
    widget = make_widget("3d", "Box with Custom Action", {"script": script, "actions": [custom_action]})
    labels = [a["label"] for a in widget["data"]["actions"]]
    assert "Inspect 3D" in labels
    assert "Export GLB" in labels
    assert "Reset View" in labels
    assert widget["data"]["actions"][-1] == custom_action


def test_make_widget_3d_script_too_large():
    huge_script = "// " + "A" * 50000
    with pytest.raises(ValueError):
        make_widget("3d", "Too Big", {"script": huge_script})
