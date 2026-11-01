import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from jarvis_voice import microphone


def volume(*percentages):
    return {str(index): {'value_percent': f'{value}%'}
            for index, value in enumerate(percentages)}


def stream(**changes):
    return {'source': 7, 'mute': False, 'volume': volume(100),
            'properties': {'application.id': 'jarvis-voice'}, **changes}


def source(**changes):
    return {'index': 7, 'name': 'custom.microphone', 'mute': False,
            'volume': volume(50), **changes}


def mock_audio(monkeypatch, streams=None, sources=None):
    lookup = AsyncMock(side_effect=[streams if streams is not None else [stream()],
                                    sources if sources is not None else [source()]])
    monkeypatch.setattr(microphone, '_pactl_json', lookup)
    return lookup


@pytest.mark.asyncio
async def test_reads_actual_routed_jarvis_source_ignoring_other_apps(monkeypatch):
    lookup = mock_audio(monkeypatch,
                        [stream(source=3, properties={'application.id': 'other.app'}), stream()],
                        [source(index=3, name='default', mute=True), source()])
    assert await microphone.read_microphone_state() == {
        'source': 'custom.microphone', 'muted': False, 'volume_percent': 50, 'issue': ''}
    assert [call.args for call in lookup.call_args_list] == [('source-outputs',), ('sources',)]


@pytest.mark.asyncio
@pytest.mark.parametrize('stream_muted,source_muted', [(True, False), (False, True), (True, True)])
async def test_reports_mute_on_either_stream_or_source(monkeypatch, stream_muted, source_muted):
    mock_audio(monkeypatch, [stream(mute=stream_muted)], [source(mute=source_muted)])
    state = await microphone.read_microphone_state()
    assert state['muted'] is True
    assert 'muted' in state['issue']


@pytest.mark.asyncio
@pytest.mark.parametrize('stream_volume,source_volume', [(volume(0, 0), volume(50)), (volume(100), volume(0, 0))])
async def test_reports_zero_only_when_all_channels_at_zero(monkeypatch, stream_volume, source_volume):
    mock_audio(monkeypatch, [stream(volume=stream_volume)], [source(volume=source_volume)])
    state = await microphone.read_microphone_state()
    assert state['volume_percent'] == 0
    assert 'zero' in state['issue']


@pytest.mark.asyncio
async def test_one_live_channel_is_not_zero_gain(monkeypatch):
    mock_audio(monkeypatch, [stream(volume=volume(0, 100))], [source(volume=volume(0, 45))])
    assert (await microphone.read_microphone_state())['issue'] == ''


@pytest.mark.asyncio
async def test_tiny_positive_gain_does_not_round_to_blocked_zero(monkeypatch):
    mock_audio(monkeypatch, [stream(volume=volume(100))], [source(volume=volume(.4))])
    state = await microphone.read_microphone_state()
    assert state['volume_percent'] == 1
    assert state['issue'] == ''


@pytest.mark.asyncio
async def test_raw_pulse_volume_is_supported(monkeypatch):
    mock_audio(monkeypatch, [stream(volume={'mono': {'value': 65536}})],
               [source(volume={'mono': {'value': 32768}})])
    assert (await microphone.read_microphone_state())['volume_percent'] == 50


@pytest.mark.asyncio
@pytest.mark.parametrize('streams,sources', [
    ([], []), ([stream(), stream()], [source()]),
    ([stream(source=99)], [source()]),
    ([stream(properties=None)], [source()]),
    ([stream(source=None)], [source()]),
    ([stream(source='None')], [source(index=None)]),
])
async def test_missing_or_ambiguous_capture_is_unknown(monkeypatch, streams, sources):
    mock_audio(monkeypatch, streams, sources)
    state = await microphone.read_microphone_state()
    assert state['muted'] is None
    assert state['volume_percent'] is None
    assert 'Unable to verify' in state['issue']


@pytest.mark.asyncio
@pytest.mark.parametrize('changes', [{'mute': 'false'}, {'volume': {}}, {'volume': {'mono': {'value': True}}}])
async def test_malformed_health_never_claims_a_muted_microphone(monkeypatch, changes):
    mock_audio(monkeypatch, [stream()], [source(**changes)])
    state = await microphone.read_microphone_state()
    assert state['muted'] is not True
    assert 'Unable to verify' in state['issue']


@pytest.mark.asyncio
@pytest.mark.parametrize('output', [b'not json', b'{}', b'[null]'])
async def test_bad_command_output_is_unknown(monkeypatch, output):
    process = SimpleNamespace(returncode=0, communicate=AsyncMock(return_value=(output, b'')))
    spawn = AsyncMock(return_value=process)
    monkeypatch.setattr(microphone.asyncio, 'create_subprocess_exec', spawn)
    state = await microphone.read_microphone_state()
    assert state['muted'] is None
    assert 'Unable to verify' in state['issue']
    assert spawn.call_args.args == ('pactl', '--format=json', 'list', 'source-outputs')


@pytest.mark.asyncio
async def test_failed_command_is_unknown(monkeypatch):
    process = SimpleNamespace(returncode=1, communicate=AsyncMock(return_value=(b'[]', b'')))
    monkeypatch.setattr(microphone.asyncio, 'create_subprocess_exec', AsyncMock(return_value=process))
    assert (await microphone.read_microphone_state())['muted'] is None


@pytest.mark.asyncio
@pytest.mark.parametrize('error', [FileNotFoundError(), PermissionError()])
async def test_missing_command_or_audio_access_is_unknown(monkeypatch, error):
    monkeypatch.setattr(microphone.asyncio, 'create_subprocess_exec', AsyncMock(side_effect=error))
    assert (await microphone.read_microphone_state())['muted'] is None


@pytest.mark.asyncio
async def test_timeout_stops_its_owned_process(monkeypatch):
    async def hang():
        await asyncio.Event().wait()
    process = SimpleNamespace(returncode=None, communicate=hang)
    cleanup = AsyncMock()
    monkeypatch.setattr(microphone.asyncio, 'create_subprocess_exec', AsyncMock(return_value=process))
    monkeypatch.setattr(microphone, 'stop_process', cleanup)
    monkeypatch.setattr(microphone, 'MICROPHONE_CHECK_SECONDS', .01)
    state = await microphone.read_microphone_state()
    assert state['muted'] is None
    assert 'Unable to verify' in state['issue']
    cleanup.assert_awaited_once_with(process)


@pytest.mark.asyncio
async def test_cancellation_cleans_up_and_propagates(monkeypatch):
    started = asyncio.Event()
    async def hang():
        started.set()
        await asyncio.Event().wait()
    process = SimpleNamespace(returncode=None, communicate=hang)
    cleanup = AsyncMock()
    monkeypatch.setattr(microphone.asyncio, 'create_subprocess_exec', AsyncMock(return_value=process))
    monkeypatch.setattr(microphone, 'stop_process', cleanup)
    task = asyncio.create_task(microphone.read_microphone_state())
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    cleanup.assert_awaited_once_with(process)
