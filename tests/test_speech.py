# tests/test_speech.py
import struct
import math
from unittest.mock import MagicMock
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

def make_pcm_frame(amplitude=0):
    """Create a 20ms PCM16 frame (320 samples = 640 bytes)."""
    return struct.pack('<320h', *([amplitude] * 320))

def make_quiet_frame():
    """Frame below -54 dBFS threshold."""
    return make_pcm_frame(amplitude=1)

def make_speech_frame():
    """Frame with clear speech-level amplitude."""
    return make_pcm_frame(amplitude=8000)


class FakeDetector:
    """Deterministic speech detector for testing."""
    def __init__(self, scores=None):
        self._scores = list(scores or [])
        self._index = 0
        self.call_count = 0
        self.fresh_prediction = True

    def __call__(self, pcm):
        self.call_count += 1
        if self._index < len(self._scores):
            score = self._scores[self._index]
            self._index += 1
            return score
        return 0.0

    def reset(self):
        self._index = 0
        self.call_count = 0


def test_fix4_quiet_frames_still_reach_detector():
    """Fix 4: quiet frames must pass through the detector for state continuity."""
    from jarvis_voice.speech import SpeechTurnGate

    detector = FakeDetector(scores=[0.0, 0.0, 0.0])
    gate = SpeechTurnGate(detector=detector)

    # Send quiet frames — energy below -54 dBFS but not absolute zero
    # These should still reach the detector
    quiet = make_pcm_frame(amplitude=50)  # Low but nonzero
    for i in range(3):
        gate.process(quiet, now=float(i))

    assert detector.call_count >= 3, \
        f"Quiet frames must still reach detector, but only {detector.call_count} calls made"


def test_fix4_absolute_silence_skips_detector():
    """Absolute silence (all zeros) may skip the detector."""
    from jarvis_voice.speech import SpeechTurnGate

    detector = FakeDetector(scores=[0.0])
    gate = SpeechTurnGate(detector=detector)

    silence = make_pcm_frame(amplitude=0)
    gate.process(silence, now=0.0)

    # All-zero frames have energy == 0, can skip detector
    # (This is acceptable — absolute silence means no signal at all)


def test_fix5_quiet_frames_update_interruption_microphone_buffer():
    """Fix 5: quiet frames must still update the _microphone deque."""
    from jarvis_voice.speech import SpokenInterruption, PlaybackReference

    ref = PlaybackReference()
    detector = FakeDetector(scores=[0.0, 0.0, 0.0])
    interrupt = SpokenInterruption(reference=ref, detector=detector)

    quiet = make_pcm_frame(amplitude=10)  # RMS < 0.004 threshold
    for i in range(3):
        interrupt.process(quiet, now=float(i))

    # The microphone deque should have been updated even for quiet frames
    assert len(interrupt._microphone) > 0, \
        "Quiet frames must still update _microphone deque for state continuity"


def test_speech_turn_opens_on_voiced_frames():
    """Basic gate operation: opens after trigger_frames of speech."""
    from jarvis_voice.speech import SpeechTurnGate

    detector = FakeDetector(scores=[0.6, 0.7, 0.8])
    gate = SpeechTurnGate(detector=detector, trigger_frames=2)

    speech = make_speech_frame()
    f1 = gate.process(speech, now=0.0)
    f2 = gate.process(speech, now=0.02)

    assert f2.opened is True
    assert gate.active is True


def test_speech_turn_closes_on_silence():
    """Gate closes after silence_frames of quiet."""
    from jarvis_voice.speech import SpeechTurnGate

    scores = [0.8] * 3 + [0.1] * 25  # 3 speech + 25 silence
    detector = FakeDetector(scores=scores)
    gate = SpeechTurnGate(detector=detector, trigger_frames=2, silence_frames=20)

    speech = make_speech_frame()
    quiet = make_pcm_frame(amplitude=50)

    # Open the turn
    for i in range(3):
        gate.process(speech, now=float(i) * 0.02)
    assert gate.active is True

    # Close with silence
    closed = False
    for i in range(25):
        frame = gate.process(quiet, now=0.06 + float(i) * 0.02)
        if frame.closed:
            closed = True
            break

    assert closed is True
