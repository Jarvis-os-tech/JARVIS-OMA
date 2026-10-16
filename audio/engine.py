"""Native real-time audio engine using PortAudio C-bindings via sounddevice.

Replaces the legacy pw-play/pw-record subprocess pipeline with persistent
hardware streams whose Python callbacks run on PortAudio threads under
Python's GIL.  The input path pushes raw microphone bytes into an asyncio
queue; the output path pulls generation-tagged PCM frames from a thread-safe
``queue.SimpleQueue`` so the C callback never touches asyncio internals.
"""
from __future__ import annotations

import asyncio
import collections
import logging
import os
import queue
import subprocess
import threading
import time
from collections.abc import Callable
from typing import Optional

import numpy as np
import sounddevice as sd

log = logging.getLogger('jarvis.audio')



class StreamLostError(Exception):
    """Raised when an underlying PortAudio stream dies or its device vanishes."""


class _CaptureQueue(asyncio.Queue):
    """Keep bytes-compatible consumers while discarding audio past its deadline."""

    def __init__(self, max_age):
        super().__init__(maxsize=200)
        self._max_age = max_age
        self.expired_frames = 0

    def put_frame(self, data, captured_at):
        super().put_nowait((captured_at, data))

    def put_nowait(self, data):
        self.put_frame(data, time.monotonic())

    def get_nowait(self):
        while True:
            captured_at, data = super().get_nowait()
            if time.monotonic() - captured_at <= self._max_age():
                return data
            self.expired_frames += 1

    async def get(self):
        while True:
            try:
                return await super().get()
            except asyncio.QueueEmpty:
                # The last queued frame can expire between wakeup and retrieval.
                continue


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
        playback_latency_ms: int = 60,
        playback_cushion_s: float | None = None,
        input_queue_capacity: int = 50,
        voice_rms_threshold: float = 450.0,
        voice_band_ratio: float = 0.55,
        duck_after_ms: int = 40,
        barge_in_after_ms: int = 300,
        release_after_ms: int = 120,
        duck_gain: float = 0.30,
        fade_ms: int = 10,
        allow_barge_in: bool = True,
        double_talk_ratio: float = 1.8,
        echo_cancellation_ratio: float = 1.0,
        hangover_ms: int = 240,
        preroll_ms: int = 60,
        on_barge_in: Optional[Callable[[], None]] = None,
        on_state_change: Optional[Callable[[str], None]] = None,
    ):
        self.loop = loop or asyncio.get_running_loop()
        self.on_barge_in = on_barge_in
        self.on_state_change = on_state_change

        # Thread-boundary queues ------------------------------------------------
        self._input_queue_capacity = input_queue_capacity
        self.async_input_queue: asyncio.Queue[bytes] = _CaptureQueue(self._capture_max_age)
        self._capture_lock = threading.Lock()
        self._capture_buffer = collections.deque()
        self._capture_drain_scheduled = False
        self._capture_enabled = True
        self._stream_epoch = 0
        self._capture_epoch = 0
        self._capture_status = None
        self._capture_status_count = 0
        self.capture_dropped_frames = 0
        self._capture_drain_batch = 16
        # SimpleQueue is thread-safe without requiring asyncio event-loop access.
        self.c_output_queue: queue.SimpleQueue[tuple[int, bytes]] = queue.SimpleQueue()

        # Audio parameters ------------------------------------------------------
        self.input_rate = input_rate
        self.output_rate = output_rate
        self.input_block_size = input_rate * input_frame_ms // 1000   # 320 samples @ 16kHz
        self.output_block_size = output_rate * output_frame_ms // 1000  # 480 samples @ 24kHz
        self.output_frame_bytes = self.output_block_size * 2  # 960 bytes (16-bit mono)
        self.input_frame_ms = input_frame_ms
        self.output_frame_ms = output_frame_ms
        self.playback_latency_ms = playback_latency_ms
        prebuffer_ms = (playback_latency_ms if playback_cushion_s is None
                        else round(playback_cushion_s * 1000))
        self._playback_prebuffer_frames = min(30, max(1, (prebuffer_ms + output_frame_ms - 1)
                                                        // output_frame_ms))
        self._playback_primed = False
        self._playback_need_fade_in = True
        self.playback_rebuffers = 0
        self.playback_drains = 0
        self.output_underflows = 0
        self.output_callback_errors = 0
        self.playback_recoveries = 0
        self._last_output_status_log_at = 0.0
        self._last_output_enqueue_at = 0.0
        # The first PCM block can arrive with a large consonant transient.
        # A raised-cosine edge avoids a hard slope at either end of the ramp.
        self._edge_fade_samples = max(1, min(self.output_block_size, self.output_rate // 100))
        edge = np.linspace(0.0, np.pi, self._edge_fade_samples, dtype=np.float32)
        self._fade_in_edge = (0.5 - 0.5 * np.cos(edge)).astype(np.float32)
        self._fade_out_edge = self._fade_in_edge[::-1].copy()

        # State & Generation ----------------------------------------------------
        self.active_generation: int = 0
        self.muted: bool = False
        self.speaking: bool = False
        self.state: str = 'listening'  # 'listening' | 'speaking' | 'ducked' | 'barged_in'
        self.allow_barge_in: bool = bool(allow_barge_in)
        self.double_talk_ratio: float = float(double_talk_ratio)
        self.echo_cancellation_ratio: float = float(echo_cancellation_ratio)

        # Isochronous Clock & Jitter Hangover (Browser-style time sync) --------
        self.playback_sample_clock: int = 0
        self.capture_sample_clock: int = 0
        self._recent_output_rms: collections.deque[float] = collections.deque(maxlen=15)
        self._hangover_frames = max(1, hangover_ms // output_frame_ms)
        self._empty_frames_count = 0
        self._turn_complete = False

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
        self._fade_out_audio: bytes | None = None
        self._last_output_sample: np.int16 = np.int16(0)
        self._state_lock = threading.Lock()

        # Precompute vectorized FFT frequency bin mask (300Hz - 3400Hz @ 16kHz)
        freqs = np.fft.rfftfreq(self.input_block_size, d=1.0 / self.input_rate)
        self._vocal_mask = (freqs >= 300.0) & (freqs <= 3400.0)

        self.input_stream: sd.InputStream | None = None
        self.output_stream: sd.OutputStream | None = None

    def mark_turn_complete(self) -> None:
        """Signals that upstream model has finished sending audio chunks for current turn."""
        with self._state_lock:
            self._turn_complete = True

    def mark_turn_started(self) -> None:
        """Signals that a new response turn has started arriving."""
        with self._state_lock:
            self._turn_complete = False
            self._empty_frames_count = 0

    def _get_echo_reference(self) -> float:
        """Return the maximum output RMS over the recent acoustic reverberation window."""
        with self._state_lock:
            if not self._recent_output_rms:
                return 0.0
            return max(self._recent_output_rms)

    def set_reconnect_buffering(self, enabled: bool) -> None:
        """Expands upstream buffer to 200 frames (4.0s) during GoAway handshakes."""
        with self._capture_lock:
            self._input_queue_capacity = 200 if enabled else 50
            while len(self._capture_buffer) > self._input_queue_capacity:
                self._capture_buffer.popleft()
                self.capture_dropped_frames += 1
        while self.async_input_queue.qsize() > self._input_queue_capacity:
            try:
                self.async_input_queue.get_nowait()
            except asyncio.QueueEmpty:
                break

    def _capture_max_age(self):
        return self._input_queue_capacity * self.input_frame_ms / 1000

    def _clear_capture(self, *, enabled=None):
        with self._capture_lock:
            self._capture_epoch += 1
            self._capture_buffer.clear()
            self._capture_status = None
            self._capture_status_count = 0
            if enabled is not None:
                self._capture_enabled = enabled
        while True:
            try:
                self.async_input_queue.get_nowait()
            except asyncio.QueueEmpty:
                break
        self.input_rms = 0.0

    def _set_state(self, new_state: str) -> None:
        with self._state_lock:
            if self.state == new_state:
                return
            self.state = new_state
            cb = getattr(self, 'on_state_change', None)

        if cb:
            try:
                loop = getattr(self, 'loop', None)
                if loop and loop.is_running():
                    loop.call_soon_threadsafe(cb, new_state)
                else:
                    cb(new_state)
            except Exception:
                pass


    # ------------------------------------------------------------------
    # PortAudio callbacks (dedicated audio threads; Python still uses the GIL)
    # ------------------------------------------------------------------

    def _input_callback(self, indata, frames, time_info, status, *, stream_epoch=None):
        """Copy into a bounded producer buffer and coalesce loop notifications."""
        try:
            with self._capture_lock:
                if not self._capture_enabled or (
                        stream_epoch is not None and stream_epoch != self._stream_epoch):
                    return
                self.capture_sample_clock += frames
                raw_bytes = bytes(indata)
                if self.muted:
                    raw_bytes = b'\x00' * len(raw_bytes)
                if status:
                    self._capture_status = status
                    self._capture_status_count += 1
                if len(self._capture_buffer) >= self._input_queue_capacity:
                    self._capture_buffer.popleft()
                    self.capture_dropped_frames += 1
                self._capture_buffer.append((self._capture_epoch, time.monotonic(), raw_bytes))
                if not self._capture_drain_scheduled:
                    self._capture_drain_scheduled = True
                    try:
                        self.loop.call_soon_threadsafe(self._drain_capture)
                    except RuntimeError:
                        self._capture_drain_scheduled = False
                        self._capture_buffer.clear()
        except Exception as e:
            log.debug("Input callback exception: %s", e)

    def _drain_capture(self):
        """Process a bounded batch on the loop; own one notification until empty."""
        with self._capture_lock:
            batch = [self._capture_buffer.popleft()
                     for _ in range(min(self._capture_drain_batch, len(self._capture_buffer)))]
            status, count = self._capture_status, self._capture_status_count
            self._capture_status = None
            self._capture_status_count = 0
        if status:
            log.warning('PortAudio input status: %s (%d callbacks)', status, count)
        try:
            for epoch, captured_at, raw_bytes in batch:
                if epoch != self._capture_epoch or not self._capture_enabled:
                    continue
                if time.monotonic() - captured_at > self._capture_max_age():
                    self.capture_dropped_frames += 1
                    continue
                try:
                    self._safe_enqueue_input(raw_bytes, captured_at=captured_at)
                except Exception:
                    log.warning('Capture frame processing failed', exc_info=True)
        finally:
            with self._capture_lock:
                if self._capture_buffer:
                    self.loop.call_soon(self._drain_capture)
                else:
                    self._capture_drain_scheduled = False

    def _safe_enqueue_input(self, raw_bytes: bytes, *, captured_at=None):
        """Enqueue with oldest-frame eviction to prevent C-thread blocking."""
        capacity = min(self._input_queue_capacity, self.async_input_queue.maxsize or self._input_queue_capacity)
        while self.async_input_queue.qsize() >= capacity:
            try:
                self.async_input_queue.get_nowait()
            except asyncio.QueueEmpty:
                break
        if self.muted:
            raw_bytes = b'\x00' * len(raw_bytes)
        if isinstance(self.async_input_queue, _CaptureQueue):
            self.async_input_queue.put_frame(raw_bytes, time.monotonic() if captured_at is None else captured_at)
        else:
            self.async_input_queue.put_nowait(raw_bytes)
        samples = (np.frombuffer(raw_bytes, dtype=np.int16).astype(np.float32) / 32768.0
                   if len(raw_bytes) % 2 == 0 else np.array([]))
        self.input_rms = min(float(np.sqrt(np.mean(samples * samples))), 1.0) if samples.size else 0.0
        self._update_voice_gate(raw_bytes)

    def _is_voice(self, raw_bytes: bytes) -> bool:
        """Return true when a frame contains sustained speech energy not attributable to echo."""
        samples = np.frombuffer(raw_bytes, dtype=np.int16).astype(np.float32)
        if samples.size < 8:
            return False
        samples -= float(samples.mean())
        rms = float(np.sqrt(np.mean(samples * samples)))
        if rms < self.voice_rms_threshold:
            return False

        # Double-talk and echo gating:
        # If output is actively playing or recently reverberating in the room,
        # ensure mic energy is significantly above the echo reference before
        # considering it as genuine user speech.
        echo_ref = self._get_echo_reference()
        if echo_ref > 0.005:
            # Normalized RMS of mic signal
            mic_normalized_rms = rms / 32768.0
            if mic_normalized_rms <= (echo_ref * self.double_talk_ratio):
                return False

        spectrum = np.abs(np.fft.rfft(samples))
        vocal_energy = float(spectrum[self._vocal_mask].sum())
        total_spec_energy = float(spectrum[1:].sum()) + 1e-9
        return (vocal_energy / total_spec_energy) >= self.voice_band_ratio

    def _update_voice_gate(self, raw_bytes: bytes):
        """Duck short backchannels and flush only sustained user speech."""
        if not self.speaking or not self.allow_barge_in:
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
        try:
            if status:
                # PortAudio reports a device-side dropout separately from an
                # empty network queue. Resume the waveform with a soft edge;
                # increasing the network cushion cannot repair a device stall.
                if getattr(status, 'output_underflow', False):
                    self.output_underflows += 1
                    if self.speaking:
                        self._playback_need_fade_in = True
                        self.playback_recoveries += 1
                now = time.monotonic()
                if now - self._last_output_status_log_at >= 10.0:
                    self._last_output_status_log_at = now
                    self.loop.call_soon_threadsafe(
                        log.warning, 'PortAudio output status: %s (underflows: %d)',
                        status, self.output_underflows,
                    )

            with self._state_lock:
                self.playback_sample_clock += frames

            # Release the current waveform smoothly when the server interrupts
            # a response. An abrupt linear edge is audible during consonants.
            if self._fade_out_pending:
                self._fade_out_pending = False
                ramp_len = min(self._edge_fade_samples, len(outdata))
                tail = (np.frombuffer(self._fade_out_audio, dtype=np.int16)
                        if self._fade_out_audio else np.empty(0, dtype=np.int16))
                self._fade_out_audio = None
                if len(tail) >= ramp_len:
                    ramp = (tail[:ramp_len].astype(np.float32) *
                            self._fade_out_edge[:ramp_len]).astype(np.int16)
                else:
                    ramp = (self._fade_out_edge[:ramp_len] *
                            float(self._last_output_sample)).astype(np.int16)
                if outdata.ndim == 2:
                    outdata[:ramp_len, 0] = ramp
                    outdata[ramp_len:, 0] = 0
                else:
                    outdata[:ramp_len] = ramp
                    outdata[ramp_len:] = 0
                self._last_output_sample = np.int16(0)
                self.output_rms = 0.0
                with self._state_lock:
                    self._recent_output_rms.append(0.0)
                    self.speaking = False
                    self._empty_frames_count = 0
                self._set_state('listening')
                return

            # Wait for a small network cushion before starting or resuming a
            # turn. A completed short turn must still play without waiting for
            # frames that will never arrive.
            if not self._playback_primed:
                queue_depth = self.c_output_queue.qsize()
                if queue_depth < self._playback_prebuffer_frames and not self._turn_complete:
                    outdata.fill(0)
                    self.output_rms = 0.0
                    finished = False
                    with self._state_lock:
                        self._recent_output_rms.append(0.0)
                        if self.speaking and queue_depth == 0:
                            self._empty_frames_count += 1
                            if self._empty_frames_count >= self._hangover_frames:
                                self.speaking = False
                                self._empty_frames_count = 0
                                finished = True
                    if finished:
                        self._set_state('listening')
                    return
                self._playback_primed = True

            chunk = None
            current_gen = self.active_generation
            while True:
                try:
                    gen, candidate = self.c_output_queue.get_nowait()
                    if gen == current_gen:
                        chunk = candidate
                        break
                except queue.Empty:
                    break

            if chunk is None:
                outdata.fill(0)
                if self.speaking:
                    # Even a completed turn can end on a nonzero PCM sample.
                    # Fade that final edge; writing hard zero here made a click
                    # whenever the last model chunk filled an exact frame.
                    fade_len = min(self._edge_fade_samples, frames)
                    fade = (self._fade_out_edge[:fade_len] * float(self._last_output_sample)).astype(np.int16)
                    if outdata.ndim == 2:
                        outdata[:fade_len, 0] = fade
                    else:
                        outdata[:fade_len] = fade
                    if not self._turn_complete:
                        self._playback_primed = False
                        self._playback_need_fade_in = True
                        packet_age_ms = round((time.monotonic() - self._last_output_enqueue_at) * 1000)
                        if packet_age_ms > 2000:
                            # A several-second-old packet can be the tail of
                            # one pre-generated speech batch. Waiting for more
                            # frames is safe, but growing the network cushion
                            # after such a drain only adds delay to later turns.
                            self.playback_drains += 1
                        else:
                            self.playback_rebuffers += 1
                            # Cap actual network-jitter recovery at 600 ms.
                            self._playback_prebuffer_frames = min(
                                30, self._playback_prebuffer_frames + 4)
                            if self.playback_rebuffers == 1 or self.playback_rebuffers % 20 == 0:
                                self.loop.call_soon_threadsafe(
                                    log.warning, 'Playback rebuffered %d time(s); cushion now %d ms; last packet %d ms ago',
                                    self.playback_rebuffers,
                                    self._playback_prebuffer_frames * self.output_frame_ms,
                                    packet_age_ms)
                self._last_output_sample = np.int16(0)
                self.output_rms = 0.0
                finished = False
                with self._state_lock:
                    self._recent_output_rms.append(0.0)
                    if self.speaking:
                        self._empty_frames_count += 1
                        # Time auto-synchronization: Don't flip state immediately on 20ms network jitter!
                        if self._empty_frames_count >= self._hangover_frames or (
                            self._turn_complete and self.c_output_queue.empty()
                        ):
                            self.speaking = False
                            self._turn_complete = False
                            self._empty_frames_count = 0
                            finished = True
                if finished:
                    self._playback_primed = False
                    self._playback_need_fade_in = True
                    self._set_state('listening')
                return

            samples = np.frombuffer(chunk, dtype=np.int16)
            n = min(len(samples), len(outdata))
            with self._state_lock:
                self._empty_frames_count = 0
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

            if self._playback_need_fade_in:
                fade_len = min(self._edge_fade_samples, n)
                samples = samples.copy()
                samples[:fade_len] = (samples[:fade_len].astype(np.float32) *
                                      self._fade_in_edge[:fade_len]).astype(np.int16)
                self._playback_need_fade_in = False

            if outdata.ndim == 2:
                outdata[:n, 0] = samples[:n]
                if n < frames:
                    outdata[n:, 0] = 0
            else:
                outdata[:n] = samples[:n]
                if n < frames:
                    outdata[n:] = 0

            self._last_output_sample = samples[n - 1] if n > 0 else np.int16(0)
            cur_rms = min(float(np.sqrt(np.mean((samples[:n].astype(np.float32) / 32768.0) ** 2))), 1.0)
            self.output_rms = cur_rms
            with self._state_lock:
                self._recent_output_rms.append(cur_rms)
                started = not self.speaking
                self.speaking = True
            if started:
                self._set_state('speaking')
        except Exception as e:
            outdata.fill(0)
            # A callback failure previously inserted a hard zero followed by
            # an un-faded PCM frame. Release the last sample smoothly and
            # re-prime before resuming rather than producing two sharp edges.
            try:
                fade_len = min(self._edge_fade_samples, len(outdata))
                fade = (self._fade_out_edge[:fade_len] *
                        float(self._last_output_sample)).astype(np.int16)
                if outdata.ndim == 2:
                    outdata[:fade_len, 0] = fade
                else:
                    outdata[:fade_len] = fade
            except Exception:
                outdata.fill(0)
            self._last_output_sample = np.int16(0)
            self._playback_primed = False
            self._playback_need_fade_in = True
            self.output_rms = 0.0
            self.playback_recoveries += 1
            self.output_callback_errors += 1
            if self.output_callback_errors == 1 or self.output_callback_errors % 20 == 0:
                self.loop.call_soon_threadsafe(
                    log.warning, 'Output callback failed %d time(s): %s', self.output_callback_errors, e)

    def set_output_gain(self, gain: float):
        """Set playback gain; the callback applies a click-free micro-fade."""
        with self._state_lock:
            self._target_gain = max(0.0, min(1.0, float(gain)))

    def enqueue_output(self, generation: int, chunk: bytes):
        """Queue one PCM frame and mark the persistent stream as speaking."""
        with self._state_lock:
            if generation != self.active_generation or self.muted:
                return
            self._turn_complete = False
            self._empty_frames_count = 0
            started = not self.speaking
            if started:
                self._target_gain = 1.0
                self.speaking = True
            self.c_output_queue.put((generation, chunk))
            self._last_output_enqueue_at = time.monotonic()
        if started:
            self._set_state('speaking')

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

    def _bind_pipewire_streams(self, source_name: str, sink_name: str) -> None:
        """Dynamically bind PortAudio client streams to PipeWire AEC virtual nodes."""
        if not source_name and not sink_name:
            return

        def _binder():
            try:
                time.sleep(0.15)
                if source_name:
                    out = subprocess.check_output(
                        ['pactl', 'list', 'source-outputs'],
                        stderr=subprocess.DEVNULL,
                    ).decode('utf-8', errors='ignore')
                    for block in out.split('Source Output #'):
                        if 'PipeWire ALSA' in block:
                            sid = block.splitlines()[0].strip()
                            subprocess.run(
                                ['pactl', 'move-source-output', sid, source_name],
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL,
                            )
                            log.info('PortAudio capture stream #%s bound to AEC source: %s', sid, source_name)
                            break
                if sink_name:
                    out = subprocess.check_output(
                        ['pactl', 'list', 'sink-inputs'],
                        stderr=subprocess.DEVNULL,
                    ).decode('utf-8', errors='ignore')
                    for block in out.split('Sink Input #'):
                        if 'PipeWire ALSA' in block:
                            sid = block.splitlines()[0].strip()
                            subprocess.run(
                                ['pactl', 'move-sink-input', sid, sink_name],
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL,
                            )
                            log.info('PortAudio playback stream #%s bound to AEC sink: %s', sid, sink_name)
                            break
            except Exception as e:
                log.debug('PipeWire stream binding not applicable or failed: %s', e)

        threading.Thread(target=_binder, name='PipeWireAECBinder', daemon=True).start()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self, source_name: str, sink_name: str):
        """Open persistent real-time streams bound to AEC virtual nodes."""
        if self.input_stream is not None or self.output_stream is not None:
            raise RuntimeError('Audio streams already exist; terminate before restarting')
        self._clear_capture(enabled=True)
        with self._capture_lock:
            self._stream_epoch += 1
            stream_epoch = self._stream_epoch
        if source_name:
            os.environ['PULSE_SOURCE'] = source_name
            os.environ['PIPEWIRE_NODE'] = source_name
        if sink_name:
            os.environ['PULSE_SINK'] = sink_name

        in_id, out_id = self.resolve_aec_devices(source_name, sink_name)

        try:
            self.input_stream = sd.InputStream(
                samplerate=self.input_rate,
                channels=1,
                dtype='int16',
                blocksize=self.input_block_size,
                device=in_id,
                callback=lambda *args: self._input_callback(*args, stream_epoch=stream_epoch),
            )
            self.output_stream = sd.OutputStream(
                samplerate=self.output_rate,
                channels=1,
                dtype='int16',
                blocksize=self.output_block_size,
                latency=self.playback_latency_ms / 1000,
                device=out_id,
                callback=self._output_callback,
            )
            self.input_stream.start()
            self.output_stream.start()
            if not self.input_stream.active:
                raise StreamLostError('Capture stream did not become active')
            if not self.output_stream.active:
                raise StreamLostError('Playback stream did not become active')
            self._set_state('listening')
            self._bind_pipewire_streams(source_name, sink_name)
        except BaseException:
            # Preserve the startup failure while releasing every stream that
            # was successfully constructed, including ones not yet started.
            self.terminate()
            raise
        log.info(
            'Native audio engine started: capture %dHz/%d-sample blocks, '
            'playback %dHz/%d-sample blocks',
            self.input_rate, self.input_block_size,
            self.output_rate, self.output_block_size,
        )

    def handle_barge_in(self):
        """Flush playback without ever stopping the AEC-locked output stream."""
        with self._state_lock:
            previous_generation = self.active_generation
            self.active_generation += 1
            # Preserve the next few PCM samples for a natural waveform fade.
            # Holding a single peak sample creates an audible DC-like pop.
            fade_audio = None
            while True:
                try:
                    generation, chunk = self.c_output_queue.get_nowait()
                except queue.Empty:
                    break
                if fade_audio is None and generation == previous_generation:
                    fade_audio = chunk
            self._fade_out_audio = fade_audio
            self._fade_out_pending = True
            self._target_gain = 1.0
            self._gain = 1.0
            self._voice_frames = 0
            self._empty_frames_count = 0
            self._turn_complete = False
            self._recent_output_rms.clear()
            self.speaking = False
            self._playback_primed = False
            self._playback_need_fade_in = True
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
        with self._capture_lock:
            self.muted = bool(muted)
        self._clear_capture()
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
            if self.input_stream is None:
                raise StreamLostError('Capture stream is missing')
            if not self.input_stream.active:
                raise StreamLostError('Capture stream became inactive')
            if self.output_stream is None:
                raise StreamLostError('Playback stream is missing')
            if not self.output_stream.active:
                raise StreamLostError('Playback stream became inactive')

    def terminate(self):
        """Gracefully release PortAudio streams and driver resources."""
        self._clear_capture(enabled=False)
        with self._capture_lock:
            self._stream_epoch += 1
        streams = (self.input_stream, self.output_stream)
        self.input_stream = None
        self.output_stream = None
        for stream in streams:
            if stream is not None:
                try:
                    stream.stop()
                except Exception:
                    log.warning('Failed to stop audio stream', exc_info=True)
                finally:
                    try:
                        stream.close()
                    except Exception:
                        log.warning('Failed to close audio stream', exc_info=True)
        log.info('Native audio engine terminated')
