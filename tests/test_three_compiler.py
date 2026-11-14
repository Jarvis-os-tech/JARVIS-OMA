import os
from pathlib import Path
import pytest
from ui.jarvis_widgets.three_compiler import (
    find_three_live_cli,
    get_3d_runtime_dir,
    validate_script,
    compile_3d,
    is_three_live_available,
)

requires_three_live = pytest.mark.skipif(
    not is_three_live_available(),
    reason="three-live-cli executable not found in PATH or ~/.cache/three-live"
)


@requires_three_live
def test_find_three_live_cli():
    cli = find_three_live_cli()
    assert cli.is_file()
    assert cli.stat().st_mode & 0o111


def test_find_three_live_cli_env(monkeypatch, tmp_path):
    fake_cli = tmp_path / "custom_cli"
    fake_cli.write_text("#!/bin/sh\necho ok")
    fake_cli.chmod(0o755)
    monkeypatch.setenv("THREE_LIVE_CLI_BIN", str(fake_cli))
    assert find_three_live_cli() == fake_cli


def test_find_three_live_cli_not_found(monkeypatch, tmp_path):
    monkeypatch.delenv("THREE_LIVE_CLI_BIN", raising=False)
    monkeypatch.setattr("shutil.which", lambda _: None)
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path / "nonexistent_home")
    monkeypatch.setattr("ui.jarvis_widgets.three_compiler.REPO_CLI_CANDIDATE", tmp_path / "nonexistent.js")
    with pytest.raises(FileNotFoundError):
        find_three_live_cli()


def test_get_3d_runtime_dir(monkeypatch, tmp_path):
    runtime_dir = tmp_path / "runtime"
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(runtime_dir))
    d = get_3d_runtime_dir()
    assert d.is_dir()
    assert d == runtime_dir / "jarvis" / "widgets" / "3d"
    mode = d.stat().st_mode & 0o777
    assert mode == 0o700


@requires_three_live
def test_validate_valid_script():
    script = (
        "const mesh = new THREE.Mesh("
        "new THREE.BoxGeometry(1, 1, 1), "
        "new THREE.MeshBasicMaterial()); "
        "scene.add(mesh);"
    )
    result = validate_script(script)
    assert result["valid"] is True
    assert "summary" in result
    assert result["summary"]["meshCount"] == 1


@requires_three_live
def test_validate_syntax_error():
    script = "const mesh = ;;"
    result = validate_script(script)
    assert result["valid"] is False
    assert len(result["diagnostics"]) > 0


@requires_three_live
def test_compile_3d_success(tmp_path):
    script = (
        "const mesh = new THREE.Mesh("
        "new THREE.SphereGeometry(0.5, 16, 16), "
        "new THREE.MeshStandardMaterial({color: 0x38bdf8})); "
        "scene.add(mesh);"
    )
    result = compile_3d(script, "Test Sphere", output_dir=tmp_path)
    assert result["valid"] is True
    assert result["error"] is None
    assert result["title"] == "Test Sphere"
    assert Path(result["model_path"]).is_file()
    assert Path(result["model_path"]).stat().st_size > 0
    assert result["source"].startswith("file://")
    assert result["triangles"] > 0
    assert result["dimensions"]["width"] > 0
    assert result["dimensions"]["unit"] == "m"


def test_compile_3d_script_too_large(tmp_path):
    huge_script = "// " + "A" * 50000
    with pytest.raises(ValueError, match="exceeds 48 KiB limit"):
        compile_3d(huge_script, "Too Large", output_dir=tmp_path)


@requires_three_live
def test_compile_3d_syntax_error(tmp_path):
    script = "const mesh = ;;"
    result = compile_3d(script, "Syntax Error", output_dir=tmp_path)
    assert result["valid"] is False
    assert result["error"] is not None
    assert result["model_path"] == ""
    assert result["source"] == ""
