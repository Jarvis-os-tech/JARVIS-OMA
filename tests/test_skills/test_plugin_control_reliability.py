"""Regression tests for swallowed plugin errors and verified state changes."""
import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from skills import system_control as controls


@pytest.fixture
def runtime(monkeypatch):
    monkeypatch.setattr(controls, "get_control_panel_script", lambda name: "/plugin/" + name)
    monkeypatch.setattr(controls.shutil, "which", lambda name: "/bin/" + name)
    runner = AsyncMock()
    monkeypatch.setattr(controls, "_run_command", runner)
    return runner


@pytest.mark.asyncio
@pytest.mark.parametrize("result", [(1, "", "permission denied"), (0, '{"success":false,"error":"denied"}', "")])
async def test_plugin_exit_or_json_failure_never_reports_success(runtime, result):
    runtime.return_value = result
    value = await controls.control_microphone("mute")
    assert value["status"] == "error"
    assert value["verified"] is False
    assert runtime.await_count == 1


@pytest.mark.asyncio
async def test_swallowed_microphone_failure_detected_by_readback(runtime):
    runtime.side_effect = [(0, "", ""), (0, "Volume: 0.50", "")]
    value = await controls.control_microphone("mute")
    assert value["status"] == "error"
    assert value["observation"]["muted"] is False
    assert runtime.call_args_list[0].args == ("/plugin/system-control.sh", "audio-set-input-mute", "1")


@pytest.mark.asyncio
async def test_audio_readback_proves_success(runtime):
    runtime.side_effect = [(0, "", ""), (0, "Volume: 0.50 [MUTED]", "")]
    value = await controls.control_microphone("mute")
    assert value["status"] == "success"
    assert value["muted"] is True and value["verified"] is True


@pytest.mark.asyncio
async def test_relative_volume_does_not_guess_fifty_percent(runtime):
    runtime.return_value = (1, "", "No default device")
    value = await controls.set_volume(action="raise", amount=10)
    assert value["status"] == "error"
    assert runtime.await_count == 1
    assert runtime.call_args.args[1] == "get-volume"


@pytest.mark.asyncio
async def test_relative_brightness_requires_hardware_reading(runtime):
    runtime.return_value = (1, "", "device missing")
    value = await controls.set_brightness(direction="raise")
    assert value["status"] == "error"
    assert all(call.args[1] in ("get", "max") for call in runtime.call_args_list)


@pytest.mark.asyncio
async def test_brightness_plugin_noop_does_not_claim_requested_value(runtime):
    async def run(*args, **kwargs):
        return (0, {"get": "20", "max": "100"}.get(args[1], ""), "")
    runtime.side_effect = run
    value = await controls.set_brightness(percent=80)
    assert value["status"] == "error"
    assert value["observation"]["brightness_percent"] == 20


@pytest.mark.asyncio
@pytest.mark.parametrize("action,current", [("on", "4000"), ("off", "6500")])
async def test_nightlight_explicit_action_is_idempotent(runtime, action, current):
    runtime.return_value = (0, current, "")
    value = await controls.control_night_light(action)
    assert value["status"] == "success"
    assert value["changed"] is False
    assert runtime.await_count == 1


@pytest.mark.asyncio
async def test_nightlight_unknown_prevents_blind_toggle(runtime):
    runtime.return_value = (0, "", "")
    value = await controls.control_night_light("toggle")
    assert value["status"] == "error"
    assert runtime.await_count == 1


@pytest.mark.asyncio
async def test_explicit_nightlight_on_can_initialize_missing_daemon(runtime):
    runtime.side_effect = [(1, "", "hyprsunset unavailable"), (0, "", ""), (0, "4000", "")]
    value = await controls.control_night_light("on")
    assert value["status"] == "success" and value["nightlight"]["enabled"] is True
    assert runtime.call_args_list[1].args == ("/plugin/display-control.sh", "set-nightlight-temp", "4000")


