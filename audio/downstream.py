"""Downstream audio slicing and buffering for full-duplex Gemini Live responses."""
from __future__ import annotations

import math
import struct
from typing import Any, Optional


class DownstreamRouter:
    """Slices variable-length Gemini audio blobs into fixed output frames.

    Parameters
    ----------
    engine : Any
        The native engine whose ``c_output_queue`` receives completed frames
        and whose ``active_generation`` tags each frame for barge-in fencing.
    """

    def __init__(self, engine: Any = None):
        self.engine = engine
        self.frame_bytes = getattr(engine, 'output_frame_bytes', 960) if engine is not None else 960
        self.residual: bytearray = bytearray()

    def feed(self, data: bytes):
        """Accumulate *data* and emit as many complete frames as possible."""
        if len(data) % 2:
            raise ValueError('Gemini output contains an incomplete PCM16 sample')
        self.residual.extend(data)
        generation = getattr(self.engine, 'active_generation', 0) if self.engine is not None else 0
        while len(self.residual) >= self.frame_bytes:
            chunk = bytes(self.residual[:self.frame_bytes])
            del self.residual[:self.frame_bytes]
            if self.engine is not None and hasattr(self.engine, 'enqueue_output'):
                self.engine.enqueue_output(generation, chunk)

    def flush(self):
        """Emit the final partial frame with a click-free tail into silence."""
        if self.residual:
            padding = self.frame_bytes - len(self.residual)
            last_sample = int.from_bytes(self.residual[-2:], 'little', signed=True)
            self.residual.extend(b'\x00' * padding)
            # A hard step from a nonzero final sample to zero can click. If
            # the padding is shorter than the fade, taper the final real
            # samples too so even a nearly full frame ends smoothly.
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
                generation = getattr(self.engine, 'active_generation', 0)
                self.engine.enqueue_output(generation, bytes(self.residual))
            self.residual.clear()

    def clear(self):
        """Discard the residual buffer (called on barge-in)."""
        self.residual.clear()
