"""Verified fast paths for common desktop controls.

The caller applies Executor policy and serialization. These handlers use its
native boundaries directly; calling Executor.call here would acquire its lock
twice. No shell syntax or model-provided program names are executed.
"""
from __future__ import annotations

import json
import math
import os
import re

ACTIONS = (
    'volume_get', 'volume_set', 'volume_adjust',
    'mute_get', 'mute_set',
    'mic_mute_get', 'mic_mute_set', 'mic_mute_toggle',
    'brightness_get', 'brightness_set', 'brightness_adjust',
    'nightlight_get', 'nightlight_set', 'nightlight_toggle',
    'idle_get', 'idle_set', 'idle_toggle',
    'dnd_get', 'dnd_set', 'dnd_toggle',
    'bluetooth_get', 'bluetooth_set', 'bluetooth_toggle',
    'touchpad_get', 'touchpad_set', 'touchpad_toggle',
    'bar_get', 'bar_set', 'bar_toggle',
    'workspace_get', 'workspace_switch', 'workspace_back',
)

SET_REQUIRING_ENABLED = (
    'mute_set', 'mic_mute_set', 'nightlight_set', 'idle_set',
    'dnd_set', 'bluetooth_set', 'touchpad_set', 'bar_set',
)

SCHEMA = {
    'name': 'system_control',
    'description': (
        'Read or change common system controls in one verified call. Use this '
        'for output volume, mute, microphone mute, brightness, night light, '
        'stay-awake (idle inhibitor), do not disturb (DND), bluetooth power, '
        'touchpad, status bar, and numbered workspaces before general Omarchy discovery. '
        'Set volume/brightness with value in percent; adjust with a signed percentage-point value. '
        'Binary states use enabled=true/false (or toggle actions without enabled). '
        'Workspace switch uses workspace="2"; workspace_back returns to the previous '
        'successfully switched workspace. Every change reads state before and verifies it afterward.'
    ),
    'input_schema': {
        'type': 'object',
        'properties': {
            'action': {'type': 'string', 'enum': list(ACTIONS)},
            'value': {'type': 'number', 'minimum': -100, 'maximum': 100},
            'enabled': {'type': 'boolean'},
            'workspace': {'type': 'string', 'description': 'Positive numbered workspace, for workspace_switch.'},
        },
        'required': ['action'],
        'additionalProperties': False,
    },
}


class SystemControlError(ValueError):
    pass


def _command(executor, argv):
    result = executor._shell(argv, timeout=5, limit=2000)
    if not result.ok:
        raise SystemControlError(result.output or f'{argv[0]} failed')
    return result.output.strip()


def _number(value, minimum, maximum):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise SystemControlError('value must be a finite number')
    if not minimum <= value <= maximum:
        raise SystemControlError(f'value must be between {minimum} and {maximum}')
    return float(value)


def _percentages(text):
    found = [float(value) for value in re.findall(r'(?<![\w.])(\d+(?:\.\d+)?)\s*%', text)]
    if not found or not all(math.isfinite(value) for value in found):
        raise SystemControlError('The audio server returned no readable volume percentage')
    return found


def _brightness(executor):
    text = _command(executor, ['omarchy', 'brightness', 'display', '--no-osd'])
    match = re.fullmatch(r'(\d+(?:\.\d+)?)\s*%?', text)
    if not match or not 0 <= float(match[1]) <= 100:
        raise SystemControlError('The display returned no readable brightness percentage')
    return float(match[1])


def _workspace(executor):
    result = executor._tool_hypr_query('activeworkspace')
    if not result.ok:
        raise SystemControlError(result.output or 'Could not read the active workspace')
    try:
        data = json.loads(result.output)
        name = data['name']
        if not isinstance(name, str) or not name:
            raise ValueError
        return name
    except (ValueError, KeyError, TypeError) as error:
        raise SystemControlError('The compositor returned no readable active workspace') from error


def _numbered_workspace(workspace):
    if not isinstance(workspace, str) or len(workspace) > 10 or not re.fullmatch(r'[1-9][0-9]*', workspace) or int(workspace) > 2_147_483_647:
        raise SystemControlError('workspace must be a positive workspace number')
    return str(int(workspace))