@pytest.mark.asyncio
async def test_nightlight_on_sets_and_reads_exact_temperature(runtime):
    runtime.side_effect = [(0, "6500", ""), (0, "", ""), (0, "4000", "")]
    value = await controls.control_night_light("on")
    assert value["status"] == "success"
    assert value["nightlight"] == {"enabled": True, "temperature": 4000}
    assert runtime.call_args_list[1].args == ("/plugin/display-control.sh", "set-nightlight-temp", "4000")


@pytest.mark.asyncio
async def test_invalid_nightlight_action_never_toggles(runtime):
    assert (await controls.control_night_light("banana"))["status"] == "error"
    runtime.assert_not_awaited()


@pytest.mark.asyncio
async def test_dnd_explicit_on_already_on_does_not_toggle(runtime):
    runtime.return_value = (0, "on", "")
    value = await controls.control_notifications("dnd_on")
    assert value["status"] == "success" and value["changed"] is False
    assert runtime.await_count == 1


@pytest.mark.asyncio
async def test_dnd_plugin_noop_detected(runtime):
    runtime.side_effect = [(0, "off", ""), (0, "", ""), (0, "off", "")]
    value = await controls.control_notifications("dnd_on")
    assert value["status"] == "error"
    assert runtime.call_args_list[1].args == ("/plugin/notifications-control.sh", "set-dnd", "true")


@pytest.mark.asyncio
async def test_dnd_fallback_uses_set_not_toggle(runtime, monkeypatch):
    monkeypatch.setattr(controls, "get_control_panel_script", lambda _: None)
    runtime.side_effect = [(0, "on", ""), (0, "", ""), (0, "off", "")]
    value = await controls.control_notifications("dnd_off")
    assert value["status"] == "success"
    assert runtime.call_args_list[1].args == ("/bin/omarchy-shell", "notifications", "setDnd", "false")


@pytest.mark.asyncio
async def test_theme_dark_is_not_an_invented_theme(runtime):
    runtime.return_value = (0, "Tokyo Night\nNord", "")
    value = await controls.control_theme("dark")
    assert value["status"] == "error"
    assert runtime.await_count == 1
    assert runtime.call_args.args == ("/bin/omarchy-theme-list",)


@pytest.mark.asyncio
async def test_theme_set_validates_installation_and_readback(runtime):
    runtime.side_effect = [(0, "Tokyo Night\nNord", ""), (0, "", ""), (0, "Nord", "")]
    value = await controls.control_theme("set", "nord")
    assert value["status"] == "success" and value["current"] == "Nord"
    assert runtime.call_args_list[1].args == ("/plugin/system-control.sh", "theme-set", "Nord")


@pytest.mark.asyncio
async def test_theme_failed_switch_readback_is_not_success(runtime):
    runtime.side_effect = [(0, "Tokyo Night\nNord", ""), (0, "", ""), (0, "Tokyo Night", "")]
    assert (await controls.control_theme("set", "Nord"))["status"] == "error"


@pytest.mark.asyncio
async def test_wifi_failed_radio_query_does_not_report_off(runtime):
    runtime.return_value = (1, "", "NetworkManager unavailable")
    value = await controls.control_wifi("status")
    assert value["status"] == "error"
    assert "wifi" not in value


@pytest.mark.asyncio
async def test_wifi_radio_noop_is_detected(runtime):
    runtime.side_effect = [(0, "", ""), (0, "disabled", "")]
    assert (await controls.control_wifi("on"))["status"] == "error"


@pytest.mark.asyncio
async def test_bluetooth_disconnect_is_explicit_not_plugin_toggle(runtime):
    runtime.side_effect = [(0, "", ""), (0, "Device AA:BB:CC:DD:EE:FF\n\tConnected: no", "")]
    value = await controls.control_bluetooth("disconnect", "AA:BB:CC:DD:EE:FF")
    assert value["status"] == "success"
    assert runtime.call_args_list[0].args == ("/bin/bluetoothctl", "disconnect", "AA:BB:CC:DD:EE:FF")


