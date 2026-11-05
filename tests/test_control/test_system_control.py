"""Common-control verification at mocked native command boundaries."""
import json
from unittest.mock import Mock

import pytest
from jarvis_control.system_control import ACTIONS, SCHEMA, execute
from jarvis_control.tools import Result


def shell_executor(*outputs):
    executor = Mock()
    executor._shell.side_effect = [x if isinstance(x, Result) else Result(True, x) for x in outputs]
    return executor


def test_schema_exposes_only_fixed_control_actions():
    assert SCHEMA['name'] == 'system_control'
    assert SCHEMA['input_schema']['properties']['action']['enum'] == list(ACTIONS)
    assert SCHEMA['input_schema']['additionalProperties'] is False


def test_volume_uses_resolved_physical_sink_and_verifies_every_channel():
    executor = shell_executor('alsa_output.physical', 'left: 40% right: 40%', '', 'left: 55% right: 55%')
    result = execute(executor, 'volume_set', value=55)
    assert result.ok and '55%' in result.output and 'verified' in result.output
    assert executor._shell.call_args_list[2].args[0] == ['pactl', 'set-sink-volume', 'alsa_output.physical', '55%']
    assert all(call.args[0][-1] == 'alsa_output.physical' for call in (executor._shell.call_args_list[1], executor._shell.call_args_list[3]))


def test_volume_verification_detects_one_unchanged_channel():
    executor = shell_executor('physical', 'left: 40% right: 40%', '', 'left: 55% right: 40%')
    result = execute(executor, 'volume_set', value=55)
    assert not result.ok
    assert 'actual channel percentages' in result.output


@pytest.mark.parametrize('value', [True, None, float('nan'), float('inf'), -1, 101, '50'])
def test_invalid_absolute_volume_never_reaches_native_commands(value):
    executor = shell_executor()
    assert not execute(executor, 'volume_set', value=value).ok
    executor._shell.assert_not_called()


@pytest.mark.parametrize('before,delta,after', [(95, 20, 100), (3, -20, 0)])
def test_volume_adjust_clamps_to_normal_output_range(before, delta, after):
    executor = shell_executor('physical', f'{before}%', '', f'{after}%')
    assert execute(executor, 'volume_adjust', value=delta).ok
    assert executor._shell.call_args_list[2].args[0][-1] == f'{after}%'


def test_sink_resolution_failure_prevents_volume_change():
    executor = shell_executor(Result(False, 'sink unavailable'))
    assert not execute(executor, 'volume_set', value=60).ok
    assert executor._shell.call_count == 1


@pytest.mark.parametrize('before,target,after,expected', [('no', True, 'yes', True), ('yes', False, 'no', True), ('no', True, 'no', False)])
def test_mute_set_uses_explicit_state_and_verifies(before, target, after, expected):
    executor = shell_executor('physical', f'Mute: {before}', '', f'Mute: {after}')
    result = execute(executor, 'mute_set', enabled=target)
    assert result.ok is expected
    assert executor._shell.call_args_list[2].args[0] == ['pactl', 'set-sink-mute', 'physical', '1' if target else '0']


def test_mute_get_does_not_toggle_or_write():
    executor = shell_executor('physical', 'Mute: yes')
    assert execute(executor, 'mute_get').output == 'Output is muted.'
    assert executor._shell.call_count == 2


def test_brightness_adjust_uses_absolute_target_and_keeps_display_lit():
    executor = shell_executor('4', '', '1')
    result = execute(executor, 'brightness_adjust', value=-30)
    assert result.ok and '1%' in result.output
    assert executor._shell.call_args_list[1].args[0] == ['omarchy', 'brightness', 'display', '--no-osd', '1%']


def test_brightness_reports_verification_failure():
    executor = shell_executor('40', '', '40')
    assert not execute(executor, 'brightness_set', value=70).ok


def test_brightness_zero_is_rejected_before_native_commands():
    executor = shell_executor()
    assert not execute(executor, 'brightness_set', value=0).ok
    executor._shell.assert_not_called()


