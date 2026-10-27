import asyncio
import json

import pytest

from scripts.island_status import snapshot, stream


def test_island_telemetry_excludes_private_content_and_bounds_values():
    record = snapshot({'state': 'listening', 'activity': 'a' * 300,
                       'microphone_rms': 0.04, 'active_jobs': 4000,
                       'transcript': 'private text', 'tool_arguments': {'secret': 'private'},
                       'model': 'model', 'vision_mode': 'screen'})
    assert len(record['activity']) == 160
    assert record['active_jobs'] == 999
    assert record['microphone_rms'] == 0.04
    assert record['level_available'] is True
    assert 'private' not in json.dumps(record)


@pytest.mark.parametrize('rms', [float('nan'), float('inf'), -1, None, '0.3', True])
def test_unusable_audio_level_cannot_animate_a_fake_meter(rms):
    record = snapshot({'state': 'listening', 'microphone_rms': rms})
    assert record['microphone_rms'] == 0
    assert record['level_available'] is False
    json.dumps(record, allow_nan=False)


def test_disconnection_discards_stale_voice_and_sharing_state():
    record = snapshot({'state': 'offline', 'muted': True, 'standby': True,
                       'activity': 'Speaking', 'microphone_rms': 1,
                       'active_jobs': 3, 'vision_mode': 'screen', 'model': 'old'})
    assert record['activity'] == 'JARVIS is offline'
    assert record['microphone_rms'] == record['active_jobs'] == 0
    assert record['vision_mode'] == 'off'
    assert record['model'] == ''


def test_reconnection_revision_cannot_display_stale_speech_or_capture_state():
    record = snapshot({'state': 'speaking', 'connection_state': 'reconnecting',
                       'connection_revision': 9, 'microphone_rms': .8,
                       'vision_mode': 'screen', 'model': 'old', 'active_jobs': 3})
    assert record['state'] == 'reconnecting'
    assert record['connection_revision'] == 9
    assert record['microphone_rms'] == 0
    assert record['vision_mode'] == 'off'
    assert record['model'] == ''


def test_mute_stops_input_animation_without_claiming_capture_release():
    record = snapshot({'state': 'listening', 'muted': True, 'microphone_rms': 0.5})
    assert record['muted'] is True
    assert record['microphone_rms'] == 0
    assert record['level_available'] is False


@pytest.mark.asyncio
async def test_stream_updates_live_levels_and_reduces_idle_polling():
    records = iter([
        {'state': 'listening', 'microphone_rms': 0.01},
        {'state': 'listening', 'microphone_rms': 0.04},
        {'state': 'offline'}, {'state': 'offline'},
    ])
    output, intervals = [], []

    async def fetch():
        return next(records)

    async def sleep(interval):
        intervals.append(interval)
        if len(intervals) == 4:
            raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        await stream(fetch=fetch, emit=lambda line, **kwargs: output.append(json.loads(line)), sleep=sleep)
    assert len(output) == 3
    assert [r['microphone_rms'] for r in output] == [0.01, 0.04, 0]
    assert intervals == [0.25, 0.25, 1.0, 1.0]
