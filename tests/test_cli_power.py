import subprocess
import sys
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
BIN_JARVIS = REPO_ROOT / "bin" / "jarvis"
SCRIPT_POWER = REPO_ROOT / "scripts" / "jarvis_power.py"


def test_cli_power_status():
    proc = subprocess.run([sys.executable, str(SCRIPT_POWER), "status"], capture_output=True, text=True, check=True)
    assert "No system power action is waiting for confirmation" in proc.stdout


def test_cli_shutdown_interactive_cancellation():
    proc = subprocess.run([sys.executable, str(SCRIPT_POWER), "shutdown"], input="n\n", capture_output=True, text=True)
    assert proc.returncode == 1
    assert "cancelled" in proc.stdout.lower()


def test_cli_restart_interactive_cancellation():
    proc = subprocess.run([sys.executable, str(SCRIPT_POWER), "restart"], input="no\n", capture_output=True, text=True)
    assert proc.returncode == 1
    assert "cancelled" in proc.stdout.lower()


def test_cli_lock_interactive_cancellation():
    proc = subprocess.run([sys.executable, str(SCRIPT_POWER), "lock"], input="n\n", capture_output=True, text=True)
    assert proc.returncode == 1
    assert "cancelled" in proc.stdout.lower()
