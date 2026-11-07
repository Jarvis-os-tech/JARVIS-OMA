# Three-Live 3D Desktop Widgets Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate `google/three-live` into JARVIS OS's `ui/jarvis_widgets` subsystem to enable dynamic, AI-generated procedural 3D models and CAD assets to be compiled and displayed as interactive 360° turntable cards on the Wayland desktop with one-click 3D inspection and GLB export.

**Architecture:** Extend `ui/jarvis_widgets/backend.py` with a first-class `kind: "3d"` widget type backed by an asynchronous compiler bridge (`ui/jarvis_widgets/three_compiler.py`). The compiler runs `three-live-cli` in a 5.0-second sandboxed fence to validate syntax, convert Three.js to binary `.glb`, generate an optimized 360° turntable `.gif`, and extract geometric telemetry. Quickshell (`WidgetCard.qml`) renders the animated turntable and telemetry badge, with card actions for interactive inspection and file export.

**Tech Stack:** Python 3.12+, Three.js, `google/three-live` (`three-live-cli-linux-x86_64`), Qt6 / Quickshell QML, Wayland / Hyprland.

**Spec:** `docs/superpowers/specs/2026-11-07-three-live-desktop-widgets-design.md`

## Global Constraints

- Android / iOS mobile implementation is explicitly excluded.
- The voice subsystem (`voice_layer/`, `jarvis_voice/`, `audio/`) is frozen under `audio/.voice_lock.json` and must remain completely untouched.
- All temporary and compiled 3D assets must be stored in `$XDG_RUNTIME_DIR/jarvis/widgets/3d/` with strict mode `0700` permissions.
- Script validation and compilation must enforce a 5.0-second timeout fence to avoid hanging desktop processes.
- Maximum input script size: 48 KiB. Maximum output GLB size: 64 MiB.

---

### Task 1: Compiler & CLI Execution Bridge (`ui/jarvis_widgets/three_compiler.py`)

**Files:**
- Create: `ui/jarvis_widgets/three_compiler.py`
- Test: `tests/test_three_compiler.py`

**Interfaces:**
- Produces:
  ```python
  def find_three_live_cli() -> Path: ...
  def validate_script(script: str, cli_path: Path | None = None) -> dict: ...
  def compile_3d(script: str, title: str, output_dir: Path | None = None) -> dict:
      # Returns: {
      #     "valid": bool,
      #     "source": str,        # file URI to turntable.gif
      #     "model_path": str,    # absolute path to model.glb
      #     "script_path": str,   # absolute path to scene.js
      #     "dimensions": {"width": float, "height": float, "depth": float, "unit": "m"},
      #     "triangles": int,
      #     "vertices": int,
      #     "error": str | None
      # }
  ```

- [ ] **Step 1: Write the failing unit tests for `three_compiler.py`**

```python
# tests/test_three_compiler.py
import pytest
from pathlib import Path
from ui.jarvis_widgets.three_compiler import find_three_live_cli, validate_script, compile_3d

def test_find_three_live_cli():
    cli = find_three_live_cli()
    assert cli.is_file()
    assert cli.stat().st_mode & 0o111

def test_validate_valid_script():
    script = "const mesh = new THREE.Mesh(new THREE.BoxGeometry(1, 1, 1), new THREE.MeshBasicMaterial()); scene.add(mesh);"
    result = validate_script(script)
    assert result["valid"] is True
    assert "summary" in result
    assert result["summary"]["meshCount"] == 1

def test_validate_syntax_error():
    script = "const mesh = ;;"
    result = validate_script(script)
    assert result["valid"] is False
    assert len(result["diagnostics"]) > 0

def test_compile_3d_success(tmp_path):
    script = "const mesh = new THREE.Mesh(new THREE.SphereGeometry(0.5, 16, 16), new THREE.MeshStandardMaterial({color: 0x38bdf8})); scene.add(mesh);"
    result = compile_3d(script, "Test Sphere", output_dir=tmp_path)
    assert result["valid"] is True
    assert Path(result["model_path"]).is_file()
    assert Path(result["model_path"]).stat().st_size > 0
    assert result["source"].startswith("file://")
    assert result["triangles"] > 0
    assert result["dimensions"]["width"] > 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_three_compiler.py -v`
Expected: FAIL with ModuleNotFoundError or ImportError (`ui.jarvis_widgets.three_compiler`).

