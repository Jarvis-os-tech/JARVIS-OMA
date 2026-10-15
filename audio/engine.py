"""Native real-time audio engine using PortAudio C-bindings via sounddevice.

Replaces the legacy pw-play/pw-record subprocess pipeline with persistent
hardware streams whose callbacks run in high-priority C threads outside
Python's GIL.  The input path pushes raw microphone bytes into an asyncio
queue; the output path pulls generation-tagged PCM frames from a thread-safe
``queue.SimpleQueue`` so the C callback never touches asyncio internals.
"""
from __future__ import annotations

import asyncio
import collections
import logging
import queue
import threading
import time
from collections.abc import Callable
from typing import Optional

import numpy as np
import sounddevice as sd

log = logging.getLogger('jarvis.audio')


class StreamLostError(Exception):
    """Raised when an underlying PortAudio stream dies or its device vanishes."""


class NativeAudioEngine:
    """Full-duplex isochronous PortAudio engine with zero-abort AEC lock,
    40ms vocal bandpass ducking, and 300ms barge-in promotion.

    Parameters
    ----------
    loop : asyncio.AbstractEventLoop, optional
        Event loop for cross-thread dispatch.  Resolved at construction time
        so callbacks can safely use ``call_soon_threadsafe``.
    input_rate : int
        Capture sample rate (default 16 000 Hz — Gemini upstream requirement).
    output_rate : int
        Playback sample rate (default 24 000 Hz — Gemini downstream format).
    input_frame_ms : int
        Capture frame duration in milliseconds (default 20).
    output_frame_ms : int
        Playback frame duration in milliseconds (default 20).
    input_queue_capacity : int
        Maximum queued capture frames before oldest-frame eviction (default 50).
    voice_rms_threshold : float
        Minimum RMS power required to evaluate a frame for speech (default 450.0).
    voice_band_ratio : float
        Minimum fraction of spectral energy in the 300Hz-3400Hz band to qualify
        as human voice (default 0.55).
    duck_after_ms : int
        Duration of sustained voice before ducking playback (default 40ms = 2 frames).
    barge_in_after_ms : int
        Duration of sustained voice before flushing playback (default 300ms = 15 frames).
    release_after_ms : int
        Duration of silence before restoring ducked playback (default 120ms = 6 frames).
    duck_gain : float
        Output gain multiplier when ducked (default 0.30 = -10.5 dB).
    fade_ms : int
        Duration of linear gain ramps in milliseconds (default 10ms).
    on_barge_in : Callable[[], None], optional
        Callback invoked when a local barge-in is triggered.
    on_state_change : Callable[[str], None], optional
        Callback invoked when the engine state transitions ("listening", "speaking", "ducked", "barged_in").
    """

    def __init__(
        self,
        loop: asyncio.AbstractEventLoop | None = None,
        *,
        input_rate: int = 16_000,
        output_rate: int = 24_000,
        input_frame_ms: int = 20,
        output_frame_ms: int = 20,
        input_queue_capacity: int = 50,
        voice_rms_threshold: float = 450.0,
        voice_band_ratio: float = 0.55,
        duck_after_ms: int = 40,
        barge_in_after_ms: int = 300,
        release_after_ms: int = 120,
        duck_gain: float = 0.30,
        fade_ms: int = 10,
        on_barge_in: Optional[Callable[[], None]] = None,
        on_state_change: Optional[Callable[[str], None]] = None,
    ):
        self.loop = loop or asyncio.get_running_loop()
        self.on_barge_in = on_barge_in
        self.on_state_change = on_state_change

        # Thread-boundary queues ------------------------------------------------
        self._input_queue_capacity = input_queue_capacity
        self.async_input_queue: asyncio.Queue[bytes] = asyncio.Queue(
            maxsize=self._input_queue_capacity,
        )
        # SimpleQueue is thread-safe without requiring asyncio event-loop access.
        self.c_output_queue: queue.SimpleQueue[tuple[int, bytes]] = queue.SimpleQueue()

        # Audio parameters ------------------------------------------------------
        self.input_rate = input_rate
        self.output_rate = output_rate
        self.input_block_size = input_rate * input_frame_ms // 1000   # 320 samples @ 16kHz
        self.output_block_size = output_rate * output_frame_ms // 1000  # 480 samples @ 24kHz
        self.output_frame_bytes = self.output_block_size * 2  # 960 bytes (16-bit mono)
        self.input_frame_ms = input_frame_ms

        # State & Generation ----------------------------------------------------
        self.active_generation: int = 0
        self.muted: bool = False
        self.speaking: bool = False
        self.state: str = 'listening'  # 'listening' | 'speaking' | 'ducked' | 'barged_in'

        # Telemetry & noise floor -----------------------------------------------
        self.input_rms: float = 0.0
        self.output_rms: float = 0.0
        self._noise_window: collections.deque[float] = collections.deque(maxlen=50)

        # Vocal detection parameters --------------------------------------------
        self.voice_rms_threshold = float(voice_rms_threshold)
        self.voice_band_ratio = float(voice_band_ratio)
        self.duck_frames = max(1, duck_after_ms // input_frame_ms)
        self.barge_frames = max(self.duck_frames + 1, barge_in_after_ms // input_frame_ms)
        self.release_frames = max(1, release_after_ms // input_frame_ms)
        self.duck_gain = float(duck_gain)
        self.fade_samples = max(1, output_rate * fade_ms // 1000)
        self._voice_frames = 0
        self._quiet_frames = 0
        self._barge_fired = False

        # Gain & micro-fade state -----------------------------------------------
        self._gain: float = 1.0
        self._target_gain: float = 1.0
        self._fade_out_pending: bool = False
        self._last_output_sample: np.int16 = np.int16(0)
        self._state_lock = threading.Lock()

        # Precompute vectorized FFT frequency bin mask (300Hz - 3400Hz @ 16kHz)
        freqs = np.fft.rfftfreq(self.input_block_size, d=1.0 / self.input_rate)
        self._vocal_mask = (freqs >= 300.0) & (freqs <= 3400.0)

        self.input_stream: sd.InputStream | None = None
        self.output_stream: sd.OutputStream | None = None

    def set_reconnect_buffering(self, enabled: bool) -> None:
        """Expands upstream buffer to 200 frames (4.0s) during GoAway handshakes."""
        self._input_queue_capacity = 200 if enabled else 50

    def _set_state(self, new_state: str) -> None:
        current_state = getattr(self, 'state', None)
        if current_state != new_state:
            self.state = new_state
            cb = getattr(self, 'on_state_change', None)
            if cb:
                try:
                    if getattr(self, 'loop', None) and self.loop.is_running():
                        self.loop.call_soon_threadsafe(cb, new_state)
                    else:
                        cb(new_state)
                except Exception:
                    pass

    # ------------------------------------------------------------------
    # PortAudio callbacks (run on dedicated OS C-threads, outside GIL)
    # ------------------------------------------------------------------

    def _input_callback(self, indata, frames, time_info, status):
        """Dispatch captured mic bytes into the asyncio event loop safely."""
        if status:
            self.loop.call_soon_threadsafe(
                log.warning, 'PortAudio input status: %s', status,
            )
        raw_bytes = bytes(indata)
        if self.muted:
            self.input_rms = 0.0
            # Send zero-floor PCM upstream so Gemini Live's clock never starves
            self.loop.call_soon_threadsafe(
                self._safe_enqueue_input, b'\x00' * len(raw_bytes),
            )
            return

        samples = np.frombuffer(raw_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        self.input_rms = min(float(np.sqrt(np.mean(samples * samples))), 1.0)
        self.loop.call_soon_threadsafe(self._safe_enqueue_input, raw_bytes)

    def _safe_enqueue_input(self, raw_bytes: bytes):
        """Enqueue with oldest-frame eviction to prevent C-thread blocking."""
        if self.async_input_queue.qsize() >= self._input_queue_capacity:
            try:
                self.async_input_queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
        self.async_input_queue.put_nowait(raw_bytes)
        self._update_voice_gate(raw_bytes)

    def _is_voice(self, raw_bytes: bytes) -> bool:
        """Return true when a frame contains sustained telephone-band speech energy."""
        samples = np.frombuffer(raw_bytes, dtype=np.int16).astype(np.float32)
        if samples.size < 8:
            return False
        samples -= float(samples.mean())
        rms = float(np.sqrt(np.mean(samples * samples)))
        if rms < self.voice_rms_threshold:
            return False
        spectrum = np.abs(np.fft.rfft(samples))
        vocal_energy = float(spectrum[self._vocal_mask].sum())
        total_spec_energy = float(spectrum[1:].sum()) + 1e-9
        return (vocal_energy / total_spec_energy) >= self.voice_band_ratio

    def _update_voice_gate(self, raw_bytes: bytes):
        """Duck short backchannels and flush only sustained user speech."""
        if not self.speaking:
            self._voice_frames = self._quiet_frames = 0
            self._barge_fired = False
            return
        if self._is_voice(raw_bytes):
            self._voice_frames += 1
            self._quiet_frames = 0
            if self._voice_frames >= self.duck_frames:
                self.set_output_gain(self.duck_gain)
                self._set_state('ducked')
            if self._voice_frames >= self.barge_frames and not self._barge_fired:
                self._barge_fired = True
                self.handle_barge_in()
                if self.on_barge_in is not None:
                    try:
                        if self.loop.is_running():
                            self.loop.call_soon_threadsafe(self.on_barge_in)
                        else:
                            self.on_barge_in()
                    except Exception:
                        pass
        else:
            self._quiet_frames += 1
            if self._quiet_frames >= self.release_frames:
                self._voice_frames = 0
                self._quiet_frames = 0
                self._barge_fired = False
                if self.speaking:
                    self.set_output_gain(1.0)
                    self._set_state('speaking')

    def _output_callback(self, outdata, frames, time_info, status):
        """Feed hardware speaker buffer from the thread-safe SimpleQueue."""
        if status:
            self.loop.call_soon_threadsafe(
                log.warning, 'PortAudio output status: %s', status,
            )

        # Micro-fade on barge-in without stopping or aborting stream
        if self._fade_out_pending:
            self._fade_out_pending = False
            ramp_len = min(120, len(outdata))
            ramp = np.linspace(float(self._last_output_sample), 0.0, ramp_len, dtype=np.float32)
            if outdata.ndim == 2:
                outdata[:ramp_len, 0] = ramp.astype(np.int16)
                outdata[ramp_len:, 0] = 0
            else:
                outdata[:ramp_len] = ramp.astype(np.int16)
                outdata[ramp_len:] = 0
            self._last_output_sample = np.int16(0)
            self.output_rms = 0.0
            self.speaking = False
            self._set_state('listening')
            return

        chunk = None
        while True:
            try:
                gen, candidate = self.c_output_queue.get_nowait()
                if gen == self.active_generation:
                    chunk = candidate
                    break
            except queue.Empty:
                break

        if chunk is None:
            outdata.fill(0)
            self._last_output_sample = np.int16(0)
            self.output_rms = 0.0
            if self.speaking:
                self.speaking = False
                self._set_state('listening')
            return

        samples = np.frombuffer(chunk, dtype=np.int16)
        n = min(len(samples), len(outdata))
        with self._state_lock:
            start_gain = self._gain
            target_gain = self._target_gain
            ramp_samples = min(n, self.fade_samples)
            if ramp_samples and abs(start_gain - target_gain) > 0.001:
                gain = np.empty(n, dtype=np.float32)
                gain[:ramp_samples] = np.linspace(start_gain, target_gain, ramp_samples)
                gain[ramp_samples:] = target_gain
                samples = np.clip(samples.astype(np.float32) * gain, -32768, 32767).astype(np.int16)
                self._gain = target_gain
            elif target_gain != 1.0:
                samples = np.clip(samples.astype(np.float32) * target_gain, -32768, 32767).astype(np.int16)

        if outdata.ndim == 2:
            outdata[:n, 0] = samples[:n]
            if n < frames:
                outdata[n:, 0] = 0
        else:
            outdata[:n] = samples[:n]
            if n < frames:
                outdata[n:] = 0

        self._last_output_sample = samples[n - 1] if n > 0 else np.int16(0)
        self.output_rms = min(float(np.sqrt(np.mean((samples[:n].astype(np.float32) / 32768.0) ** 2))), 1.0)
        if not self.speaking:
            self.speaking = True
            self._set_state('speaking')

    def set_output_gain(self, gain: float):
        """Set playback gain; the callback applies a click-free micro-fade."""
        with self._state_lock:
            self._target_gain = max(0.0, min(1.0, float(gain)))

    def enqueue_output(self, generation: int, chunk: bytes):
        """Queue one PCM frame and mark the persistent stream as speaking."""
        if not self.speaking:
            self.set_output_gain(1.0)
        self.speaking = True
        self._set_state('speaking')
        self.c_output_queue.put((generation, chunk))

    def enqueue_playback(self, raw_pcm_24k: bytes, generation: Optional[int] = None) -> None:
        """Enqueue arbitrary raw 24kHz PCM bytes sliced into 20ms frames."""
        if self.muted:
            return
        tag = self.active_generation if generation is None else generation
        for offset in range(0, len(raw_pcm_24k), self.output_frame_bytes):
            frame = raw_pcm_24k[offset : offset + self.output_frame_bytes]
            self.enqueue_output(tag, frame)

    # ------------------------------------------------------------------
    # Device resolution
    # ------------------------------------------------------------------

    @staticmethod
    def resolve_aec_devices(
        source_name: str,
        sink_name: str,
        *,
        retries: int = 3,
        delay: float = 0.5,
    ) -> tuple[int | None, int | None]:
        """Match PipeWire virtual AEC nodes by name substring."""
        source_lower = source_name.lower()
        sink_lower = sink_name.lower()
        for attempt in range(retries):
            devices = sd.query_devices()
            in_idx: int | None = None
            out_idx: int | None = None
            for idx, dev in enumerate(devices):
                name = dev.get('name', '').lower()
                if source_lower in name:
                    if dev.get('max_input_channels', 0) > 0:
                        in_idx = idx
                if sink_lower in name:
                    if dev.get('max_output_channels', 0) > 0:
                        out_idx = idx
            if in_idx is not None and out_idx is not None:
                log.info(
                    'AEC devices resolved: input=%s (idx %d), output=%s (idx %d)',
                    source_name, in_idx, sink_name, out_idx,
                )
                return in_idx, out_idx
            if attempt < retries - 1:
                time.sleep(delay)

        defaults = sd.default.device
        log.warning(
            'AEC virtual nodes not found after %d attempts; '
            'falling back to system defaults (input=%s, output=%s)',
            retries, defaults[0], defaults[1],
        )
        return defaults[0], defaults[1]

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self, source_name: str, sink_name: str):
        """Open persistent real-time streams bound to AEC virtual nodes."""
        in_id, out_id = self.resolve_aec_devices(source_name, sink_name)

        self.input_stream = sd.InputStream(
            samplerate=self.input_rate,
            channels=1,
            dtype='int16',
            blocksize=self.input_block_size,
            device=in_id,
            callback=self._input_callback,
        )
        self.output_stream = sd.OutputStream(
            samplerate=self.output_rate,
            channels=1,
            dtype='int16',
            blocksize=self.output_block_size,
            device=out_id,
            callback=self._output_callback,
        )
        self.input_stream.start()
        self.output_stream.start()
        self._set_state('listening')
        log.info(
            'Native audio engine started: capture %dHz/%d-sample blocks, '
            'playback %dHz/%d-sample blocks',
            self.input_rate, self.input_block_size,
            self.output_rate, self.output_block_size,
        )

    def handle_barge_in(self):
        """Flush playback without ever stopping the AEC-locked output stream."""
        self.active_generation += 1
        self._fade_out_pending = True
        self.set_output_gain(1.0)
        self._gain = 1.0
        self._voice_frames = 0
        while not self.c_output_queue.empty():
            try:
                self.c_output_queue.get_nowait()
            except queue.Empty:
                break
        self.speaking = False
        self._set_state('barged_in')

    def trigger_barge_in(self, notify_orchestrator: bool = True) -> None:
        """Explicitly trigger zero-abort barge-in with optional callback notification."""
        self.handle_barge_in()
        if notify_orchestrator and self.on_barge_in:
            try:
                if self.loop.is_running():
                    self.loop.call_soon_threadsafe(self.on_barge_in)
                else:
                    self.on_barge_in()
            except Exception:
                pass

    def set_muted(self, muted: bool) -> bool:
        """Toggle mic capture and playback enqueue gating."""
        self.muted = bool(muted)
        if self.muted:
            self.handle_barge_in()
        log.info('Audio engine muted: %s', self.muted)
        return self.muted

    async def stop_speaking(self):
        """Immediately stop playback while keeping the mic stream alive."""
        self.handle_barge_in()

    async def monitor_health(self):
        """Async sentinel: raises StreamLostError if a stream dies."""
        while True:
            await asyncio.sleep(2.0)
            if self.input_stream and not self.input_stream.active:
                raise StreamLostError('Capture stream became inactive')
            if self.output_stream and not self.output_stream.active:
                raise StreamLostError('Playback stream became inactive')

    def terminate(self):
        """Gracefully release PortAudio streams and driver resources."""
        for stream in (self.input_stream, self.output_stream):
            if stream is not None:
                try:
                    stream.stop()
                    stream.close()
                except Exception:
                    pass
        self.input_stream = None
        self.output_stream = None
        log.info('Native audio engine terminated')
