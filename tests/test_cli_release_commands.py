import subprocess
import sys
from pathlib import Path

def test_jarvis_cli_help_includes_release_commands():
    bin_jarvis = Path(__file__).resolve().parents[1] / "bin" / "jarvis"
    res = subprocess.run([str(bin_jarvis), "--help"], capture_output=True, text=True, check=True)
    assert "update" in res.stdout
    assert "rollback" in res.stdout
    assert "releases" in res.stdout

def test_jarvis_release_script_help():
    script = Path(__file__).resolve().parents[1] / "scripts" / "jarvis_release.py"
    res = subprocess.run([sys.executable, str(script), "--help"], capture_output=True, text=True, check=True)
    assert "check" in res.stdout
    assert "update" in res.stdout
    assert "rollback" in res.stdout
    assert "list" in res.stdout
