import asyncio
import json
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from voice_layer.echo import MonitorEchoCancellation
from voice_layer.daemon import LiveVoice
from voice_layer.playback import Playback


def echo_for(previous):
    echo = MonitorEchoCancellation()
    echo.active = True
    echo.microphone = 'physical-input'
    echo._physical_muted = previous
    return echo


def sources(echo, muted, **changes):
    return json.dumps([
        {'name': 'physical-input', 'mute': muted},
        {'name': echo.source, 'mute': True, **changes},
        {'name': 'different-default-input', 'mute': False},
    ])


@pytest.mark.asyncio
@pytest.mark.parametrize('previous,current', [(True, False), (False, True)])
async def test_physical_mute_transition_updates_only_owned_aec(monkeypatch, previous, current):
    echo = echo_for(previous)
    command = AsyncMock(side_effect=[sources(echo, current), ''])
    monkeypatch.setattr(sys.modules[MonitorEchoCancellation.__module__], 'pactl', command)
    await echo.sync_microphone_mute()
    command.assert_any_await('set-source-mute', echo.source, '1' if current else '0')
    assert echo._physical_muted is current
    assert command.await_count == 2


@pytest.mark.asyncio
async def test_independent_virtual_mute_is_preserved_until_physical_transition(monkeypatch):
    echo = echo_for(False)
    command = AsyncMock(return_value=sources(echo, False))
    monkeypatch.setattr(sys.modules[MonitorEchoCancellation.__module__], 'pactl', command)
    await echo.sync_microphone_mute()
    assert command.await_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize('snapshot', ['[]', '{}', '[null]', 'not-json',
                                      '[{"name":"physical-input","mute":"false"}]'])
async def test_unknown_physical_state_never_unmutes(monkeypatch, snapshot):
    echo = echo_for(True)
    command = AsyncMock(return_value=snapshot)
    monkeypatch.setattr(sys.modules[MonitorEchoCancellation.__module__], 'pactl', command)
    await echo.sync_microphone_mute()
    assert command.await_count == 1
    assert echo._physical_muted is True


@pytest.mark.asyncio
async def test_failed_update_is_retried_without_losing_physical_transition(monkeypatch):
    echo = echo_for(True)
    command = AsyncMock(side_effect=[sources(echo, False), RuntimeError('audio busy'),
                                    sources(echo, False), ''])
    monkeypatch.setattr(sys.modules[MonitorEchoCancellation.__module__], 'pactl', command)
    await echo.sync_microphone_mute()
    assert echo._physical_muted is True
    await echo.sync_microphone_mute()
    assert echo._physical_muted is False


@pytest.mark.asyncio
async def test_inactive_aec_never_changes_audio(monkeypatch):
    echo = echo_for(True)
    echo.active = False
    command = AsyncMock()
    monkeypatch.setattr(sys.modules[MonitorEchoCancellation.__module__], 'pactl', command)
    await echo.sync_microphone_mute()
    command.assert_not_awaited()


@pytest.mark.asyncio
async def test_health_monitor_syncs_before_reporting_recovered_input(monkeypatch):
    voice = LiveVoice(Playback('test'))
    order = []
    async def sync(): order.append('sync')
    async def health():
        order.append('health')
        return dict(source='owned-aec', muted=False, volume_percent=100, issue='')
    async def stop(_): raise asyncio.CancelledError
    monkeypatch.setattr(sys.modules[LiveVoice.__module__], 'read_microphone_state', health)
    monkeypatch.setattr(asyncio, 'sleep', stop)
    with pytest.raises(asyncio.CancelledError):
        await voice.monitor_microphone(SimpleNamespace(sync_microphone_mute=sync))
    assert order == ['sync', 'health']

@pytest.mark.asyncio
@pytest.mark.parametrize('snapshot', [
    '[{"name":"physical-input","mute":false}]',
    '[{"name":"physical-input","mute":false},{"name":"physical-input","mute":false}]',
])
async def test_missing_owned_node_or_ambiguous_physical_input_is_not_changed(monkeypatch, snapshot):
    echo = echo_for(True)
    command = AsyncMock(return_value=snapshot)
    monkeypatch.setattr(sys.modules[MonitorEchoCancellation.__module__], 'pactl', command)
    await echo.sync_microphone_mute()
    assert command.await_count == 1
    assert echo._physical_muted is True


@pytest.mark.asyncio
async def test_unknown_initial_mute_establishes_baseline_without_overriding_user(monkeypatch):
    echo = echo_for(None)
    command = AsyncMock(return_value=sources(echo, False))
    monkeypatch.setattr(sys.modules[MonitorEchoCancellation.__module__], 'pactl', command)
    await echo.sync_microphone_mute()
    assert command.await_count == 1
    assert echo._physical_muted is False


@pytest.mark.asyncio
async def test_shutdown_cancellation_is_not_swallowed(monkeypatch):
    echo = echo_for(True)
    command = AsyncMock(side_effect=asyncio.CancelledError)
    monkeypatch.setattr(sys.modules[MonitorEchoCancellation.__module__], 'pactl', command)
    with pytest.raises(asyncio.CancelledError):
        await echo.sync_microphone_mute()
