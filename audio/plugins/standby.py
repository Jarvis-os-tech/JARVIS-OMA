"""Offline wake-word listener for privacy-preserving voice standby."""
from __future__ import annotations

import asyncio
from importlib.resources import files
import logging

import numpy as np


log = logging.getLogger('gemini_voice')


class WakeWordUnavailable(RuntimeError):
    """The configured local wake-word runtime could not be loaded."""


class OpenWakeWordDetector:
    """Recognize the bundled ``Hey Jarvis`` model from 16 kHz PCM16 frames."""

    sample_count = 1280  # openWakeWord consumes 80 ms at 16 kHz

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

    def reset(self) -> None:
        self._pcm.clear()
        self._model.reset()
        self.last_score = 0.0
        self.peak_score = 0.0

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
                detected = True
                log.info('Wake phrase matched (confidence %.3f, threshold %.3f)',
                         self.last_score, self.threshold)
                self.reset()
                break
        return detected


class StandbyController:
    """Coordinate live-session shutdown and local wake-word activation."""

    def __init__(self, *, enabled: bool = True, threshold: float = 0.05,
                 vad_threshold: float = 0.0, detector=None):
        self.enabled = enabled
        self.threshold = threshold
        self.vad_threshold = vad_threshold
        self.detector = detector
        self.active = False
        self._requested = asyncio.Event()

    async def prepare(self) -> None:
        if self.enabled and self.detector is None:
            # ONNX sessions are created and used on the same event-loop thread;
            # this happens only on the first explicit standby request.
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
        self._requested.clear()

    async def listen_for_wake_word(self, engine) -> None:
        if self.detector is None:
            raise WakeWordUnavailable('wake-word detector is not ready')
        self.active = True
        self.detector.reset()
        while not engine.async_input_queue.empty():
            engine.async_input_queue.get_nowait()
        try:
            windows = 0
            while True:
                frame = await engine.async_input_queue.get()
                # Standby has no live network or playback loop to protect. Running
                # this small ONNX window inline also avoids cross-thread model state.
                if self.detector.process(frame):
                    return
                windows += 1
                if windows % 250 == 0:
                    log.info('Wake listener active (peak confidence %.3f, threshold %.3f)',
                             self.detector.peak_score, self.threshold)
                    self.detector.peak_score = 0.0
        finally:
            self.active = False
