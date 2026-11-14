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
        "[ALERT] Thermal (TCPU). Temperature critical: 95.0°C (limit 85.0°C).",
        "[ALERT] HTTP https://cloudflare.com. HTTP request failed: handshake timed out.",
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
        ("Battery Warning. Battery level low: 9% remaining", "low_battery"),
        ("Battery level 12%", "low_battery"),
        ("Low battery: 5% left", "low_battery"),
        ("Battery at 20%", "low_battery"),
    ]
    for text, expected_cat in battery_samples:
        should_tell, category = EventClassifier.should_tell(text, source="power")
        assert should_tell is True, f"Expected '{text}' to be spoken"
        assert category == expected_cat

    # Safe battery level should not be spoken
    should_tell, category = EventClassifier.should_tell("Battery 85% charged", source="power")
    assert should_tell is False
    assert category == "non_critical"


@pytest.mark.asyncio
async def test_speech_client_does_not_use_local_tts():
    client = SpeechClient()
    # Confirm SpeechClient has no offline_speech fallback object
    assert not hasattr(client, "_offline_speech") or client._offline_speech is None
    # When socket is missing, speak should gracefully return False without crashing or playing espeak
    res = await client.speak("Test alert", priority="critical", source="test", silent=False)
    # Result is a boolean, no exception raised
    assert isinstance(res, bool)


@pytest.mark.asyncio
async def test_arbiter_deduplicates_sensor_bursts_by_category():
    from unittest.mock import AsyncMock
    client = SpeechClient()
    client.speak = AsyncMock(return_value=True)
    arbiter = SpeechArbiter(client)

    burst = [
        "Critical memory: RAM usage is 96%.",
        "Critical memory: RAM usage is 97%.",
        "Critical memory: RAM usage is 98%.",
    ]

    for item in burst:
        await arbiter.handle_event(item, source="notification", dedup_key=f"notif_{item[:20]}", urgency=2)

    # High RAM alerts: only the FIRST should be dispatched to speak, the others rate-limited
    assert client.speak.call_count == 1
    call_args = client.speak.call_args[1]
    assert call_args["priority"] == "critical"
    assert call_args["dedup_key"] == "critical_high_ram"


@pytest.mark.asyncio
async def test_arbiter_silences_thermal_and_cloudflare_alerts():
    from unittest.mock import AsyncMock
    client = SpeechClient()
    client.speak = AsyncMock(return_value=True)
    arbiter = SpeechArbiter(client)

    suppressed = [
        "[ALERT] Thermal (TCPU). Temperature critical: 95.0°C (limit 85.0°C).",
        "[ALERT] HTTP https://cloudflare.com. HTTP request failed: <urlopen error handshake timed out>.",
    ]

    for item in suppressed:
        await arbiter.handle_event(item, source="notification", dedup_key=f"notif_{item[:20]}", urgency=2)

    # Both must be registered silently (silent=True, priority=normal)
    assert client.speak.call_count == 2
    for call in client.speak.call_args_list:
        assert call[1]["silent"] is True
        assert call[1]["priority"] != "critical"
