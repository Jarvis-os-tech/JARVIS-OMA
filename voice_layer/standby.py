"""Offline wake-word listener for privacy-preserving voice standby."""
from __future__ import annotations

import asyncio
from importlib.resources import files
import json
import logging
import math
import os
from pathlib import Path
from typing import Any, Optional

import numpy as np

log = logging.getLogger('voice_layer')


class WakeWordUnavailable(RuntimeError):
    """The configured local wake-word runtime could not be loaded."""


class LocalPhraseDetector:
    """Recognize both greetings locally using the bundled English speech model."""

    phrases = ('hey jarvis', 'hello jarvis')

    def __init__(self, *, recognizer=None, model_path=None):
        if recognizer is None:
            try:
                from vosk import Model, KaldiRecognizer
                path = Path(model_path or os.environ.get('JARVIS_WAKE_MODEL',
                    str(Path(__file__).with_name('assets') / 'wake-model'))).expanduser()
                # An explicit local path prevents Vosk from downloading a model.
                self._model = Model(str(path))
                grammar = [*self.phrases, 'hey', 'hello', 'jarvis', 'hey there',
                           'hello there', 'hello world', 'goodbye jarvis', '[unk]']
                recognizer = KaldiRecognizer(self._model, 16000, json.dumps(grammar))
                recognizer.SetWords(True)
                recognizer.SetPartialWords(True)
            except Exception as error:
                raise WakeWordUnavailable('local Hello/Hey Jarvis model is unavailable') from error
        self._recognizer = recognizer
        self.reset()

    def reset(self):
        self._recognizer.Reset()
        self.last_phrase = ''
        self.last_score = self.peak_score = 0.0

    def process(self, frame):
        final = self._recognizer.AcceptWaveform(frame)
        result = json.loads(self._recognizer.Result() if final else self._recognizer.PartialResult())
        phrase = ' '.join(result.get('text' if final else 'partial', '').casefold().split())
        if phrase not in self.phrases:
            return False
        words = result.get('result' if final else 'partial_result') or []
        if [word.get('word') for word in words] != phrase.split():
            return False
        scores = [word.get('conf') for word in words]
        if any(type(score) not in (float, int) or not math.isfinite(score) for score in scores):
            return False
        self.last_score = min(scores)
        self.peak_score = max(self.peak_score, self.last_score)
        if self.last_score < .80:
            return False
        self.last_phrase = phrase
        log.info('Local wake phrase matched: %s (confidence %.3f)', phrase, self.last_score)
        return True


class JarvisWakeDetector:
    """Keep the fast Hey model alongside explicit local Hello/Hey recognition."""

    def __init__(self, *, threshold=.50, vad_threshold=.50):
        self.detectors = []
        errors = []
        for factory in (lambda: LocalPhraseDetector(),
                        lambda: OpenWakeWordDetector(threshold=threshold, vad_threshold=vad_threshold)):
            try:
                self.detectors.append(factory())
            except WakeWordUnavailable as error:
                errors.append(str(error))
        if not self.detectors:
            raise WakeWordUnavailable('; '.join(errors))
        for error in errors:
            log.warning('Wake recognition degraded: %s', error)
        self.reset()

    @property
    def phrases(self):
        return ['Hey Jarvis', 'Hello Jarvis'] if any(isinstance(d, LocalPhraseDetector)
            for d in self.detectors) else ['Hey Jarvis']

    def reset(self):
        for detector in self.detectors:
            detector.reset()
        self.last_score = self.peak_score = 0.0

    def process(self, frame):
        for detector in self.detectors:
            detected = detector.process(frame)
            self.last_score = detector.last_score
            self.peak_score = max(self.peak_score, detector.peak_score)
            if detected:
                return True
        return False