def workspace_executor(initial='2'):
    state = {'name': initial}
    executor = Mock()
    executor._system_control_previous_workspace = ''
    executor._tool_hypr_query.side_effect = lambda kind: Result(True, json.dumps(state))
    def dispatch(lua):
        state['name'] = lua.split('"')[1]
        return Result(True, 'dispatched')
    executor._tool_hypr_dispatch.side_effect = dispatch
    return executor, state


def test_workspace_switch_and_back_verify_actual_state():
    executor, state = workspace_executor()
    assert execute(executor, 'workspace_switch', workspace='5').ok
    assert state['name'] == '5'
    assert executor._system_control_previous_workspace == '2'
    assert execute(executor, 'workspace_back').ok
    assert state['name'] == '2'
    assert executor._system_control_previous_workspace == '5'


def test_failed_workspace_switch_does_not_update_previous_state():
    executor, state = workspace_executor()
    executor._tool_hypr_dispatch.side_effect = lambda lua: Result(True, 'no state change')
    result = execute(executor, 'workspace_switch', workspace='5')
    assert not result.ok
    assert executor._system_control_previous_workspace == ''


@pytest.mark.parametrize('workspace', ['', '0', '-1', '2; execute()', 'e+1', 'special:test', '2147483648'])
def test_workspace_switch_accepts_numbered_destinations_only(workspace):
    executor, _ = workspace_executor()
    assert not execute(executor, 'workspace_switch', workspace=workspace).ok
    executor._tool_hypr_dispatch.assert_not_called()


def test_back_without_previous_workspace_is_an_explicit_failure():
    executor, _ = workspace_executor()
    assert not execute(executor, 'workspace_back').ok


def test_unknown_control_action_never_calls_native_commands():
    executor = Mock()
    assert not execute(executor, 'shutdown').ok
    executor._shell.assert_not_called()


@pytest.mark.parametrize('action,kwargs', [
    ('volume_set', {'value': 120}),
    ('brightness_set', {'value': 0}),
    ('mute_set', {'enabled': 'false'}),
    ('workspace_switch', {'workspace': '2; bad()'}),
    ('workspace_switch', {'workspace': '9' * 5000}),
])
def test_dry_run_validation_rejects_bad_arguments_without_executor(action, kwargs):
    from jarvis_control.system_control import validate
    assert validate(action, **kwargs)


def test_dry_run_validation_accepts_supported_shapes_without_hardware():
    from jarvis_control.system_control import validate
    assert validate('volume_adjust', value=-5) is None
    assert validate('mute_set', enabled=False) is None
    assert validate('workspace_switch', workspace='4') is None


def test_unavailable_native_hardware_returns_failure_not_exception():
    executor = Mock()
    executor._shell.side_effect = OSError('audio backend unavailable')
    result = execute(executor, 'volume_get')
    assert not result.ok
    assert 'unavailable' in result.output


@pytest.mark.parametrize('action,outputs,expected', [
    ('volume_get', ['physical', 'left: 62% right: 62%'], '62%'),
    ('brightness_get', ['42'], '42%'),
])
def test_getters_report_observed_values_without_writes(action, outputs, expected):
    executor = shell_executor(*outputs)
    result = execute(executor, action)
    assert result.ok and expected in result.output
    assert executor._shell.call_count == len(outputs)



def test_brightness_minimum_verification_does_not_accept_a_dark_display():
    executor = shell_executor('3', '', '0')
    result = execute(executor, 'brightness_set', value=1)
    assert not result.ok
    assert 'actual brightness is 0%' in result.output


def test_dry_run_still_reads_controls_but_never_sets_them(monkeypatch):
    from jarvis_control.config import Config
    from jarvis_control.tools import Executor
    executor = Executor(Config(dry_run=True))
    handler = Mock(return_value=Result(True, 'Output volume is 40%.'))
    monkeypatch.setattr(executor, '_tool_system_control', handler)
    result = executor.call('system_control', {'action': 'volume_get'})
    assert result.ok and result.output == 'Output volume is 40%.'
    handler.assert_called_once()
    handler.reset_mock()
    result = executor.call('system_control', {'action': 'volume_set', 'value': 40})
    assert result.ok and '[dry-run]' in result.output
    handler.assert_not_called()


