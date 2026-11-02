"""Read microphone health for JARVIS's actual capture stream."""
import asyncio
import json
import math
import re

from .playback import stop_process


MICROPHONE_CHECK_SECONDS = 1.0


async def _pactl_json(kind):
    process = await asyncio.create_subprocess_exec(
        'pactl', '--format=json', 'list', kind,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
    )
    try:
        stdout, _ = await process.communicate()
        if process.returncode != 0:
            raise ValueError('Microphone lookup failed')
        data = json.loads(stdout)
        if not isinstance(data, list) or any(not isinstance(item, dict) for item in data):
            raise ValueError('Invalid microphone lookup')
        return data
    finally:
        if process.returncode is None:
            await stop_process(process)


def _gain_percent(volume):
    if not isinstance(volume, dict) or not volume:
        return None
    gains = []
    for channel in volume.values():
        if not isinstance(channel, dict):
            return None
        percent = channel.get('value_percent')
        if isinstance(percent, str) and re.fullmatch(r'\d+(?:\.\d+)?%', percent):
            value = float(percent[:-1])
        else:
            raw = channel.get('value')
            if isinstance(raw, bool) or not isinstance(raw, (int, float)):
                return None
            value = raw * 100 / 65536
        if not math.isfinite(value) or value < 0:
            return None
        gains.append(value)
    return max(gains)


async def read_microphone_state():
    """Inspect the tagged JARVIS stream; never change microphone settings.

    The system default can differ from an already-routed capture stream, so
    only JARVIS's application ID and its connected source determine health.
    """
    state = {'source': '', 'muted': None, 'volume_percent': None,
             'issue': 'Unable to verify the JARVIS microphone.'}
    try:
        async with asyncio.timeout(MICROPHONE_CHECK_SECONDS):
            streams = await _pactl_json('source-outputs')
            matches = [stream for stream in streams
                       if isinstance(stream.get('properties'), dict)
                       and stream['properties'].get('application.id') == 'jarvis-voice']
            if len(matches) != 1:
                return state
            stream = matches[0]
            source_id = stream.get('source')
            if (isinstance(source_id, bool) or not isinstance(source_id, (int, str))
                    or not str(source_id).isdigit()):
                return state
            sources = await _pactl_json('sources')
            sources = [source for source in sources
                       if str(source.get('index')) == str(source_id)]
            if len(sources) != 1:
                return state
            source = sources[0]
            if isinstance(source.get('name'), str):
                state['source'] = source['name']
            stream_mute, source_mute = stream.get('mute'), source.get('mute')
            if stream_mute is True or source_mute is True:
                state['muted'] = True
            elif stream_mute is False and source_mute is False:
                state['muted'] = False
            stream_gain, source_gain = _gain_percent(stream.get('volume')), _gain_percent(source.get('volume'))
            if stream_gain is not None and source_gain is not None:
                effective_gain = stream_gain * source_gain / 100
                state['volume_percent'] = max(1, round(effective_gain)) if effective_gain > 0 else 0
            if state['muted']:
                state['issue'] = 'The JARVIS microphone is muted in the system audio settings.'
            elif stream_gain == 0 or source_gain == 0:
                state['volume_percent'] = 0
                state['issue'] = 'The JARVIS microphone volume is zero in the system audio settings.'
            elif state['muted'] is False and state['volume_percent'] is not None:
                state['issue'] = ''
            return state
    except (OSError, ValueError, TypeError, TimeoutError):
        return state