- [ ] **Step 3: Implement `ui/jarvis_widgets/three_compiler.py`**

```python
"""Bridge to three-live on-device JIT compiler and headless renderer."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile
import uuid


def find_three_live_cli() -> Path:
    env_bin = os.environ.get("THREE_LIVE_CLI_BIN")
    if env_bin and Path(env_bin).is_file():
        return Path(env_bin)

    system_bin = shutil.which("three-live-cli")
    if system_bin:
        return Path(system_bin)

    cache_dir = Path.home() / ".cache" / "three-live"
    if cache_dir.is_dir():
        for candidate in cache_dir.glob("**/three-live-cli-linux-x86_64"):
            if candidate.is_file():
                return candidate

    repo_candidate = Path("/tmp/three-live/bin/three-live-cli.js")
    if repo_candidate.is_file():
        return repo_candidate

    raise FileNotFoundError("three-live-cli executable not found in PATH or ~/.cache/three-live")


def get_3d_runtime_dir() -> Path:
    root = (Path(os.environ.get("XDG_RUNTIME_DIR") or Path.home() / ".local/state")
            / "jarvis" / "widgets" / "3d")
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    info = root.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise ValueError("3D runtime directory must be private and owned by this user")
    return root


def validate_script(script: str, cli_path: Path | None = None) -> dict:
    cli = cli_path or find_three_live_cli()
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
        f.write(script)
        temp_js = Path(f.name)

    try:
        cmd = [str(cli)] if not str(cli).endswith(".js") else ["node", str(cli)]
        cmd.extend(["validate", "--json", str(temp_js)])
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=5.0)
        if proc.stdout.strip():
            return json.loads(proc.stdout.strip())
        return {"valid": False, "diagnostics": [{"message": proc.stderr.strip() or "Validation failed"}]}
    finally:
        temp_js.unlink(missing_ok=True)


def compile_3d(script: str, title: str, output_dir: Path | None = None) -> dict:
    if len(script.encode("utf-8")) > 48000:
        raise ValueError("3D script exceeds 48 KiB limit")

    cli = find_three_live_cli()
    run_dir = output_dir or get_3d_runtime_dir()
    run_dir.mkdir(parents=True, exist_ok=True, mode=0o700)

    token = uuid.uuid4().hex[:12]
    script_file = run_dir / f"scene_{token}.js"
    glb_file = run_dir / f"model_{token}.glb"
    gif_file = run_dir / f"turntable_{token}.gif"

    script_file.write_text(script, encoding="utf-8")

    try:
        cmd_base = [str(cli)] if not str(cli).endswith(".js") else ["node", str(cli)]

        # 1. Validate and extract spatial bounds
        val_proc = subprocess.run(cmd_base + ["validate", "--json", str(script_file)],
                                  capture_output=True, text=True, timeout=5.0)
        val_data = json.loads(val_proc.stdout.strip()) if val_proc.stdout.strip() else {}
        if not val_data.get("valid", False):
            diag = val_data.get("diagnostics", [{}])[0].get("message", "Script syntax or runtime error")
            return {
                "valid": False,
                "error": diag,
                "script_path": str(script_file),
                "model_path": "",
                "source": "",
                "dimensions": {"width": 0.0, "height": 0.0, "depth": 0.0, "unit": "m"},
                "triangles": 0,
                "vertices": 0
            }

        # 2. Convert to GLB
        subprocess.run(cmd_base + ["convert", str(script_file), "-o", str(glb_file)],
                       check=True, capture_output=True, text=True, timeout=5.0)

        # 3. Render 360 turntable GIF (16 frames)
        subprocess.run(cmd_base + ["render", str(script_file), "--turntable", "--frames", "16", "-o", str(gif_file)],
                       check=True, capture_output=True, text=True, timeout=5.0)

        summary = val_data.get("summary") or {}
        bounds = summary.get("worldBounds") or {}
        size = bounds.get("size") or [1.0, 1.0, 1.0]
        index_count = summary.get("indexCount") or 0
        vertex_count = summary.get("vertexCount") or 0

        return {
            "valid": True,
            "error": None,
            "title": title,
            "source": gif_file.as_uri(),
            "model_path": str(glb_file.resolve()),
            "script_path": str(script_file.resolve()),
            "dimensions": {
                "width": round(float(size[0]), 3),
                "height": round(float(size[1]), 3),
                "depth": round(float(size[2]), 3),
                "unit": "m"
            },
            "triangles": index_count // 3,
            "vertices": vertex_count
        }
    except Exception as exc:
        return {
            "valid": False,
            "error": str(exc),
            "script_path": str(script_file),
            "model_path": "",
            "source": "",
            "dimensions": {"width": 0.0, "height": 0.0, "depth": 0.0, "unit": "m"},
            "triangles": 0,
            "vertices": 0
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_three_compiler.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add ui/jarvis_widgets/three_compiler.py tests/test_three_compiler.py
git commit -m "feat(widgets): add three-live compiler bridge and unit tests"
```

