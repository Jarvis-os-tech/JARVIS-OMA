"""Downstream audio slicing and buffering for full-duplex Gemini Live responses."""
from __future__ import annotations

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
        """Pad and emit any remaining sub-frame residual with silence."""
        if self.residual:
            padding = self.frame_bytes - len(self.residual)
            self.residual.extend(b'\x00' * padding)
            if self.engine is not None and hasattr(self.engine, 'enqueue_output'):
                generation = getattr(self.engine, 'active_generation', 0)
                self.engine.enqueue_output(generation, bytes(self.residual))
            self.residual.clear()

    def clear(self):
        """Discard the residual buffer (called on barge-in)."""
        self.residual.clear()