def test_nightlight_get_reports_status_and_temperature():
    executor = shell_executor('{"enabled": true, "temperature": 4000}')
    res = execute(executor, 'nightlight_get')
    assert res.ok and 'Night light is on (4000K)' in res.output


def test_nightlight_set_and_toggle():
    # nightlight_set: before is true, target is false -> executes toggle, after is false
    executor = shell_executor(
        '{"enabled": true, "temperature": 4000}',
        '',
        '{"enabled": false, "temperature": 6500}'
    )
    res = execute(executor, 'nightlight_set', enabled=False)
    assert res.ok and 'Night light turned off (6500K) (verified)' in res.output
    assert executor._shell.call_args_list[1].args[0] == ['omarchy', 'toggle', 'nightlight']

    # nightlight_toggle: before is false -> toggles, after is true
    executor = shell_executor(
        '{"enabled": false, "temperature": 6500}',
        '',
        '{"enabled": true, "temperature": 4000}'
    )
    res = execute(executor, 'nightlight_toggle')
    assert res.ok and 'Night light toggled on (4000K) (verified)' in res.output


def test_idle_stay_awake_get_set_toggle():
    executor = shell_executor('{"enabled": true}')
    res = execute(executor, 'idle_get')
    assert res.ok and 'Stay-awake (sleep inhibitor) is enabled' in res.output

    executor = shell_executor('{"enabled": true}', '', '{"enabled": false}')
    res = execute(executor, 'idle_set', enabled=False)
    assert res.ok and 'Normal idle restored (verified)' in res.output
    assert executor._shell.call_args_list[1].args[0] == ['omarchy', 'toggle', 'idle', 'allow-idle']


def test_dnd_get_set_toggle():
    executor = Mock()
    executor._shell.side_effect = [Result(True, ''), Result(True, ''), Result(True, '')]
    res = execute(executor, 'dnd_get')
    assert res.ok and 'Do Not Disturb (notification silencing) is enabled' in res.output


def test_bluetooth_get_set_toggle():
    executor = Mock()
    executor._shell.side_effect = [Result(True, '')]
    res = execute(executor, 'bluetooth_get')
    assert res.ok and 'Bluetooth is powered on' in res.output

    executor._shell.side_effect = [Result(True, ''), Result(True, ''), Result(False, '')]
    res = execute(executor, 'bluetooth_set', enabled=False)
    assert res.ok and 'Bluetooth turned off (verified)' in res.output


def test_touchpad_and_bar_controls():
    executor = Mock()
    # Touchpad: file exists -> not ok -> touchpad is disabled
    executor._shell.side_effect = [Result(True, '')]
    res = execute(executor, 'touchpad_get')
    assert res.ok and 'Touchpad is disabled' in res.output

    # Bar: flag file does not exist -> Result(False) -> visible
    executor._shell.side_effect = [Result(False, '')]
    res = execute(executor, 'bar_get')
    assert res.ok and 'Status bar is visible' in res.output


def test_microphone_mute_get_set_toggle():
    executor = shell_executor('Volume: 0.50 [MUTED]')
    res = execute(executor, 'mic_mute_get')
    assert res.ok and 'Microphone is muted' in res.output

    executor = shell_executor('Volume: 0.50 [MUTED]', '', 'Volume: 0.50')
    res = execute(executor, 'mic_mute_set', enabled=False)
    assert res.ok and 'Microphone unmuted (verified)' in res.output
    assert executor._shell.call_args_list[1].args[0] == ['wpctl', 'set-mute', '@DEFAULT_AUDIO_SOURCE@', '0']



def test_media_controls_play_pause_and_status():
    executor = Mock()
    # media_status with no player
    executor._shell.return_value = Result(False, 'No players found')
    res = execute(executor, 'media_status')
    assert res.ok and 'No media player is currently active' in res.output

    # media_status with playing track
    executor._shell.side_effect = [Result(True, 'Playing'), Result(True, 'Queen - Bohemian Rhapsody')]
    res = execute(executor, 'media_status')
    assert res.ok and 'Playing: Queen - Bohemian Rhapsody' in res.output

    # media_play
    executor._shell.side_effect = [Result(True, ''), Result(True, 'Queen - Bohemian Rhapsody'), Result(True, 'Queen - Bohemian Rhapsody')]
    res = execute(executor, 'media_play')
    assert res.ok and 'Media playback started: Queen - Bohemian Rhapsody (verified)' in res.output

    # media_pause
    executor._shell.side_effect = None
    executor._shell.return_value = Result(True, '')
    res = execute(executor, 'media_pause')
    assert res.ok and 'Media playback paused (verified)' in res.output

    # media_next
    executor._shell.side_effect = [Result(True, 'Playing'), Result(True, ''), Result(True, "Queen - Don't Stop Me Now")]
    res = execute(executor, 'media_next')
    assert res.ok and "Skipped to next track: Queen - Don't Stop Me Now (verified)" in res.output