---

### Task 2: Backend Widget Integration (`ui/jarvis_widgets/backend.py`)

**Files:**
- Modify: `ui/jarvis_widgets/backend.py:22-150`
- Test: `tests/test_widget_3d.py`

**Interfaces:**
- Consumes: `three_compiler.compile_3d(script, title)`
- Produces: `make_widget("3d", title, data)` with enriched 3D payload and actions.

- [ ] **Step 1: Write the failing unit tests for widget kind `"3d"`**

```python
# tests/test_widget_3d.py
import pytest
from ui.jarvis_widgets.backend import validate, make_widget, KINDS, FIELDS

def test_3d_in_kinds():
    assert "3d" in KINDS
    assert "script" in FIELDS["3d"]

def test_make_widget_3d_valid(tmp_path):
    script = "const mesh = new THREE.Mesh(new THREE.BoxGeometry(2, 1, 0.5), new THREE.MeshStandardMaterial()); scene.add(mesh);"
    widget = make_widget("3d", "Test Box", {"script": script, "caption": "A simple box"})
    assert widget["kind"] == "3d"
    assert widget["title"] == "Test Box"
    assert widget["data"]["source"].startswith("file://")
    assert widget["data"]["model_path"].endswith(".glb")
    assert widget["data"]["dimensions"]["width"] == 2.0
    assert len(widget["data"]["actions"]) >= 2
    labels = [a["label"] for a in widget["data"]["actions"]]
    assert "Inspect 3D" in labels
    assert "Export GLB" in labels

def test_make_widget_3d_invalid_script():
    with pytest.raises(ValueError, match="3D script error"):
        make_widget("3d", "Broken", {"script": "const m = ;;"})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_widget_3d.py -v`
Expected: FAIL with "Unsupported widget kind" or AssertionError.

- [ ] **Step 3: Modify `ui/jarvis_widgets/backend.py` to support `kind: "3d"`**

Add `"3d"` to `KINDS` and `FIELDS`:
```python
KINDS = {"view", "text", "qr", "image", "pip", "table", "chart", "progress", "3d"}
FIELDS["3d"] = {"script", "title", "caption", "actions"}
```

In `validate(kind, data)`:
```python
    if kind == "3d":
        script_content = text(data.get("script", ""), 48000)
        if not script_content.strip():
            raise ValueError("3D widget requires a Three.js script")
        from ui.jarvis_widgets.three_compiler import compile_3d
        compiled = compile_3d(script_content, title="3D Model")
        if not compiled.get("valid", False):
            raise ValueError(f"3D script error: {compiled.get('error', 'Compilation failed')}")
        
        actions = [
            {"label": "Inspect 3D", "action": f"inspect_3d:{compiled['model_path']}", "primary": True},
            {"label": "Export GLB", "action": f"export_glb:{compiled['model_path']}", "primary": False}
        ]
        if "actions" in data and isinstance(data["actions"], list):
            actions.extend(data["actions"])

        return {
            "source": compiled["source"],
            "model_path": compiled["model_path"],
            "script_path": compiled["script_path"],
            "caption": text(data.get("caption", ""), 1000),
            "dimensions": compiled["dimensions"],
            "triangles": compiled["triangles"],
            "vertices": compiled["vertices"],
            "actions": actions
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_widget_3d.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add ui/jarvis_widgets/backend.py tests/test_widget_3d.py
git commit -m "feat(widgets): register 3d widget kind with three-live compiler in backend"
```

---

### Task 3: Desktop QML Card Presentation (`ui/jarvis_widgets/WidgetCard.qml`)

**Files:**
- Modify: `ui/jarvis_widgets/WidgetCard.qml:87-95, 224-263`

**Interfaces:**
- Consumes: `card.widget.kind === "3d"`, `card.widgetData.source`, `card.widgetData.dimensions`, `card.widgetData.triangles`
- Produces: Visual turntable animation with spatial badge and action triggers.

