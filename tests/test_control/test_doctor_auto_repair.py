"""Unit and integration tests for JARVIS OS doctor and auto-repair capabilities."""
from __future__ import annotations

import json
import os
from pathlib import Path
import socket
import sqlite3
import stat
import subprocess
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from jarvis_control import __main__ as cli
from jarvis_control import diagnostics


def test_dead_socket_detection_and_repair(tmp_path, monkeypatch):
    """Dead UNIX domain sockets and broken symlinks must be detected and removed."""
    sock_dir = tmp_path / "run_user" / "jarvis"
    sock_dir.mkdir(parents=True)
    dead_sock = sock_dir / "control.sock"

    # Create a listening socket, close it without unlinking, leaving dead socket file
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.bind(str(dead_sock))
    s.close()
    assert dead_sock.exists()

    # Broken symlink
    broken_link = sock_dir / "broken.sock"
    broken_link.symlink_to(tmp_path / "nonexistent.sock")
    assert broken_link.is_symlink()

    with patch("os.getuid", return_value=1000):
        with patch.object(diagnostics, "Path", side_effect=lambda p: Path(str(p).replace("/run/user/1000", str(tmp_path / "run_user")))):
            # Check-only mode
            issues, repairs = diagnostics.check_and_fix_dead_sockets(fix=False)
            paths = [iss["path"] for iss in issues]
            assert str(dead_sock) in paths
            assert str(broken_link) in paths
            assert len(repairs) == 0
            assert dead_sock.exists()

            # Fix mode
            issues, repairs = diagnostics.check_and_fix_dead_sockets(fix=True)
            assert not dead_sock.exists()
            assert not broken_link.exists()
            assert any("Removed dead UNIX socket" in r for r in repairs)
            assert any("Removed broken socket symlink" in r for r in repairs)


def test_stale_lock_detection_and_repair(tmp_path):
    """Stale locks containing dead PIDs or abandoned files must be cleaned up."""
    learn_dir = tmp_path / ".jarvis-learning"
    learn_dir.mkdir(parents=True)
    lock_file = learn_dir / "task.lock"
    # Write PID that definitely does not exist
    lock_file.write_text("99999999\n", encoding="utf-8")

    issues, repairs = diagnostics.check_and_fix_stale_locks(tmp_path, fix=False)
    assert any(str(lock_file) in iss["path"] for iss in issues)
    assert lock_file.exists()

    issues, repairs = diagnostics.check_and_fix_stale_locks(tmp_path, fix=True)
    assert not lock_file.exists()
    assert any("Removed stale lock file" in r for r in repairs)


def test_audio_unmute_repair():
    """Muted microphone or speaker must be unmuted automatically."""
    def fake_subprocess_run(cmd, *args, **kwargs):
        cmd_str = " ".join(cmd)
        mock_res = MagicMock()
        mock_res.returncode = 0
        if "get-source-mute" in cmd_str:
            mock_res.stdout = "Mute: yes\n"
        elif "get-sink-mute" in cmd_str:
            mock_res.stdout = "Mute: yes\n"
        elif "get-default-source" in cmd_str:
            mock_res.stdout = "alsa_output.pci.monitor\n"
        elif "list short sources" in cmd_str:
            mock_res.stdout = "1 alsa_output.pci.monitor PipeWire\n2 alsa_input.pci.mic PipeWire\n"
        else:
            mock_res.stdout = ""
        return mock_res

    with patch("shutil.which", return_value="/usr/bin/pactl"):
        with patch("subprocess.run", side_effect=fake_subprocess_run) as mock_run:
            issues, repairs = diagnostics.check_and_fix_audio(fix=True)
            assert any("mic_muted" == iss["type"] for iss in issues)
            assert any("speaker_muted" == iss["type"] for iss in issues)
            assert any("source_is_monitor" == iss["type"] for iss in issues)
            assert any("Unmuted default microphone input" in r for r in repairs)
            assert any("Unmuted default speaker output" in r for r in repairs)
            assert any("Switched default audio source" in r for r in repairs)


def test_secrets_and_env_permissions_repair(tmp_path):
    """Insecure .env permissions must be hardened to 0600 and synced to ~/.config/jarvis-voice."""
    project_env = tmp_path / ".env"
    project_env.write_text("GEMINI_API_KEY=test-gemini-key\n", encoding="utf-8")
    project_env.chmod(0o644)

    fake_home = tmp_path / "home"
    fake_home.mkdir()

    with patch("jarvis_control.diagnostics.Path.home", return_value=fake_home):
        issues, repairs = diagnostics.check_and_fix_secrets_and_env(tmp_path, fix=True)
        # Check hardened permission
        assert project_env.stat().st_mode & 0o777 == 0o600
        # Check synced file
        synced_env = fake_home / ".config/jarvis-voice/.env"
        assert synced_env.exists()
        assert synced_env.stat().st_mode & 0o777 == 0o600
        assert any("Secured .env permissions to 0600" in r for r in repairs)
        assert any("Synchronized .env" in r for r in repairs)


