"""Tests for PipeWire monitor echo-cancellation module."""
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from jarvis_voice.echo import MonitorEchoCancellation, monitor_properties, pactl


def test_monitor_properties_structure():
    props = monitor_properties("source_node", "sink_node", "jarvis_aec_test")
    assert props["monitor.mode"] is True
    assert props["audio.rate"] == 48000
    assert props["capture.props"]["target.object"] == "source_node"
    assert props["sink.props"]["target.object"] == "sink_node"
    assert props["source.props"]["node.name"] == "jarvis_aec_test"
    assert props["source.props"]["priority.session"] == 0


@pytest.mark.asyncio
@pytest.mark.parametrize('source_muted', [False, True])
async def test_echo_cancellation_lifecycle_mocked(source_muted):
    echo = MonitorEchoCancellation()
    assert not echo.active

    with patch("jarvis_voice.echo.pactl", new_callable=AsyncMock) as mock_pactl, \
         patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec, \
         patch("jarvis_voice.echo.stop_process", new_callable=AsyncMock) as mock_stop:

        mock_pactl.side_effect = lambda *args: {
            ("get-default-source",): "alsa_mic",
            ("get-default-sink",): "alsa_speaker",
            ("list", "short", "sources"): f"1\t{echo.source}\tmodule-echo-cancel\ts16le 1ch 48000Hz\tIDLE",
            ('--format=json', 'list', 'sources'): json.dumps([{'name': 'alsa_mic', 'mute': source_muted}]),
            ('set-source-mute', echo.source, '1' if source_muted else '0'): '',
        }[args]

        mock_process = AsyncMock()
        mock_process.stdin = MagicMock()
        mock_process.stdin.drain = AsyncMock()
        mock_process.returncode = None
        mock_exec.return_value = mock_process

        success = await echo.start()
        assert success is True
        assert echo.active is True
        assert echo.sink == "alsa_speaker"
        mock_pactl.assert_any_await('set-source-mute', echo.source, '1' if source_muted else '0')
        assert not any(call.args[:2] == ('set-source-mute', 'alsa_mic') for call in mock_pactl.await_args_list)
        assert sum(call.args[:1] == ('set-source-mute',) for call in mock_pactl.await_args_list) == 1

        await echo.close()
        assert not echo.active
        mock_stop.assert_awaited_once_with(mock_process)


@pytest.mark.asyncio
async def test_echo_cancellation_graceful_failure_fallback():
    echo = MonitorEchoCancellation()
    with patch("jarvis_voice.echo.pactl", side_effect=RuntimeError("PipeWire unavailable")):
        success = await echo.start()
        assert success is False
        assert not echo.active
