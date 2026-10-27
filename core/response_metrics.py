"""Bounded observation timings for voice replies, without retaining speech.

These measurements begin when a recognized-input update reaches the client.
They are not acoustic end-of-speech latency: provider transcription can arrive
out of order, and speaker buffering happens after the first PCM is received.
"""
from __future__ import annotations

from collections import deque
import time


class ResponseMetrics:
    def __init__(self, *, clock=time.monotonic, capacity=64):
        if type(capacity) is not int or capacity < 1:
            raise ValueError('response metric capacity must be a positive integer')
        self._clock = clock
        self._audio_samples = deque(maxlen=capacity)
        self.reset()

    def recognized_input(self, now=None):
        """Anchor the next response observations to the latest input update."""
        self._input_at = self._clock() if now is None else now
        self._first_audio_ms = None
        self._first_tool_ms = None

    def _elapsed(self, now):
        if self._input_at is None:
            return None
        elapsed = ((self._clock() if now is None else now) - self._input_at) * 1000
        return round(elapsed, 3) if elapsed >= 0 else None

    def audio_received(self, now=None):
        """Count the first subsequent PCM packet once per input observation."""
        if self._first_audio_ms is None:
            elapsed = self._elapsed(now)
            if elapsed is not None:
                self._first_audio_ms = elapsed
                self._audio_samples.append(elapsed)

    def tool_started(self, now=None):
        """Record the first tool dispatch following the latest input update."""
        if self._first_tool_ms is None:
            self._first_tool_ms = self._elapsed(now)

    def reset(self):
        """Discard the current observation while keeping bounded prior samples."""
        self._input_at = None
        self._first_audio_ms = None
        self._first_tool_ms = None

    def interrupted(self):
        self.reset()

    def snapshot(self):
        ordered = sorted(self._audio_samples)

        def percentile(fraction):
            if not ordered:
                return None
            position = (len(ordered) - 1) * fraction
            lower = int(position)
            upper = min(lower + 1, len(ordered) - 1)
            return round(ordered[lower] + (ordered[upper] - ordered[lower]) *
                         (position - lower), 3)

        return {
            'response_first_audio_ms': self._first_audio_ms,
            'response_first_audio_p50_ms': percentile(.50),
            'response_first_audio_p95_ms': percentile(.95),
            'response_first_audio_samples': len(ordered),
            'response_first_tool_ms': self._first_tool_ms,
        }
