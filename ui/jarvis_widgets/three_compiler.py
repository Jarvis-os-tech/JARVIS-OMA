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

REPO_CLI_CANDIDATE = Path("/tmp/three-live/bin/three-live-cli.js")


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

    if REPO_CLI_CANDIDATE.is_file():
        return REPO_CLI_CANDIDATE

    raise FileNotFoundError("three-live-cli executable not found in PATH or ~/.cache/three-live")


def get_3d_runtime_dir() -> Path:
    root = (
        Path(os.environ.get("XDG_RUNTIME_DIR") or Path.home() / ".local/state")
        / "jarvis"
        / "widgets"
        / "3d"
    )
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        os.chmod(root, 0o700)
    except OSError:
        pass
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
        return {
            "valid": False,
            "diagnostics": [{"message": proc.stderr.strip() or "Validation failed"}],
        }
    except Exception as exc:
        return {
            "valid": False,
            "diagnostics": [{"message": str(exc)}],
        }
    finally:
        temp_js.unlink(missing_ok=True)


def compile_3d(script: str, title: str, output_dir: Path | None = None) -> dict:
    if len(script.encode("utf-8")) > 48000:
        raise ValueError("3D script exceeds 48 KiB limit")

    cli = find_three_live_cli()
    run_dir = output_dir or get_3d_runtime_dir()
    run_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        os.chmod(run_dir, 0o700)
    except OSError:
        pass

    token = uuid.uuid4().hex[:12]
    script_file = run_dir / f"scene_{token}.js"
    glb_file = run_dir / f"model_{token}.glb"
    gif_file = run_dir / f"turntable_{token}.gif"

    script_file.write_text(script, encoding="utf-8")

    try:
        cmd_base = [str(cli)] if not str(cli).endswith(".js") else ["node", str(cli)]

        # 1. Validate and extract spatial bounds
        val_proc = subprocess.run(
            cmd_base + ["validate", "--json", str(script_file)],
            capture_output=True,
            text=True,
            timeout=5.0,
        )
        val_data = json.loads(val_proc.stdout.strip()) if val_proc.stdout.strip() else {}
        if not val_data.get("valid", False):
            diagnostics = val_data.get("diagnostics") or []
            diag = (
                diagnostics[0].get("message", "Script syntax or runtime error")
                if diagnostics
                else "Script syntax or runtime error"
            )
            return {
                "valid": False,
                "error": diag,
                "title": title,
                "script_path": str(script_file),
                "model_path": "",
                "source": "",
                "dimensions": {"width": 0.0, "height": 0.0, "depth": 0.0, "unit": "m"},
                "triangles": 0,
                "vertices": 0,
            }

        # 2. Convert to GLB
        subprocess.run(
            cmd_base + ["convert", str(script_file), "-o", str(glb_file)],
            check=True,
            capture_output=True,
            text=True,
            timeout=5.0,
        )

        # 3. Render 360 turntable GIF (16 frames)
        subprocess.run(
            cmd_base + ["render", str(script_file), "--turntable", "--frames", "16", "-o", str(gif_file)],
            check=True,
            capture_output=True,
            text=True,
            timeout=5.0,
        )

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
                "unit": "m",
            },
            "triangles": index_count // 3,
            "vertices": vertex_count,
        }
    except Exception as exc:
        return {
            "valid": False,
            "error": str(exc),
            "title": title,
            "script_path": str(script_file),
            "model_path": "",
            "source": "",
            "dimensions": {"width": 0.0, "height": 0.0, "depth": 0.0, "unit": "m"},
            "triangles": 0,
            "vertices": 0,
        }
