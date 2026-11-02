"""Downstream audio slicing, local conversational filler mixing, and ducking for full-duplex Gemini Live responses."""
from __future__ import annotations

import logging
import math
import os
from pathlib import Path
import struct
from typing import Any, Dict, List, Optional

log = logging.getLogger('jarvis.audio.downstream')

# 24 kHz mono PCM16 constants
SAMPLE_RATE = 24000
BYTES_PER_SAMPLE = 2
DEFAULT_FRAME_BYTES = 960  # 20 ms at 24 kHz mono signed PCM16
DEFAULT_DUCKING_WINDOW_MS = 50  # 50 ms ducking transition window
DEFAULT_BUFFER_PRECHARGE = 2  # chunks pre-loaded into RAM to eliminate disk wake latency
DEFAULT_FILLER_DIR = Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local/share')) / 'jarvis-oma/audio/fillers'


class DownstreamRouter:
    """Slices variable-length Gemini audio blobs into fixed output frames,

    with a low-latency local conversational filler track and raised-cosine cross-fader
    to eliminate audio pops and dead-air latency during deep thought states.

    Parameters
    ----------
    engine : Any
        The native engine whose ``c_output_queue`` receives completed frames
        and whose ``active_generation`` tags each frame for barge-in fencing.
    ducking_window_ms : int
        Duration in milliseconds for the raised-cosine ducking crossfade.
    local_buffer_precharge : int
        Number of audio frames pre-buffered in RAM.
    filler_audio_dir : Path | str | None
        Directory containing pre-rendered filler PCM files.
    phrase_definitions : List[dict] | None
        Configured phrase mappings with context, text, file, duration_ms.
    """

    def __init__(
        self,
        engine: Any = None,
        ducking_window_ms: int = DEFAULT_DUCKING_WINDOW_MS,
        local_buffer_precharge: int = DEFAULT_BUFFER_PRECHARGE,
        filler_audio_dir: Optional[Path | str] = None,
        phrase_definitions: Optional[List[dict]] = None,
    ):
        self.engine = engine
        self.frame_bytes = getattr(engine, 'output_frame_bytes', DEFAULT_FRAME_BYTES) if engine is not None else DEFAULT_FRAME_BYTES
        self.residual: bytearray = bytearray()
        self._residual_generation: int | None = None

        # Cross-fader and local filler mixing configuration
        self.ducking_window_ms = ducking_window_ms
        self.local_buffer_precharge = local_buffer_precharge
        self.filler_audio_dir = Path(filler_audio_dir).expanduser() if filler_audio_dir else DEFAULT_FILLER_DIR
        self.phrase_definitions = phrase_definitions or [
            {"text": "humm", "file": "humm_thoughtful.pcm", "duration_ms": 800, "context": "generic_deep_thought"},
            {"text": "wait a sec", "file": "wait_sec_system.pcm", "duration_ms": 1100, "context": "system_mutation"},
            {"text": "let's see", "file": "lets_see_code.pcm", "duration_ms": 950, "context": "filesystem_grep"},
            {"text": "give me a moment", "file": "moment_agent.pcm", "duration_ms": 1400, "context": "sub_agent_spawn"},
        ]

        # RAM-cached filler snippets (zero disk latency)
        self._precharged_fillers: Dict[str, bytes] = {}
        self._load_precharged_fillers()

        # Active filler playback & cross-fading state
        self._active_filler: bytearray = bytearray()
        self._active_filler_generation: int | None = None
        self._is_filler_active: bool = False

    def _generation(self) -> int:
        return getattr(self.engine, 'active_generation', 0) if self.engine is not None else 0

    def _load_precharged_fillers(self) -> None:
        """Pre-charge configured PCM files into RAM cache."""
        for phrase in self.phrase_definitions:
            context = phrase.get("context", "generic_deep_thought")
            filename = phrase.get("file", "")
            filepath = self.filler_audio_dir / filename if filename else None
            pcm_bytes = None
            if filepath and filepath.is_file():
                try:
                    pcm_bytes = filepath.read_bytes()
                    if len(pcm_bytes) % 2 != 0:
                        pcm_bytes = pcm_bytes[:-1]
                except Exception as err:
                    log.warning("Could not precharge filler %s: %s", filepath, err)

            if pcm_bytes is None:
                # Procedural zero-click comfort tone fallback (low-amplitude subtle carrier)
                duration_ms = phrase.get("duration_ms", 800)
                pcm_bytes = self._generate_procedural_filler(duration_ms)

            self._precharged_fillers[context] = pcm_bytes

    def _generate_procedural_filler(self, duration_ms: int) -> bytes:
        """Generate a procedural click-free placeholder filler if disk files are absent."""
        total_samples = int(SAMPLE_RATE * (duration_ms / 1000.0))
        fade_len = min(240, max(1, total_samples // 4))
        buf = bytearray(total_samples * BYTES_PER_SAMPLE)
        for i in range(total_samples):
            # Soft, warm comfort tone at 180Hz with minimal amplitude (<1% FS)
            val = math.sin(2.0 * math.pi * 180.0 * i / SAMPLE_RATE) * 120.0
            if i < fade_len:
                val *= 0.5 * (1.0 - math.cos(math.pi * (i + 1) / fade_len))
            elif i >= total_samples - fade_len:
                remain = total_samples - 1 - i
                val *= 0.5 * (1.0 + math.cos(math.pi * (fade_len - remain) / fade_len))
            struct.pack_into('<h', buf, i * 2, int(round(val)))
        return bytes(buf)

    def trigger_filler(self, context_type: str = "generic_deep_thought", generation: Optional[int] = None) -> bool:
        """Trigger instant playback of a pre-charged conversational filler reflex."""
        gen = generation if generation is not None else self._generation()
        filler_data = self._precharged_fillers.get(context_type) or self._precharged_fillers.get("generic_deep_thought")
        if not filler_data:
            return False

        self._active_filler = bytearray(filler_data)
        self._active_filler_generation = gen
        self._is_filler_active = True

        # Precharge initial frames directly to the engine output queue to eliminate PipeWire wake jitter
        chunks_to_emit = min(self.local_buffer_precharge, len(self._active_filler) // self.frame_bytes)
        for _ in range(chunks_to_emit):
            chunk = bytes(self._active_filler[:self.frame_bytes])
            del self._active_filler[:self.frame_bytes]
            if self.engine is not None and hasattr(self.engine, 'enqueue_output'):
                self.engine.enqueue_output(gen, chunk)

        return True

    def feed(self, data: bytes):
        """Accumulate *data* and emit complete frames, cross-fading active filler if present."""
        if len(data) % 2:
            raise ValueError('Gemini output contains an incomplete PCM16 sample')
        generation = self._generation()
        if self._residual_generation is not None and generation != self._residual_generation:
            # Local barge-in / generation transition
            self.residual.clear()
            self._active_filler.clear()
            self._is_filler_active = False
        self._residual_generation = generation

        incoming = bytearray(data)

        # Cross-fader ducking mixer: smoothly transition from filler to Gemini Live PCM
        if self._is_filler_active and self._active_filler and self._active_filler_generation == generation:
            incoming = self._crossfade_ducking(incoming)

        self.residual.extend(incoming)
        while len(self.residual) >= self.frame_bytes:
            chunk = bytes(self.residual[:self.frame_bytes])
            del self.residual[:self.frame_bytes]
            if self.engine is not None and hasattr(self.engine, 'enqueue_output'):
                self.engine.enqueue_output(generation, chunk)

    def _crossfade_ducking(self, gemini_bytes: bytearray) -> bytearray:
        """Apply Raised-Cosine ducking window to transition from local filler to Gemini voice."""
        ducking_samples = int(SAMPLE_RATE * (self.ducking_window_ms / 1000.0))
        available_gemini_samples = len(gemini_bytes) // BYTES_PER_SAMPLE
        available_filler_samples = len(self._active_filler) // BYTES_PER_SAMPLE

        n_samples = min(ducking_samples, available_gemini_samples, available_filler_samples)
        if n_samples <= 0:
            self._is_filler_active = False
            self._active_filler.clear()
            return gemini_bytes

        # Raised-Cosine crossfade: C1-continuous, constant-amplitude sum = 1.0
        for i in range(n_samples):
            w_out = 0.5 * (1.0 + math.cos(math.pi * (i + 1) / n_samples))
            w_in = 1.0 - w_out

            offset = i * 2
            s_filler = struct.unpack_from('<h', self._active_filler, offset)[0]
            s_gemini = struct.unpack_from('<h', gemini_bytes, offset)[0]

            s_mixed = round(s_filler * w_out + s_gemini * w_in)
            s_clamped = max(-32768, min(32767, s_mixed))
            struct.pack_into('<h', gemini_bytes, offset, s_clamped)

        # Truncate used filler audio and finish ducking phase
        self._is_filler_active = False
        self._active_filler.clear()
        return gemini_bytes

    def flush(self):
        """Emit the final partial frame with a click-free tail into silence."""
        if self._residual_generation != self._generation():
            self.clear()
            return
        if self.residual:
            padding = self.frame_bytes - len(self.residual)
            last_sample = int.from_bytes(self.residual[-2:], 'little', signed=True)
            self.residual.extend(b'\x00' * padding)
            if abs(last_sample) >= 32:
                original_samples = (self.frame_bytes - padding) // 2
                fade_start = min(original_samples, max(0, self.frame_bytes // 2 - 240))
                fade_samples = min(240, self.frame_bytes // 2 - fade_start)
                for index in range(fade_samples):
                    gain = 0.5 + 0.5 * math.cos(math.pi * (index + 1) / fade_samples)
                    sample_index = fade_start + index
                    source = (struct.unpack_from('<h', self.residual, sample_index * 2)[0]
                              if sample_index < original_samples else last_sample)
                    struct.pack_into('<h', self.residual, sample_index * 2,
                                     round(source * gain))
            if self.engine is not None and hasattr(self.engine, 'enqueue_output'):
                self.engine.enqueue_output(self._residual_generation, bytes(self.residual))
            self.clear()

    def clear(self):
        """Discard residual buffer and active filler track (called on barge-in)."""
        self.residual.clear()
        self._residual_generation = None
        self._active_filler.clear()
        self._active_filler_generation = None
        self._is_filler_active = False
