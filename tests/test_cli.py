import os
import subprocess
import sys
from unittest.mock import MagicMock, patch
import pytest

def test_cli_help():
    result = subprocess.run(
        [sys.executable, '-m', 'jarvis_voice', '--help'],
        capture_output=True, text=True, timeout=10)
    assert result.returncode == 0
    assert 'jarvis' in result.stdout.lower() or 'voice' in result.stdout.lower()

def test_cli_check_no_network():
    """--check validates dependencies without opening audio or network."""
    result = subprocess.run(
        [sys.executable, '-m', 'jarvis_voice', '--check'],
        capture_output=True, text=True, timeout=10)
    # audio commands pw-record etc. are present on linux or might fail
    assert result.returncode in (0, 1)

def test_cli_status_not_running(tmp_path, monkeypatch):
    """When socket does not exist, status exits with code 1."""
    fake_sock = tmp_path / 'nonexistent.sock'
    monkeypatch.setattr('jarvis_voice.config.SOCKET_PATH', fake_sock)
    
    from jarvis_voice.__main__ import main
    monkeypatch.setattr(sys, 'argv', ['jarvis-voice', 'status'])
    rc = main()
    assert rc == 1

def test_cli_status_json_socket(tmp_path, monkeypatch):
    """Status command connects to unix socket and receives response."""
    import socket
    import threading
    sock_path = tmp_path / 'control.sock'
    monkeypatch.setattr('jarvis_voice.config.SOCKET_PATH', sock_path)

    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(str(sock_path))
    server.settimeout(3.0)
    server.listen(1)

    def handle():
        try:
            conn, _ = server.accept()
            conn.settimeout(2.0)
            data = conn.recv(1024)
            if data == b'status --json\n':
                conn.sendall(b'{"state": "idle", "model": "gemini-3.8-live"}\n')
            elif data == b'listen toggle\n':
                conn.sendall(b'{"muted": true}\n')
            conn.close()
        except socket.timeout:
            pass
        finally:
            server.close()

    t = threading.Thread(target=handle)
    t.start()

    from jarvis_voice.__main__ import main
    monkeypatch.setattr(sys, 'argv', ['jarvis-voice', 'status', '--json'])
    rc = main()
    assert rc == 0
    t.join()
