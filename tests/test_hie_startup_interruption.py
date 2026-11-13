"""Startup barge-in behavior without microphone, speaker or network access."""
import asyncio
import math
import struct
import time
from types import SimpleNamespace

import pytest

from voice_layer.daemon import LiveVoice
from voice_layer.playback import Playback
from voice_layer.speech import GateFrame, PlaybackReference, SpokenInterruption


def pcm_tone(rate, seconds, frequency=440, amplitude=12000):
    return struct.pack(
        f'<{int(rate * seconds)}h',
        *(int(amplitude * math.sin(2 * math.pi * frequency * i / rate))
          for i in range(int(rate * seconds))),
    )


@pytest.mark.asyncio
async def test_capture_admits_verified_interruption_100ms_after_first_write():
    pcm = struct.pack('<320h', *([2000] * 320))
    player = Playback('default')
    player.enqueue(b'\x01\x00' * 480)
    player.first_write_at = time.monotonic() - 0.1
    voice = LiveVoice(player, barge_in=True)
    voice._reply_authorized = voice._reply_started = voice._model_active = True
    calls = []
    voice.barge_gate = SimpleNamespace(
        process=lambda chunk, now: calls.append(now) or GateFrame(chunk, opened=True, barge_in=True),
        reset=lambda: None,
    )
    reader = asyncio.StreamReader()
    reader.feed_data(pcm)
    reader.feed_eof()

    with pytest.raises(EOFError, match='Microphone stream ended'):
        await voice._capture_audio(reader, asyncio.Queue())

    assert len(calls) == 1
    assert voice.local_interruptions == 1


def test_playback_reference_rejects_startup_echo_without_startup_holdoff():
    playback = PlaybackReference()
    playback.add(pcm_tone(24000, 0.5), now=1.0)

    class Detector:
        fresh_prediction = True

        def __call__(self, _pcm):
            return 0.95

        def reset(self):
            pass

    interruption = SpokenInterruption(playback, detector=Detector())
    mic = pcm_tone(16000, 0.5)
    results = [interruption.process(mic[i:i + 640], 1.01 + i / 32000)
               for i in range(0, len(mic), 640)]

    assert interruption.rejected_echo_frames > 0
    assert not any(results)


def test_distinct_user_speech_interrupts_during_startup():
    playback = PlaybackReference()
    playback.add(pcm_tone(24000, 0.5, frequency=440), now=1.0)

    class Detector:
        fresh_prediction = True

        def __call__(self, _pcm):
            return 0.95

        def reset(self):
            pass

    interruption = SpokenInterruption(playback, detector=Detector())
    mic = pcm_tone(16000, 0.3, frequency=730)
    accepted_at = None
    for i in range(0, len(mic), 640):
        if interruption.process(mic[i:i + 640], 1.01 + i / 32000):
            accepted_at = i / 32000
            break

    assert accepted_at is not None
    assert accepted_at < 0.2


def test_interruption_waits_when_playback_reference_is_unavailable():
    class Detector:
        fresh_prediction = True

        def __call__(self, _pcm):
            return 0.95

        def reset(self):
            pass

    interruption = SpokenInterruption(PlaybackReference(), detector=Detector())
    pcm = pcm_tone(16000, 0.2)
    results = [interruption.process(pcm[i:i + 640], 1.0 + i / 32000)
               for i in range(0, len(pcm), 640)]

    assert all(result is None for result in results)