- [ ] **Step 1: Check existing `WidgetCard.qml` structure and verify QML syntax**

Run: `quickshell -p "ui/jarvis_widgets" --help` to confirm quickshell parser is ready.

- [ ] **Step 2: Add `threeDBlock` component in `ui/jarvis_widgets/WidgetCard.qml`**

In the `Loader` `sourceComponent` mapping (lines 90-95):
```qml
sourceComponent: card.widget.kind === "3d" ? threeDBlock
    : card.widget.kind === "task" ? taskBlock
    : card.widget.kind === "view" ? generatedBlock
    ...
```

Add `Component { id: threeDBlock ... }`:
```qml
    Component {
        id: threeDBlock
        ColumnLayout {
            spacing: 8
            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                color: "#101923"
                radius: 12
                clip: true

                AnimatedImage {
                    id: turntableAnim
                    anchors.fill: parent
                    source: String(card.widgetData.source || "")
                    fillMode: Image.PreserveAspectFit
                    asynchronous: true
                    playing: card.activeMedia
                }

                Rectangle {
                    anchors.top: parent.top
                    anchors.right: parent.right
                    anchors.margins: 8
                    radius: 6
                    color: "#A014202D"
                    border.color: "#354A5E"
                    implicitHeight: 22
                    implicitWidth: badgeText.implicitWidth + 12

                    Text {
                        id: badgeText
                        anchors.centerIn: parent
                        text: "3D LIVE"
                        color: "#55DDEA"
                        font.pixelSize: 10
                        font.weight: Font.Bold
                    }
                }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 12
                visible: card.widgetData.dimensions !== undefined

                Text {
                    Layout.fillWidth: true
                    text: {
                        var d = card.widgetData.dimensions || {width: 0, height: 0, depth: 0, unit: "m"}
                        return d.width + " × " + d.height + " × " + d.depth + " " + (d.unit || "m") + "  •  " + (card.widgetData.triangles || 0) + " tris"
                    }
                    color: "#8DA0B5"
                    font.pixelSize: 11
                    elide: Text.ElideRight
                }
            }

            Text {
                Layout.fillWidth: true
                visible: text.length > 0
                text: String(card.widgetData.caption || "")
                textFormat: Text.PlainText
                color: "#B4BFCE"
                wrapMode: Text.WordWrap
                font.pixelSize: 13
            }
        }
    }
```

- [ ] **Step 3: Verify QML component syntax with quickshell**

Run: `python3 -c "import subprocess; res = subprocess.run(['quickshell', '-p', 'ui/jarvis_widgets/WidgetCard.qml'], capture_output=True, text=True, timeout=1); print(res.stderr)"`
Confirm no fatal QML syntax errors.

- [ ] **Step 4: Commit**

```bash
git add ui/jarvis_widgets/WidgetCard.qml
git commit -m "feat(ui): add 3d turntable card component with spatial telemetry in WidgetCard.qml"
```

---

### Task 4: Interactive Three-Live Inspector & Action Handlers

**Files:**
- Create: `ui/jarvis_widgets/inspector/viewer.html`
- Create: `ui/jarvis_widgets/inspector_launcher.py`
- Modify: `ui/jarvis_widgets/backend.py` (action routing for `inspect_3d` and `export_glb`)
- Test: `tests/test_inspector_actions.py`

**Interfaces:**
- Consumes: Action clicks `inspect_3d:<model_path>` and `export_glb:<model_path>`
- Produces: Opens interactive 3D browser canvas on `inspect_3d`; copies file to `~/Downloads/` on `export_glb`.

- [ ] **Step 1: Write unit tests for action routing**

```python
# tests/test_inspector_actions.py
import pytest
from pathlib import Path
from ui.jarvis_widgets.inspector_launcher import handle_widget_action

def test_handle_export_glb(tmp_path, monkeypatch):
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_inspector_actions.py -v`
Expected: FAIL with ModuleNotFoundError (`ui.jarvis_widgets.inspector_launcher`).

