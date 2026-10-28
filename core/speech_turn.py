"""Local speech admission and a speaker-echo holdoff for protected voice turns."""
from collections import deque
from dataclasses import dataclass
import math
import struct


class SileroSpeechDetector:
    """Reuse the already-installed offline wake-word package's Silero VAD."""
    def __init__(self):
        import numpy as np
        import onnxruntime as ort
        ort.disable_telemetry_events()
        from openwakeword.vad import VAD
        self.np = np
        self.model = VAD()
        self._pending = np.empty(0, dtype='<i2')
        self._last_score = 0.0
        self.fresh_prediction = False

    def __call__(self, pcm):
        # This installed Silero model recommends 480 samples (30 ms). Sending
        # 320 samples markedly reduces detection under background noise. Keep
        # transport at 20 ms, but feed contiguous, non-overlapping model windows.
        self._pending = self.np.concatenate((self._pending, self.np.frombuffer(pcm, dtype='<i2')))
        if len(self._pending) < 480:
            self.fresh_prediction = False
            return self._last_score
        chunk, self._pending = self._pending[:480], self._pending[480:]
        score = float(self.model.predict(chunk, frame_size=480))
        if not math.isfinite(score):
            raise RuntimeError('Local speech detector returned an invalid score')
        self.fresh_prediction = True
        self._last_score = score
        return score

    def reset(self):
        self._pending = self.np.empty(0, dtype='<i2')
        self._last_score = 0.0
        self.fresh_prediction = False
        self.model.reset_states()


@dataclass(frozen=True)
class GateFrame:
    pcm: bytes
    opened: bool = False
    closed: bool = False


class SpeechTurnGate:
    def __init__(self, detector=None, trigger_frames=2, silence_frames=30, tail_seconds=.45):
        self.detector = detector
        self.trigger_frames, self.silence_frames = trigger_frames, silence_frames
        self.tail_seconds = tail_seconds
        self.active = False
        self.accepted_turns = self.suppressed_frames = 0
        self._voiced = self._quiet = 0
        self._hold_until = 0.0
        self._preroll = deque(maxlen=10)
        self._needs_reset = False
        self.last_probability = self.peak_unadmitted_probability = 0.0

    def reset(self, hold_until=0.0):
        self.active = False
        self._voiced = self._quiet = 0
        self._hold_until = hold_until
        self._preroll.clear()
        self._needs_reset = True

    def process(self, pcm, now, blocked=False):
        if len(pcm) != 640:
            raise ValueError('Speech admission requires a 20 ms PCM16 frame')
        if blocked:
            self.reset(hold_until=now + self.tail_seconds)
        if blocked or now < self._hold_until:
            self.suppressed_frames += 1
            return GateFrame(bytes(640))
        if self._needs_reset:
            reset = getattr(self.detector, 'reset', None)
            if callable(reset):
                reset()
            self._needs_reset = False
        samples = struct.unpack('<320h', pcm)
        energy = sum(x*x for x in samples) / 320
        fresh_prediction = True
        # Below -54 dBFS cannot open a turn, even with lingering VAD state.
        if energy < (32768 * .002) ** 2:
            score = 0.0
        else:
            if self.detector is None:
                self.detector = SileroSpeechDetector()
            score = float(self.detector(pcm))
            fresh_prediction = getattr(self.detector, 'fresh_prediction', True)
            if not math.isfinite(score):
                raise RuntimeError('Local speech detector returned an invalid score')
        self.last_probability = score
        if self.active:
            # Continuing speech can be less confident than its onset. Keep a
            # noisy phrase together without lowering the .5 start threshold.
            self._quiet = self._quiet + 1 if score < .25 else 0
            if self._quiet >= self.silence_frames:
                self.active = False
                self._voiced = self._quiet = 0
                self._needs_reset = True
                return GateFrame(pcm, closed=True)
            return GateFrame(pcm)
        self._preroll.append(pcm)
        self.peak_unadmitted_probability = max(self.peak_unadmitted_probability, score)
        if fresh_prediction:
            self._voiced = self._voiced + 1 if score >= .5 else 0
        if self._voiced >= self.trigger_frames:
            self.active = True
            self.accepted_turns += 1
            self.peak_unadmitted_probability = 0.0
            buffered = b''.join(self._preroll)
            self._preroll.clear()
            return GateFrame(buffered, opened=True)
        self.suppressed_frames += 1
        return GateFrame(bytes(640))