def _nightlight(executor) -> tuple[bool, int | None]:
    text = _command(executor, ['omarchy', 'toggle', 'nightlight', '--status'])
    try:
        data = json.loads(text)
        return bool(data.get('enabled')), data.get('temperature')
    except (ValueError, TypeError, KeyError) as error:
        raise SystemControlError('Could not read nightlight status') from error


def _idle(executor) -> bool:
    text = _command(executor, ['omarchy', 'toggle', 'idle', 'status'])
    try:
        data = json.loads(text)
        return bool(data.get('enabled'))
    except (ValueError, TypeError, KeyError) as error:
        raise SystemControlError('Could not read stay-awake/idle status') from error


def _dnd(executor) -> bool:
    return executor._shell(['omarchy', 'toggle', 'enabled', 'notification-silencing'], timeout=5).ok


def _bluetooth(executor) -> bool:
    return executor._shell(['omarchy', 'bluetooth', 'power', 'is-on'], timeout=5).ok


def _touchpad(executor) -> bool:
    name_file = os.path.expanduser('~/.local/state/omarchy/toggles/hypr/touchpad-disabled-name')
    return not executor._shell(['test', '-f', name_file], timeout=5).ok


def _bar(executor) -> bool:
    flag_file = os.path.expanduser('~/.local/state/omarchy/toggles/bar')
    return not executor._shell(['test', '-f', flag_file], timeout=5).ok


def _mic_muted(executor) -> bool:
    text = _command(executor, ['wpctl', 'get-volume', '@DEFAULT_AUDIO_SOURCE@'])
    return '[MUTED]' in text.upper()


def _arguments(action, value, enabled, workspace):
    if action not in ACTIONS:
        raise SystemControlError('Unknown system control action; choose one of: ' + ', '.join(ACTIONS))
    if action in ('volume_set', 'brightness_set'):
        value = _number(value, 1 if action.startswith('brightness') else 0, 100)
    elif action in ('volume_adjust', 'brightness_adjust'):
        value = _number(value, -100, 100)
    elif action in SET_REQUIRING_ENABLED and type(enabled) is not bool:
        raise SystemControlError(f'enabled must be true or false for {action}')
    elif action == 'workspace_switch':
        workspace = _numbered_workspace(workspace)
    return value, workspace


def validate(action: str, value=None, enabled=None, workspace: str = ''):
    """Return an argument error without inspecting or changing the desktop.

    Executor's dry-run validator can call this before reporting a planned action.
    Hardware availability and observed-state verification belong to execute().
    """
    try:
        _arguments(action, value, enabled, workspace)
    except SystemControlError as error:
        return str(error)
    return None