def test_window_controls_close_fullscreen_float_pin_center():
    executor = Mock()
    win_data = json.dumps({'address': '0x123', 'class': 'kitty', 'title': 'Terminal', 'fullscreen': 0, 'floating': False, 'pinned': False})
    fs_win = json.dumps({'address': '0x123', 'class': 'kitty', 'title': 'Terminal', 'fullscreen': 1, 'floating': False, 'pinned': False})
    fl_win = json.dumps({'address': '0x123', 'class': 'kitty', 'title': 'Terminal', 'fullscreen': 0, 'floating': True, 'pinned': False})
    pin_win = json.dumps({'address': '0x123', 'class': 'kitty', 'title': 'Terminal', 'fullscreen': 0, 'floating': True, 'pinned': True})

    # window_close
    executor._tool_hypr_query.return_value = Result(True, win_data)
    executor._shell.return_value = Result(True, '')
    res = execute(executor, 'window_close')
    assert res.ok and 'Closed Terminal (verified)' in res.output

    # window_fullscreen
    executor._tool_hypr_query.side_effect = [Result(True, win_data), Result(True, fs_win)]
    res = execute(executor, 'window_fullscreen')
    assert res.ok and 'Window fullscreen enabled (verified)' in res.output

    # window_toggle_float
    executor._tool_hypr_query.side_effect = [Result(True, win_data), Result(True, fl_win)]
    res = execute(executor, 'window_toggle_float')
    assert res.ok and 'Window set to floating (verified)' in res.output

    # window_pin
    executor._tool_hypr_query.side_effect = [Result(True, fl_win), Result(True, pin_win)]
    res = execute(executor, 'window_pin')
    assert res.ok and 'Window pinned across workspaces (verified)' in res.output

    # window_center
    executor._tool_hypr_query.side_effect = [Result(True, win_data)]
    res = execute(executor, 'window_center')
    assert res.ok and 'Window centered (verified)' in res.output


def test_window_focus_by_fuzzy_name():
    executor = Mock()
    clients = json.dumps([
        {'address': '0x1', 'class': 'google-chrome', 'title': 'GitHub - Chrome', 'workspace': {'name': '2'}},
        {'address': '0x2', 'class': 'foot', 'title': 'g0pi@omarchy:~', 'workspace': {'name': '1'}},
    ])
    executor._tool_hypr_query.return_value = Result(True, clients)
    executor._shell.return_value = Result(True, '')

    # Exact class match
    res = execute(executor, 'window_focus', target='google-chrome')
    assert res.ok and 'Focused google-chrome on workspace 2 (verified)' in res.output

    # Substring match on title / class
    res = execute(executor, 'window_focus', target='chrome')
    assert res.ok and 'Focused google-chrome on workspace 2 (verified)' in res.output

    # Not found
    res = execute(executor, 'window_focus', target='nonexistent')
    assert not res.ok and 'No open window matching' in res.output


def test_notification_dismiss():
    executor = Mock()
    executor._shell.return_value = Result(True, '')

    # Dismiss all
    res = execute(executor, 'notification_dismiss')
    assert res.ok and 'Dismissed notifications (verified)' in res.output
    assert executor._shell.call_args[0][0] == ['hyprctl', 'dismissnotify']

    # Dismiss targeted summary
    res = execute(executor, 'notification_dismiss', target='battery')
    assert res.ok and "Dismissed notification matching 'battery' (verified)" in res.output
    assert executor._shell.call_args[0][0] == ['omarchy', 'notification', 'dismiss', 'battery']
