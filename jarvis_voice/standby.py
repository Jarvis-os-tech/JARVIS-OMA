"""Offline wake-word listener for privacy-preserving voice standby."""
from __future__ import annotations

import asyncio
from importlib.resources import files
import logging
from typing import Any, Optional

import numpy as np

log = logging.getLogger('jarvis_voice')


class WakeWordUnavailable(RuntimeError):
    """The configured local wake-word runtime could not be loaded."""


class OpenWakeWordDetector:
    """Recognize the bundled ``Hey Jarvis`` model from 16 kHz PCM16 frames."""

    sample_count = 1280  # openWakeWord consumes 80 ms (1280 samples) at 16 kHz

    def __init__(self, *, threshold: float = 0.05, vad_threshold: float = 0.0):
        try:
            from openwakeword.model import Model
            model_path = files('openwakeword').joinpath(
                'resources/models/hey_jarvis_v0.1.onnx')
            if not model_path.is_file():
                raise FileNotFoundError(str(model_path))
            self._model = Model(
                wakeword_model_paths=[str(model_path)],
                vad_threshold=vad_threshold,
            )
        except Exception as error:
            raise WakeWordUnavailable(
                'offline Hey Jarvis wake-word model is unavailable') from error
        self.threshold = threshold
        self._pcm = bytearray()
        self.last_score = 0.0
        self.peak_score = 0.0
        self._candidate_hits = 0
        self._candidate_age = 0

    def reset(self) -> None:
        self._pcm.clear()
        if hasattr(self, '_model') and hasattr(self._model, 'reset'):
            self._model.reset()
        self.last_score = 0.0
        self.peak_score = 0.0
        self._candidate_hits = 0
        self._candidate_age = 0

    def process(self, frame: bytes) -> bool:
        self._pcm.extend(frame)
        byte_count = self.sample_count * 2
        detected = False
        while len(self._pcm) >= byte_count:
            chunk = bytes(self._pcm[:byte_count])
            del self._pcm[:byte_count]
            samples = np.frombuffer(chunk, dtype='<i2')
            scores = self._model.predict(samples)
            self.last_score = (max(float(score) for score in scores.values())
                               if scores else 0.0)
            self.peak_score = max(getattr(self, 'peak_score', 0.0), self.last_score)
            if self.last_score >= self.threshold:
                self._candidate_hits = getattr(self, '_candidate_hits', 0) + 1
                self._candidate_age = 0
                strong_threshold = min(1.0, max(0.15, self.threshold + 0.05))
                if self.last_score >= strong_threshold or self._candidate_hits >= 2:
                    detected = True
                    log.info(
                        'Wake phrase matched (confidence %.3f, threshold %.3f, hits %d)',
                        self.last_score, self.threshold, self._candidate_hits)
                    self.reset()
                    break
            elif getattr(self, '_candidate_hits', 0):
                self._candidate_age = getattr(self, '_candidate_age', 0) + 1
                if self._candidate_age > 12:
                    self._candidate_hits = 0
                    self._candidate_age = 0
        return detected


class StandbyController:
    """Coordinate live-session shutdown and local wake-word activation."""

    def __init__(self, *, enabled: bool = True, threshold: float = 0.05,
                 vad_threshold: float = 0.0, detector=None,
                 arming_delay: float = 0.5):
        self.enabled = enabled
        self.threshold = threshold
        self.vad_threshold = vad_threshold
        self.detector = detector
        self.arming_delay = max(0.0, float(arming_delay))
        self.active = False
        self._requested = asyncio.Event()

    @property
    def engaged(self) -> bool:
        """True from the instant standby is requested until wake completes."""
        return self._requested.is_set() or self.active

    async def prepare(self) -> None:
        if self.enabled and self.detector is None:
            self.detector = OpenWakeWordDetector(
                threshold=self.threshold,
                vad_threshold=self.vad_threshold,
            )

    async def request(self) -> dict:
        if not self.enabled:
            raise WakeWordUnavailable('standby mode is disabled')
        await self.prepare()
        self._requested.set()
        return {'status': 'standby_requested', 'wake_phrase': 'Hey Jarvis'}

    async def wait_until_requested(self) -> None:
        await self._requested.wait()

    def cancel_request(self) -> None:
        self._requested.clear()

    async def listen_for_wake_word(self, stream: Any) -> None:
        if self.detector is None:
            await self.prepare()
        if self.detector is None:
            raise WakeWordUnavailable('wake-word detector is not ready')
        self.active = True
        try:
            if self.arming_delay:
                await asyncio.sleep(self.arming_delay)
            # Drain residual frames queued before standby armed
            if hasattr(stream, 'async_input_queue'):
                while not stream.async_input_queue.empty():
                    stream.async_input_queue.get_nowait()
            elif isinstance(stream, asyncio.Queue):
                while not stream.empty():
                    stream.get_nowait()
            self.detector.reset()
            windows = 0
            while True:
                if isinstance(stream, asyncio.StreamReader):
                    try:
                        frame = await stream.readexactly(640)
                    except asyncio.IncompleteReadError:
                        break
                elif hasattr(stream, 'async_input_queue'):
                    frame = await stream.async_input_queue.get()
                elif hasattr(stream, 'get'):
                    frame = await stream.get()
                elif hasattr(stream, 'read'):
                    frame = await stream.read(640)
                else:
                    raise TypeError(f"Unsupported stream type: {type(stream)}")

                if not frame:
                    break
                if self.detector.process(frame):
                    return
                windows += 1
                if windows % 250 == 0:
                    log.info('Wake listener active (peak confidence %.3f, threshold %.3f)',
                             self.detector.peak_score, self.threshold)
                    self.detector.peak_score = 0.0
        finally:
            self.active = False
            self._requested.clear()