def test_database_integrity_and_wal_maintenance(tmp_path):
    """SQLite database files must have 0600 permissions, intact integrity, and flushed WAL."""
    db_dir = tmp_path / "memory/data"
    db_dir.mkdir(parents=True)
    db_file = db_dir / "memory_graph.db"
    conn = sqlite3.connect(str(db_file))
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("CREATE TABLE test_data (id INTEGER PRIMARY KEY, note TEXT);")
    conn.execute("INSERT INTO test_data (note) VALUES ('hello jarvis');")
    conn.commit()
    conn.close()

    db_file.chmod(0o644)
    assert db_file.stat().st_mode & 0o777 == 0o644

    issues, repairs = diagnostics.check_and_fix_databases(tmp_path, fix=True)
    assert db_file.stat().st_mode & 0o777 == 0o600
    assert any("Secured database permissions (0600)" in r for r in repairs)
    assert any("Flushed WAL journal & vacuumed database" in r for r in repairs)


def test_systemd_services_sync_and_enable(tmp_path):
    """Systemd unit files in repo must sync to user config and core services enabled."""
    src_systemd = tmp_path / "systemd"
    src_systemd.mkdir()
    (src_systemd / "jarvis-voice.service").write_text("[Unit]\nDescription=JARVIS Voice\n", encoding="utf-8")
    (src_systemd / "jarvis-memory-sync.timer").write_text("[Unit]\nDescription=Timer\n", encoding="utf-8")

    fake_home = tmp_path / "home"
    user_systemd = fake_home / ".config/systemd/user"
    user_systemd.mkdir(parents=True)

    calls = []

    def fake_subprocess_run(cmd, *args, **kwargs):
        calls.append(" ".join(cmd))
        mock_res = MagicMock()
        mock_res.returncode = 0
        if "is-enabled" in cmd:
            mock_res.stdout = "disabled\n"
        else:
            mock_res.stdout = ""
        return mock_res

    with patch("shutil.which", return_value="/usr/bin/systemctl"):
        with patch("subprocess.run", side_effect=fake_subprocess_run):
            with patch("jarvis_control.diagnostics.Path.home", return_value=fake_home):
                issues, repairs = diagnostics.check_and_fix_systemd_services(tmp_path, fix=True)
                assert (user_systemd / "jarvis-voice.service").exists()
                assert (user_systemd / "jarvis-memory-sync.timer").exists()
                assert any("Synchronized and reloaded" in r for r in repairs)
                assert any("Enabled systemd service for boot auto-start" in r for r in repairs)
                assert any("daemon-reload" in c for c in calls)
                assert any("enable jarvis-voice.service" in c for c in calls)


def test_doctor_cli_flags(tmp_path, monkeypatch, capsys):
    """Doctor CLI must respect --fix, --check-only, and --json flags."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    voice_dir = tmp_path / "jarvis-voice"
    voice_dir.mkdir()
    (voice_dir / "config.toml").write_text('api_key_env = "DUMMY_KEY"\ntasks_enabled = false\nvision_enabled = false\n')
    monkeypatch.setenv("DUMMY_KEY", "secret-test-key")

    monkeypatch.setattr(diagnostics.shutil, "which", lambda c: "/bin/" + c)
    monkeypatch.setattr(diagnostics.importlib.util, "find_spec", lambda n: object())

    # 1. Test --check-only / --no-fix
    ret = cli.main(["doctor", "--check-only"])
    assert ret == 0
    out = capsys.readouterr().out
    assert "JARVIS OS DOCTOR & AUTO-REPAIR" in out
    assert "[AUTO-REPAIRS APPLIED" not in out

    # 2. Test --json output
    ret = cli.main(["doctor", "--json"])
    assert ret == 0
    out = capsys.readouterr().out
    data = json.loads(out)
    assert data["ok"] is True
    assert data["checks"]["voice credential"]["detail"] == "DUMMY_KEY"
    assert "secret-test-key" not in out
    assert "temporary_issues" in data
    assert "long_term_issues" in data
    assert "repairs_applied" in data