def execute(executor, action: str, value=None, enabled=None, workspace: str = ''):
    """Perform one fixed native control operation and return a verified Result."""
    from .tools import Result

    try:
        value, workspace = _arguments(action, value, enabled, workspace)

        if action.startswith('volume_') or action.startswith('mute_'):
            sink = _command(executor, ['omarchy', 'audio', 'output', 'sink'])
            if not sink or len(sink.splitlines()) != 1 or '\x00' in sink:
                raise SystemControlError('Could not resolve the current physical output sink')
            if action.startswith('mute_'):
                def muted():
                    text = _command(executor, ['pactl', 'get-sink-mute', sink])
                    match = re.fullmatch(r'Mute:\s*(yes|no)', text, re.I)
                    if not match:
                        raise SystemControlError('The audio server returned no readable mute state')
                    return match[1].lower() == 'yes'
                before = muted()
                if action == 'mute_get':
                    return Result(True, 'Output is muted.' if before else 'Output is unmuted.')
                if before != enabled:
                    _command(executor, ['pactl', 'set-sink-mute', sink, '1' if enabled else '0'])
                after = muted()
                if after != enabled:
                    raise SystemControlError('Mute command completed but the requested state could not be verified')
                return Result(True, 'Output muted (verified).' if after else 'Output unmuted (verified).')

            before = _percentages(_command(executor, ['pactl', 'get-sink-volume', sink]))
            if action == 'volume_get':
                return Result(True, f'Output volume is {max(before):g}%.')
            target = value if action == 'volume_set' else min(100.0, max(0.0, max(before) + value))
            _command(executor, ['pactl', 'set-sink-volume', sink, f'{target:g}%'])
            after = _percentages(_command(executor, ['pactl', 'get-sink-volume', sink]))
            if any(abs(actual - target) > 1 for actual in after):
                raise SystemControlError(f'Volume did not reach {target:g}%; actual channel percentages: ' + ', '.join(f'{x:g}' for x in after))
            return Result(True, f'Output volume set to {max(after):g}% (verified).')

        if action.startswith('brightness_'):
            before = _brightness(executor)
            if action == 'brightness_get':
                return Result(True, f'Display brightness is {before:g}%.')
            target = value if action == 'brightness_set' else min(100.0, max(1.0, before + value))
            _command(executor, ['omarchy', 'brightness', 'display', '--no-osd', f'{target:g}%'])
            after = _brightness(executor)
            if after < 1 or abs(after - target) > 1:
                raise SystemControlError(f'Brightness did not reach {target:g}%; actual brightness is {after:g}%')
            return Result(True, f'Display brightness set to {after:g}% (verified).')

        if action.startswith('mic_mute_'):
            before = _mic_muted(executor)
            if action == 'mic_mute_get':
                return Result(True, 'Microphone is muted.' if before else 'Microphone is unmuted.')
            if action == 'mic_mute_set':
                if before != enabled:
                    _command(executor, ['wpctl', 'set-mute', '@DEFAULT_AUDIO_SOURCE@', '1' if enabled else '0'])
                after = _mic_muted(executor)
                if after != enabled:
                    raise SystemControlError('Microphone mute state could not be verified')
                return Result(True, 'Microphone muted (verified).' if after else 'Microphone unmuted (verified).')
            _command(executor, ['wpctl', 'set-mute', '@DEFAULT_AUDIO_SOURCE@', 'toggle'])
            after = _mic_muted(executor)
            if after == before:
                raise SystemControlError('Microphone mute toggle could not be verified')
            return Result(True, 'Microphone muted (verified).' if after else 'Microphone unmuted (verified).')

        if action.startswith('nightlight_'):
            before, temp = _nightlight(executor)
            if action == 'nightlight_get':
                temp_s = f' ({temp}K)' if temp else ''
                return Result(True, f'Night light is on{temp_s}.' if before else f'Night light is off{temp_s}.')
            if action == 'nightlight_set':
                if before != enabled:
                    _command(executor, ['omarchy', 'toggle', 'nightlight'])
                after, temp = _nightlight(executor)
                if after != enabled:
                    raise SystemControlError('Night light state could not be verified')
                temp_s = f' ({temp}K)' if temp else ''
                return Result(True, f'Night light turned on{temp_s} (verified).' if after else f'Night light turned off{temp_s} (verified).')
            _command(executor, ['omarchy', 'toggle', 'nightlight'])
            after, temp = _nightlight(executor)
            if after == before:
                raise SystemControlError('Night light toggle could not be verified')
            temp_s = f' ({temp}K)' if temp else ''
            return Result(True, f'Night light toggled on{temp_s} (verified).' if after else f'Night light toggled off{temp_s} (verified).')

        if action.startswith('idle_'):
            before = _idle(executor)
            if action == 'idle_get':
                return Result(True, 'Stay-awake (sleep inhibitor) is enabled.' if before else 'Normal idle and sleep are enabled.')
            if action == 'idle_set':
                if before != enabled:
                    _command(executor, ['omarchy', 'toggle', 'idle', 'stay-awake' if enabled else 'allow-idle'])
                after = _idle(executor)
                if after != enabled:
                    raise SystemControlError('Stay-awake state could not be verified')
                return Result(True, 'Stay-awake enabled (verified).' if after else 'Normal idle restored (verified).')
            _command(executor, ['omarchy', 'toggle', 'idle', 'toggle'])
            after = _idle(executor)
            if after == before:
                raise SystemControlError('Stay-awake toggle could not be verified')
            return Result(True, 'Stay-awake enabled (verified).' if after else 'Normal idle restored (verified).')

        if action.startswith('dnd_'):
            before = _dnd(executor)
            if action == 'dnd_get':
                return Result(True, 'Do Not Disturb (notification silencing) is enabled.' if before else 'Do Not Disturb is disabled.')
            if action == 'dnd_set':
                if before != enabled:
                    _command(executor, ['omarchy', 'toggle', 'notification-silencing'])
                after = _dnd(executor)
                if after != enabled:
                    raise SystemControlError('Do Not Disturb state could not be verified')
                return Result(True, 'Do Not Disturb enabled (verified).' if after else 'Do Not Disturb disabled (verified).')
            _command(executor, ['omarchy', 'toggle', 'notification-silencing'])
            after = _dnd(executor)
            if after == before:
                raise SystemControlError('Do Not Disturb toggle could not be verified')
            return Result(True, 'Do Not Disturb toggled on (verified).' if after else 'Do Not Disturb toggled off (verified).')

        if action.startswith('bluetooth_'):
            before = _bluetooth(executor)
            if action == 'bluetooth_get':
                return Result(True, 'Bluetooth is powered on.' if before else 'Bluetooth is powered off.')
            if action == 'bluetooth_set':
                if before != enabled:
                    _command(executor, ['omarchy', 'bluetooth', 'power', 'on' if enabled else 'off'])
                after = _bluetooth(executor)
                if after != enabled:
                    raise SystemControlError('Bluetooth power state could not be verified')
                return Result(True, 'Bluetooth turned on (verified).' if after else 'Bluetooth turned off (verified).')
            _command(executor, ['omarchy', 'bluetooth', 'power', 'toggle'])
            after = _bluetooth(executor)
            if after == before:
                raise SystemControlError('Bluetooth toggle could not be verified')
            return Result(True, 'Bluetooth toggled on (verified).' if after else 'Bluetooth toggled off (verified).')

        if action.startswith('touchpad_'):
            before = _touchpad(executor)
            if action == 'touchpad_get':
                return Result(True, 'Touchpad is enabled.' if before else 'Touchpad is disabled.')
            if action == 'touchpad_set':
                if before != enabled:
                    _command(executor, ['omarchy', 'toggle', 'touchpad', 'on' if enabled else 'off'])
                after = _touchpad(executor)
                if after != enabled:
                    raise SystemControlError('Touchpad state could not be verified')
                return Result(True, 'Touchpad enabled (verified).' if after else 'Touchpad disabled (verified).')
            _command(executor, ['omarchy', 'toggle', 'touchpad', 'toggle'])
            after = _touchpad(executor)
            if after == before:
                raise SystemControlError('Touchpad toggle could not be verified')
            return Result(True, 'Touchpad toggled on (verified).' if after else 'Touchpad toggled off (verified).')

        if action.startswith('bar_'):
            before = _bar(executor)
            if action == 'bar_get':
                return Result(True, 'Status bar is visible.' if before else 'Status bar is hidden.')
            if action == 'bar_set':
                if before != enabled:
                    _command(executor, ['omarchy', 'toggle', 'bar', 'on' if enabled else 'off'])
                after = _bar(executor)
                if after != enabled:
                    raise SystemControlError('Status bar state could not be verified')
                return Result(True, 'Status bar visible (verified).' if after else 'Status bar hidden (verified).')
            _command(executor, ['omarchy', 'toggle', 'bar', 'toggle'])
            after = _bar(executor)
            if after == before:
                raise SystemControlError('Status bar toggle could not be verified')
            return Result(True, 'Status bar toggled on (verified).' if after else 'Status bar toggled off (verified).')

        before = _workspace(executor)
        if action == 'workspace_get':
            return Result(True, f'Workspace {before} is active.')
        if action == 'workspace_back':
            previous = getattr(executor, '_system_control_previous_workspace', '')
            if not previous:
                raise SystemControlError('No previous workspace has been recorded by system_control')
            workspace = _numbered_workspace(previous)
        result = executor._tool_hypr_dispatch('hl.dsp.focus({ workspace = ' + json.dumps(workspace) + ' })')
        if not result.ok:
            raise SystemControlError(result.output or 'Workspace switch failed')
        after = _workspace(executor)
        if after != workspace:
            raise SystemControlError(f'Workspace switch could not be verified; workspace {after} remains active')
        if before != after:
            executor._system_control_previous_workspace = before
        return Result(True, f'Workspace {after} is active (verified).')
    except SystemControlError as error:
        return Result(False, str(error))
    except OSError as error:
        return Result(False, f'System control unavailable: {error}')