@pytest.mark.asyncio
async def test_bluetooth_zero_exit_text_failure_is_error(runtime):
    runtime.return_value = (0, "Failed to connect: org.bluez.Error.Failed", "")
    value = await controls.control_bluetooth("connect", "AA:BB:CC:DD:EE:FF")
    assert value["status"] == "error"


@pytest.mark.asyncio
async def test_power_plugin_noop_does_not_claim_profile(runtime):
    runtime.side_effect = [(0, "", ""), (0, "balanced", "")]
    value = await controls.control_power("performance")
    assert value["status"] == "error"
    assert value["observation"]["profile"] == "balanced"


@pytest.mark.asyncio
async def test_status_snapshot_labels_missing_data_unknown(runtime, monkeypatch):
    monkeypatch.setattr(controls, "find_control_panel_plugin", lambda: None)
    runtime.return_value = (1, "", "unavailable")
    value = await controls.get_control_status()
    assert value["status"] == "partial"
    assert value["plugin"]["installed"] is False
    assert len(value["observations"]) == 9
    assert all(observation["status"] == "error" and observation["observed_at"] for observation in value["observations"].values())
    assert not any("set" in call.args[1:] for call in runtime.call_args_list)


@pytest.mark.asyncio
async def test_successful_write_missing_readback_is_unverified(runtime):
    runtime.side_effect = [(0, "", ""), (1, "", "device unavailable")]
    value = await controls.control_microphone("mute")
    assert value["status"] == "unverified" and value["verified"] is False


@pytest.mark.asyncio
async def test_wifi_error_redacts_secret(runtime):
    runtime.return_value = (1, "", "failed with secret-password")
    value = await controls.control_wifi("connect", "Office", "secret-password")
    assert "secret-password" not in json.dumps(value)


@pytest.mark.asyncio
@pytest.mark.parametrize("category,expected", [("display", {"brightness", "nightlight"}), ("audio", {"audio", "microphone"})])
async def test_control_status_grouping_is_read_only(runtime, monkeypatch, category, expected):
    monkeypatch.setattr(controls, "find_control_panel_plugin", lambda: None)
    runtime.return_value = (1, "", "unavailable")
    value = await controls.get_control_status(category)
    assert set(value["observations"]) == expected
    assert all("observed_at" in item for item in value["observations"].values())


@pytest.mark.asyncio
async def test_notification_history_reads_files_without_replay(runtime, monkeypatch, tmp_path):
    monkeypatch.setattr(controls.Path, "home", lambda: tmp_path)
    directory = tmp_path / ".local/state/omarchy/notifications/history"
    directory.mkdir(parents=True)
    (directory / "one.json").write_text(json.dumps({"app": "Example", "summary": "A notification", "private_extra": "omit"}))
    (directory / "link.json").symlink_to(directory / "one.json")
    value = await controls.control_notifications("history")
    assert value["status"] == "success"
    assert value["history"] == [{"app": "Example", "summary": "A notification"}]
    runtime.assert_not_awaited()


@pytest.mark.asyncio
async def test_invalid_notification_history_reports_partial(runtime, monkeypatch, tmp_path):
    monkeypatch.setattr(controls.Path, "home", lambda: tmp_path)
    directory = tmp_path / ".local/state/omarchy/notifications/history"
    directory.mkdir(parents=True)
    (directory / "bad.json").write_text("not json")
    value = await controls.control_notifications("history")
    assert value["status"] == "partial" and value["verified"] is False
    assert len(value["errors"]) == 1


@pytest.mark.asyncio
async def test_cancelled_desktop_command_kills_and_reaps_child(monkeypatch):
    entered = asyncio.Event()
    count = 0

    async def communicate():
        nonlocal count
        count += 1
        if count == 1:
            entered.set()
            await asyncio.Event().wait()
        return b"", b""

    process = SimpleNamespace(communicate=communicate, kill=Mock(), returncode=-9)
    monkeypatch.setattr(controls.asyncio, "create_subprocess_exec", AsyncMock(return_value=process))
    task = asyncio.create_task(controls._run_command("/fake/read-state"))
    await entered.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    process.kill.assert_called_once()
    assert count == 2
