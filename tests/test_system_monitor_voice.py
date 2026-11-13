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
    action_batt_low = AlertAction(
        action_type="ALERT",
        alert_type="battery_low",
        category="resource",
        name="Battery",
        message="Battery low: 18% remaining and discharging",
    )
    speech_batt_low = format_alert_speech(action_batt_low)
    assert "battery alert" in speech_batt_low.lower()
    assert "18%" in speech_batt_low

    action_batt_crit = AlertAction(
        action_type="ALERT",
        alert_type="battery_critical",
        category="resource",
        name="Battery",
        message="Battery critically low: 8% remaining and not charging!",
    )
    speech_batt_crit = format_alert_speech(action_batt_crit)
    assert "critical power alert" in speech_batt_crit.lower()
    assert "immediately" in speech_batt_crit.lower()

    action_mem_high = AlertAction(
        action_type="ALERT",
        alert_type="memory_high",
        category="resource",
        name="Memory Usage",
        message="Memory high: 83.5% used",
    )
    speech_mem_high = format_alert_speech(action_mem_high)
    assert "high ram" in speech_mem_high.lower() or "memory" in speech_mem_high.lower()

    action_mem_crit = AlertAction(
        action_type="ALERT",
        alert_type="memory_critical",
        category="resource",
        name="Memory Usage",
        message="Memory critical: 94.0% used",
    )
    speech_mem_crit = format_alert_speech(action_mem_crit)
    assert "critically low" in speech_mem_crit.lower()

    action_rec = AlertAction(
        action_type="RECOVERY",
        alert_type="recovery",
        category="resource",
        name="Battery",
        message="Battery restored to normal state",
    )
    speech_rec = format_alert_speech(action_rec)
    assert "recovered" in speech_rec.lower() or "restored" in speech_rec.lower() or "healthy" in speech_rec.lower()


def test_voice_layer_speaker_mock_socket(tmp_path):
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
    ok = speaker.speak_alert("Battery is critically low: 9% remaining")
    t.join(timeout=2.0)
    server.close()

    assert ok is True
    assert len(received_commands) == 1
    assert received_commands[0].startswith("tell ")
    assert "Battery is critically low" in received_commands[0]


def test_voice_layer_speaker_fallback_when_socket_missing(tmp_path):
    missing_sock = tmp_path / "nonexistent.sock"
    speaker = JarvisVoiceSpeaker(socket_path=missing_sock)
    assert speaker.is_available() is False
    assert speaker.speak_alert("Test alert") is False


def test_dispatch_actions_voice_only_for_battery_and_silent_notifications():
    class MockSpeaker:
        def __init__(self):
            self.spoken = []

        def speak_alert(self, text: str):
            self.spoken.append(text)
            return True

    class MockNotifier:
        def __init__(self):
            self.notifications = []

        def notify(self, title, message, urgency="normal", **kwargs):
            self.notifications.append((title, message, urgency, kwargs))
            return True

    class MockAudioEngine:
        def __init__(self):
            self.played = []

        def play_alert(self, alert_type, async_play=True):
            self.played.append(alert_type)

    manager = AlertStateManager()
    speaker = MockSpeaker()
    notifier = MockNotifier()
    audio = MockAudioEngine()

    actions = [
        AlertAction(
            action_type="ALERT",
            alert_type="battery_low",
            category="resource",
            name="Battery",
            message="Battery low: 18% remaining",
            urgency="normal",
        ),
        AlertAction(
            action_type="ALERT",
            alert_type="memory_high",
            category="resource",
            name="Memory Usage",
            message="Memory high: 83.5% used",
            urgency="normal",
        ),
        AlertAction(
            action_type="ALERT",
            alert_type="cpu_overload",
            category="resource",
            name="CPU Load",
            message="CPU load at 92.0%",
            urgency="critical",
        ),
        AlertAction(
            action_type="ALERT",
            alert_type="battery_critical",
            category="resource",
            name="Battery",
            message="Battery critically low: 8% remaining",
            urgency="critical",
        ),
        AlertAction(
            action_type="RECOVERY",
            alert_type="recovery",
            category="resource",
            name="Memory Usage",
            message="Memory restored to normal state",
            urgency="normal",
        ),
    ]

    # Dispatch with default voice_battery_only=True and sound_alert=False
    manager.dispatch_actions(
        actions,
        audio_engine=audio,
        notifier=notifier,
        jarvis_speaker=speaker,
        voice_alert=True,
        sound_alert=False,
        desktop_notify=True,
        voice_battery_only=True,
    )

    # 1. Spoken alerts: STRICTLY the 2 battery alerts, never memory, CPU, or recovery
    assert len(speaker.spoken) == 2
    assert any("Battery alert" in s for s in speaker.spoken)
    assert any("Critical power alert" in s for s in speaker.spoken)
    for s in speaker.spoken:
        assert "Memory" not in s
        assert "CPU" not in s

    # 2. Desktop notifications: ALL 5 alerts notified
    assert len(notifier.notifications) == 5
    notif_titles = [n[0] for n in notifier.notifications]
    assert "[ALERT] Battery" in notif_titles
    assert "[ALERT] Memory Usage" in notif_titles
    assert "[ALERT] CPU Load" in notif_titles
    assert "[RESOLVED] Memory Usage" in notif_titles

    # Verify notification sound suppression hint is active
    for n in notifier.notifications:
        kwargs = n[3]
        assert kwargs.get("suppress_sound") is True

    # 3. Audio engine: ZERO procedural sounds played
    assert len(audio.played) == 0


def test_dispatch_actions_voice_all_allows_non_battery_when_configured():
    class MockSpeaker:
        def __init__(self):
            self.spoken = []

        def speak_alert(self, text: str):
            self.spoken.append(text)
            return True

    manager = AlertStateManager()
    speaker = MockSpeaker()

    actions = [
        AlertAction(
            action_type="ALERT",
            alert_type="memory_high",
            category="resource",
            name="Memory Usage",
            message="Memory high: 83.5% used",
            urgency="normal",
        ),
    ]

    manager.dispatch_actions(
        actions,
        jarvis_speaker=speaker,
        voice_alert=True,
        voice_battery_only=False,
    )

    assert len(speaker.spoken) == 1
    assert "Memory" in speaker.spoken[0]

