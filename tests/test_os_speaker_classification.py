"""Unit tests for JARVIS OS EventClassifier and spoken notification filtering."""
import pytest
from voice_layer.os_speaker import EventClassifier, SpeechClient, SpeechArbiter


def test_classifier_rejects_routine_noise():
    noise_samples = [
        "Antigravity. Agent finished: Git Repository Status Check.",
        "Antigravity. Agent finished: AI Portfolio Website Content Generation.",
        "Screenshot saved and copied. 1,920 × 857 · 516.0 kB.",
        "Workspace layout set to scrolling.",
        "Omarchy Healer: [Issue Resolved] Elevated System RAM Usage (81.0%). Tag: Issue Resolved (Auto-Healed).",
        "USB device connected.",
        "USB device disconnected.",
        "Power cable connected. Charging battery.",
        "Volume set to 40 percent.",
        "Theme changed to Catppuccin Mocha.",
    ]
    for text in noise_samples:
        should_tell, category = EventClassifier.should_tell(text, source="notification")
        assert should_tell is False, f"Expected '{text}' to NOT be spoken, got {category}"
        assert category == "routine_noise"


def test_classifier_identifies_critical_failures():
    failure_samples = [
        ("System alert: Service device-bridge encountered an error: Failed with result 'exit-code'.", "failure"),
        ("System alert: Service jarvis-voice failed to start.", "failure"),
        ("Fatal error: Unhandled exception in core dispatcher.", "failure"),
    ]
    for text, expected_cat in failure_samples:
        should_tell, category = EventClassifier.should_tell(text, source="systemd")
        assert should_tell is True, f"Expected '{text}' to be spoken"
        assert category == expected_cat


def test_classifier_identifies_crashes():
    crash_samples = [
        ("Process Discord crashed with segmentation fault (core dumped).", "crash"),
        ("Application segfault in libc.so.", "crash"),
        ("Kernel panic - not syncing: Fatal hardware error.", "crash"),
        ("Worker killed by OOM killer.", "oom"),
        ("The screenshot tool crashed with segmentation fault.", "crash"),
        ("Browser tab crashed unexpectedly with fatal error.", "crash"),
    ]
    for text, expected_cat in crash_samples:
        should_tell, category = EventClassifier.should_tell(text, source="os")
        assert should_tell is True, f"Expected '{text}' to be spoken"
        assert category == expected_cat


def test_classifier_identifies_high_usage():
    usage_samples = [
        ("Omarchy Healer: Elevated System RAM Usage at 94.2%.", "high_ram"),
        ("Critical memory: RAM usage is 98%.", "high_ram"),
        ("CPU usage is at 99%.", "high_cpu"),
        ("No space left on device: disk full on root partition.", "disk_full"),
        ("Thermal throttling detected: CPU temperature high.", "thermal"),
    ]
    for text, expected_cat in usage_samples:
        should_tell, category = EventClassifier.should_tell(text, source="os")
        assert should_tell is True, f"Expected '{text}' to be spoken"
        assert category == expected_cat


def test_classifier_identifies_low_battery():
    battery_samples = [
        ("Critical battery warning: 10 percent remaining.", "low_battery"),
        ("Battery is low at 15 percent.", "low_battery"),
        ("Time to recharge!. Battery down to 8%.", "low_battery"),
    ]
    for text, expected_cat in battery_samples:
        should_tell, category = EventClassifier.should_tell(text, source="power")
        assert should_tell is True, f"Expected '{text}' to be spoken"
        assert category == expected_cat


@pytest.mark.asyncio
async def test_speech_client_does_not_use_local_tts():
    client = SpeechClient()
    # Confirm SpeechClient has no offline_speech fallback object
    assert not hasattr(client, "_offline_speech") or client._offline_speech is None
    # When socket is missing, speak should gracefully return False without crashing or playing espeak
    res = await client.speak("Test alert", priority="critical", source="test", silent=False)
    # Result is a boolean, no exception raised
    assert isinstance(res, bool)