- [ ] **Step 3: Implement `ui/jarvis_widgets/inspector/viewer.html`**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>JARVIS 3D Inspector</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    body, html { margin: 0; padding: 0; width: 100%; height: 100%; background: #0b1118; color: #f2f5fa; font-family: system-ui, sans-serif; overflow: hidden; }
    #canvas-container { width: 100%; height: 100%; display: flex; align-items: center; justify-content: center; }
    #header { position: absolute; top: 12px; left: 16px; z-index: 10; display: flex; gap: 12px; align-items: center; background: rgba(20, 32, 45, 0.85); padding: 8px 16px; border-radius: 10px; border: 1px solid #354a5e; }
    #header h1 { font-size: 14px; margin: 0; font-weight: 600; color: #55ddea; }
    #controls { position: absolute; bottom: 16px; left: 50%; transform: translateX(-50%); z-index: 10; display: flex; gap: 8px; background: rgba(20, 32, 45, 0.85); padding: 6px 12px; border-radius: 8px; border: 1px solid #354a5e; }
    button { background: #1c2b3c; color: #f2f5fa; border: 1px solid #4a6075; border-radius: 6px; padding: 6px 12px; cursor: pointer; font-size: 12px; }
    button:hover { background: #273b52; border-color: #55ddea; }
  </style>
  <script type="module" src="https://ajax.googleapis.com/ajax/libs/model-viewer/4.0.0/model-viewer.min.js"></script>
</head>
<body>
  <div id="header">
    <h1>JARVIS 3D Spatial Inspector</h1>
  </div>
  <div id="canvas-container">
    <model-viewer id="viewer" src="" camera-controls auto-rotate shadow-intensity="1" ar style="width: 100%; height: 100%;">
    </model-viewer>
  </div>
  <div id="controls">
    <button onclick="document.getElementById('viewer').cameraOrbit = '0deg 75deg 105%'">Reset View</button>
    <button onclick="const v = document.getElementById('viewer'); v.autoRotate = !v.autoRotate;">Toggle Auto-Rotate</button>
  </div>
  <script>
    const urlParams = new URLSearchParams(window.location.search);
    const model = urlParams.get('model');
    if (model) {
      document.getElementById('viewer').src = model;
    }
  </script>
</body>
</html>
```

- [ ] **Step 4: Implement `ui/jarvis_widgets/inspector_launcher.py` and backend action hook**

```python
"""Action dispatcher for 3D widget interactions."""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import webbrowser


def handle_widget_action(action_str: str) -> dict:
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
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_inspector_actions.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add ui/jarvis_widgets/inspector/ ui/jarvis_widgets/inspector_launcher.py tests/test_inspector_actions.py
git commit -m "feat(widgets): add 3d standalone inspector viewer and action handlers"
```

---

### Task 5: End-to-End System Test & Voice Lock Verification

**Files:**
- Create: `tests/test_e2e_3d_widget.py`
- Verify: `scripts/verify_voice_lock.py`

- [ ] **Step 1: Write End-to-End integration test**

```python
# tests/test_e2e_3d_widget.py
import pytest
from pathlib import Path
from ui.jarvis_widgets.backend import make_widget
from ui.jarvis_widgets.inspector_launcher import handle_widget_action

def test_e2e_create_and_export_3d_widget(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    three_script = """
    const geom = new THREE.CylinderGeometry(0.5, 0.5, 1.2, 32);
    const mat = new THREE.MeshStandardMaterial({color: 0xffaa00, metalness: 0.5});
    scene.add(new THREE.Mesh(geom, mat));
    """
    widget = make_widget("3d", "Test Cylinder", {"script": three_script, "caption": "Orange Cylinder"})
    assert widget["kind"] == "3d"
    assert widget["data"]["triangles"] > 0
    assert widget["data"]["dimensions"]["height"] == 1.2
    
    # Test export action
    export_action = next(a["action"] for a in widget["data"]["actions"] if a["label"] == "Export GLB")
    res = handle_widget_action(export_action)
    assert res["ok"] is True
    assert Path(res["exported_path"]).is_file()
```

- [ ] **Step 2: Run all widget test suites**

Run: `pytest tests/test_three_compiler.py tests/test_widget_3d.py tests/test_inspector_actions.py tests/test_e2e_3d_widget.py -v`
Expected: PASS (100% passing).

- [ ] **Step 3: Execute voice subsystem lock verification**

Run: `python scripts/verify_voice_lock.py`
Expected: PASS: 0 changes, checksums match recorded baseline.

- [ ] **Step 4: Commit**

```bash
git add tests/test_e2e_3d_widget.py
git commit -m "test(widgets): add end-to-end 3d widget test and verify voice lock"
```
