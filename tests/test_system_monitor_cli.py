import json
import subprocess
import sys
from pathlib import Path
import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "system_monitor.py"


def test_cli_help():
    res = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--help"],
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0
    assert "--once" in res.stdout
    assert "--daemon" in res.stdout
    assert "--test-audio" in res.stdout
    assert "--config" in res.stdout


def test_cli_test_audio_argument():
    # Run --test-audio with mock/quiet or just verify it accepts argument and enumerates sounds
    res = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--test-audio", "--quiet-audio"],
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0
    assert "Testing alert sounds" in res.stdout
    assert "network_down" in res.stdout
    assert "recovery" in res.stdout


def test_cli_once_json_output(tmp_path):
    # Create minimal test config
    config_file = tmp_path / "test_config.json"
    config_file.write_text(
        json.dumps(
            {
                "network": {
                    "dns_targets": ["127.0.0.1"],
                    "wan_urls": [],
                    "check_gateway": False,
                },
                "servers": {"tcp": [], "http": []},
                "resources": {
                    "cpu_threshold_percent": 99.0,
                    "memory_threshold_percent": 99.0,
                    "disk_threshold_percent": 99.0,
                    "disks": ["/"],
                    "thermal_threshold_celsius": 120.0,
                },
                "services": {"user": [], "system": []},
            }
        )
    )

    res = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--once",
            "--json",
            "--quiet-audio",
            "--quiet-notify",
            "--config",
            str(config_file),
        ],
        capture_output=True,
        text=True,
    )
    assert res.returncode in (0, 1)
    payload = json.loads(res.stdout)
    assert "timestamp" in payload
    assert "summary" in payload
    assert "results" in payload
    assert isinstance(payload["results"], list)
