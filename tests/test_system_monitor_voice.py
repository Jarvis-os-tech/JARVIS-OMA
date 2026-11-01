import asyncio
import os
from pathlib import Path
import socket
import pytest

from core.system_monitor import (
    AlertAction,
    AlertStateManager,
    JarvisVoiceSpeaker,
    format_alert_speech,
)


def test_format_alert_speech_all_categories():
    action_net = AlertAction(
        action_type="ALERT",
        alert_type="network_down",
        category="network",
        name="DNS Resolution",
        message="DNS lookup failed for all targets",
    )
    speech_net = format_alert_speech(action_net)
    assert "network" in speech_net.lower()
    assert "dns" in speech_net.lower() or "connection" in speech_net.lower()

    action_srv = AlertAction(
        action_type="ALERT",
        alert_type="server_down",
        category="server",
        name="TCP 192.168.1.100:80",
        message="Connection refused",
    )
    speech_srv = format_alert_speech(action_srv)
    assert "server" in speech_srv.lower()

    action_rec = AlertAction(
        action_type="RECOVERY",
        alert_type="recovery",
        category="network",
        name="DNS Resolution",
        message="DNS Resolution restored to normal state",
    )
    speech_rec = format_alert_speech(action_rec)
    assert "restored" in speech_rec.lower() or "recovered" in speech_rec.lower() or "healthy" in speech_rec.lower()


def test_jarvis_voice_speaker_mock_socket(tmp_path):
    sock_path = tmp_path / "control.sock"
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(str(sock_path))
    server.listen(1)

    received_commands = []

    def handle_client():
        conn, _ = server.accept()
        data = conn.recv(1024).decode()
        received_commands.append(data)
        conn.sendall(b'{"status":"sent"}\n')
        conn.close()

    import threading
    t = threading.Thread(target=handle_client, daemon=True)
    t.start()

    speaker = JarvisVoiceSpeaker(socket_path=sock_path)
    ok = speaker.speak_alert("Network gateway is unreachable")
    t.join(timeout=2.0)
    server.close()

    assert ok is True
    assert len(received_commands) == 1
    assert received_commands[0].startswith("tell ")
    assert "Network gateway is unreachable" in received_commands[0]


def test_jarvis_voice_speaker_fallback_when_socket_missing(tmp_path):
    missing_sock = tmp_path / "nonexistent.sock"
    speaker = JarvisVoiceSpeaker(socket_path=missing_sock)
    assert speaker.is_available() is False
    assert speaker.speak_alert("Test alert") is False