class OpenWakeWordDetector:
    """Recognize the bundled ``Hey Jarvis`` model from 16 kHz PCM16 frames."""

    sample_count = 1280  # openWakeWord consumes 80 ms (1280 samples) at 16 kHz

    def __init__(self, *, threshold: float = 0.50, vad_threshold: float = 0.50):
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
        self.vad_threshold = vad_threshold
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
                strong_threshold = min(1.0, max(0.65 if self.threshold >= 0.4 else 0.15, self.threshold + 0.05))
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

    def __init__(self, *, enabled: bool = True, threshold: float = 0.50,
                 vad_threshold: float = 0.50, detector=None,
                 arming_delay: float = 0.1):
        self.enabled = enabled
        self.threshold = threshold
        self.vad_threshold = vad_threshold
        self.detector = detector
        self.arming_delay = max(0.0, float(arming_delay))
        self.active = False
        self._requested = asyncio.Event()
        self._wake_event = asyncio.Event()
        self.generation = 0

    @property
    def engaged(self) -> bool:
        """True from the instant standby is requested until wake completes."""
        return self._requested.is_set() or self.active

    def wake(self) -> None:
        """Trigger immediate wake from standby mode."""
        if self.engaged:
            self.generation += 1
            self._requested.clear()
            self._wake_event.set()

    async def prepare(self) -> None:
        if self.enabled and self.detector is None:
            self.detector = JarvisWakeDetector(
                threshold=self.threshold,
                vad_threshold=self.vad_threshold,
            )

    async def request(self) -> dict:
        if not self.enabled:
            raise WakeWordUnavailable('standby mode is disabled')
        if not self._requested.is_set():
            self.generation += 1
            self._wake_event.clear()
        self._requested.set()
        try:
            await self.prepare()
        except BaseException:
            self._requested.clear()
            raise
        return {'status': 'standby_requested', 'wake_phrase': 'Hey Jarvis',
                'wake_phrases': getattr(self.detector, 'phrases', ['Hey Jarvis'])}

    async def wait_until_requested(self) -> None:
        await self._requested.wait()

    def cancel_request(self) -> None:
        self._requested.clear()

    async def toggle(self) -> dict:
        if self.engaged and not self._wake_event.is_set():
            self.wake()
            return {'status': 'awake', 'standby': False}
        result = await self.request()
        return {**result, 'standby': True}

    async def _read_or_wake(self, stream):
        if isinstance(stream, asyncio.StreamReader):
            read = stream.readexactly(640)
        elif hasattr(stream, 'async_input_queue'):
            read = stream.async_input_queue.get()
        elif hasattr(stream, 'get'):
            read = stream.get()
        elif hasattr(stream, 'read'):
            read = stream.read(640)
        else:
            raise TypeError(f'Unsupported stream type: {type(stream)}')
        tasks = [asyncio.create_task(read), asyncio.create_task(self._wake_event.wait())]
        try:
            done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            if tasks[1] in done:
                return None
            return tasks[0].result()
        except asyncio.IncompleteReadError:
            return b''
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    async def listen_for_wake_word(self, stream: Any) -> None:
        if self._wake_event.is_set():
            self._requested.clear()
            self._wake_event.clear()
            return
        if self.detector is None:
            await self.prepare()
        if self.detector is None:
            raise WakeWordUnavailable('wake-word detector is not ready')
        generation = self.generation
        self.active = True
        try:
            if self.arming_delay:
                try:
                    await asyncio.wait_for(self._wake_event.wait(), self.arming_delay)
                    return
                except TimeoutError:
                    pass
            if hasattr(stream, 'async_input_queue'):
                while not stream.async_input_queue.empty():
                    stream.async_input_queue.get_nowait()
            elif isinstance(stream, asyncio.Queue):
                while not stream.empty():
                    stream.get_nowait()
            self.detector.reset()
            windows = 0
            while not self._wake_event.is_set():
                frame = await self._read_or_wake(stream)
                if frame is None:
                    return
                if not frame:
                    raise WakeWordUnavailable('wake microphone stream ended before a wake request')
                if self.detector.process(frame):
                    return
                windows += 1
                if windows % 250 == 0:
                    log.info('Wake listener active (peak confidence %.3f, threshold %.3f)',
                             self.detector.peak_score, self.threshold)
                    self.detector.peak_score = 0.0
        finally:
            self.active = False
            # An old listener must not erase a newer standby request.
            if generation == self.generation or not self._requested.is_set():
                self._requested.clear()
                self._wake_event.clear()
