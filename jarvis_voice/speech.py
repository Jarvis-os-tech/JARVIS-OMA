"""Local speech admission, turn gating, and spoken interruption detection.

Fixes from 30 Oct 2026 audit:
- Fix 4: Quiet frames still pass through the detector for state continuity.
- Fix 5: Quiet frames update the interruption microphone buffer.
"""
from collections import deque
from dataclasses import dataclass
import math
import struct
import time

import numpy as np


class SileroSpeechDetector:
    """Reuse the installed OpenWakeWord package's Silero VAD."""

    def __init__(self):
        import onnxruntime as ort
        ort.disable_telemetry_events()
        from openwakeword.vad import VAD
        self.np = np
        self.model = VAD()
        self._pending = np.empty(0, dtype='<i2')
        self._last_score = 0.0
        self.fresh_prediction = False

    def __call__(self, pcm):
        self._pending = self.np.concatenate((
            self._pending, self.np.frombuffer(pcm, dtype='<i2')))
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
    barge_in: bool = False


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
        self._needs_reset = True
        self.last_probability = self.peak_unadmitted_probability = 0.0

    def reset(self, hold_until=0.0):
        self.active = False
        self._voiced = self._quiet = 0
        self._hold_until = hold_until
        self._preroll.clear()
        self._needs_reset = True

    def admit_interruption(self):
        """Continue a locally verified interruption as a normal spoken turn."""
        self.reset()
        self.active = True
        self.accepted_turns += 1

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
        energy = sum(x * x for x in samples) / 320

        # Fix 4: Only skip detector for absolute silence (energy == 0).
        # Low-energy frames still pass through for detector state continuity.
        if energy == 0:
            score = 0.0
            fresh_prediction = True
        else:
            if self.detector is None:
                self.detector = SileroSpeechDetector()
            score = float(self.detector(pcm))
            fresh_prediction = getattr(self.detector, 'fresh_prediction', True)
            if not math.isfinite(score):
                raise RuntimeError('Local speech detector returned an invalid score')
            # Below -54 dBFS: clamp score to prevent ghost turns,
            # but we already fed the frame to the detector above.
            if energy < (32768 * .002) ** 2:
                score = 0.0

        self.last_probability = score
        if self.active:
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


class PlaybackReference:
    def __init__(self):
        self.samples = deque(maxlen=2400)
        self.pending = b''
        self.updated_at = float('-inf')

    def add(self, pcm, *, now=None):
        data = self.pending + pcm
        count = len(data) // 24 * 24
        self.pending = data[count:]
        if count:
            values = np.frombuffer(data[:count], dtype='<i2').astype(np.float32)
            self.samples.extend(values.reshape(-1, 12).mean(axis=1).tolist())
            self.updated_at = time.monotonic() if now is None else now

    def correlation(self, microphone, now):
        if now - self.updated_at > 1.2 or not self.samples:
            return 0.0
        signal = np.asarray(microphone, dtype=np.float64)
        reference = np.asarray(self.samples, dtype=np.float64)
        if len(signal) < 160 or len(reference) < len(signal):
            return None
        signal = signal - signal.mean()
        energy = float(signal @ signal)
        if energy < 1:
            return 1.0
        n = len(signal)
        sums = np.concatenate(([0.0], np.cumsum(reference)))
        squares = np.concatenate(([0.0], np.cumsum(reference * reference)))
        variance = np.maximum(0, squares[n:] - squares[:-n] - (sums[n:] - sums[:-n]) ** 2 / n)
        products = np.correlate(reference, signal, mode='valid')
        scores = np.divide(np.abs(products), np.sqrt(variance * energy),
                           out=np.zeros_like(products), where=variance > 1)
        return float(np.clip(scores.max(initial=0), 0, 1))


class SpokenInterruption:
    """Require 120 ms of speech evidence, independent of recent speaker output.

    Fix 5: quiet frames still update _microphone deque for state continuity.
    """

    def __init__(self, reference, detector=None):
        self.reference = reference
        self.detector = detector
        self._frames = deque(maxlen=10)
        self._microphone = deque(maxlen=240)
        self._positives = self._voiced_frames = 0
        self.rejected_echo_frames = 0
        self.last_correlation = 0.0

    def reset(self):
        self._frames.clear()
        self._microphone.clear()
        self._positives = self._voiced_frames = 0

    def process(self, pcm, now):
        if len(pcm) != 640:
            raise ValueError('Spoken interruption requires a 20 ms PCM16 frame')
        samples = np.frombuffer(pcm, dtype='<i2').astype(np.float32)

        # Fix 5: Always update _microphone deque, even for quiet frames.
        self._microphone.extend(samples.reshape(-1, 8).mean(axis=1).tolist())
        self._frames.append(pcm)

        rms = float(np.sqrt(np.mean(samples * samples))) / 32768
        if rms < .004:
            # Fix 5: Still update the detector for state continuity, but
            # don't promote to an interruption.
            if self.detector is not None:
                self.detector(pcm)
            self._positives = self._voiced_frames = 0
            return None
        if self.detector is None:
            self.detector = SileroSpeechDetector()
        probability = float(self.detector(pcm))
        if not np.isfinite(probability):
            raise RuntimeError('Interruption detector returned an invalid probability')
        correlation = self.reference.correlation(self._microphone, now)
        self.last_correlation = correlation if correlation is not None else 1.0
        if correlation is not None and correlation >= .75:
            self.rejected_echo_frames += 1
            self._positives = self._voiced_frames = 0
            self._frames.clear()
            return None
        if probability < .8:
            self._positives = self._voiced_frames = 0
            return None
        self._voiced_frames += 1
        if getattr(self.detector, 'fresh_prediction', True):
            self._positives += 1
        if self._voiced_frames < 6 or self._positives < 4 or correlation is None:
            return None
        frame = GateFrame(b''.join(self._frames), opened=True, barge_in=True)
        self.reset()
        return frame
