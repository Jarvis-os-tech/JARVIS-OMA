"""Isolated spoken interruption extension over the private echo-cancelled source.

The short playback reference stays in memory. It supplements PipeWire WebRTC
AEC; it is not a replacement for acoustic cancellation or a speaker-identity
model. No recording, transcript or audio is persisted here.
"""
from collections import deque
import time

import numpy as np

from core.speech_turn import GateFrame, SileroSpeechDetector


class PlaybackReference:
    def __init__(self):
        self.samples = deque(maxlen=2400)  # 1.2 seconds at 2 kHz.
        self.pending = b''
        self.updated_at = float('-inf')

    def add(self, pcm, *, now=None):
        data = self.pending + pcm
        count = len(data) // 24 * 24  # 12 PCM16 samples: 24 kHz -> 2 kHz.
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
            return None  # Need at least 80 ms before admitting double-talk.
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
    """Require 120 ms of speech evidence, independent of recent speaker output."""
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
        self._microphone.extend(samples.reshape(-1, 8).mean(axis=1).tolist())
        self._frames.append(pcm)
        rms = float(np.sqrt(np.mean(samples * samples))) / 32768
        if rms < .004:
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
