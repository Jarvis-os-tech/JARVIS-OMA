"""Non-invasive extension architecture for JARVIS-OMA audio.

Allows adding new audio features (DSP filters, speech detectors, audio recorders,
telemetry taps, external STT/TTS bridges, sound effects) without modifying or
overriding the locked core voice files (audio/engine.py, audio/downstream.py,
audio/echo_cancel.py).
"""
from __future__ import annotations

import asyncio
from typing import Any, Callable, Protocol, runtime_checkable

from audio.engine import NativeAudioEngine


@runtime_checkable
class AudioFrameProcessor(Protocol):
    """Protocol for audio frame interceptors, filters, or telemetry taps."""

    def process_input_frame(self, frame: bytes) -> bytes | None:
        """Process or inspect an upstream 16 kHz capture PCM frame.

        Return modified bytes to alter the stream, the original bytes to pass through,
        or None to drop the frame.
        """
        return frame

    def process_output_frame(self, frame: bytes) -> bytes | None:
        """Process or inspect a downstream 24 kHz playback PCM frame.

        Return modified bytes to alter the stream, the original bytes to pass through,
        or None to drop the frame.
        """
        return frame


@runtime_checkable
class AudioHook(Protocol):
    """Protocol for event notifications across audio engine lifecycle."""

    def on_state_change(self, state: str) -> None:
        """Called when state transitions (e.g. 'listening', 'speaking', 'ducked', 'barged_in')."""
        pass

    def on_barge_in(self) -> None:
        """Called when acoustic barge-in is triggered."""
        pass

    def on_turn_started(self) -> None:
        """Called when a model turn commences."""
        pass

    def on_turn_completed(self) -> None:
        """Called when a model turn finishes."""
        pass


class AudioExtensionRegistry:
    """Registry managing dynamic frame processors and lifecycle hooks."""

    def __init__(self) -> None:
        self._processors: list[tuple[int, AudioFrameProcessor]] = []
        self._hooks: list[AudioHook] = []

    def register_processor(self, processor: AudioFrameProcessor, *, priority: int = 100) -> None:
        """Register a frame processor with priority (lower number runs earlier)."""
        self._processors.append((priority, processor))
        self._processors.sort(key=lambda item: item[0])

    def unregister_processor(self, processor: AudioFrameProcessor) -> bool:
        """Unregister a frame processor."""
        initial_len = len(self._processors)
        self._processors = [p for p in self._processors if p[1] is not processor]
        return len(self._processors) < initial_len

    def register_hook(self, hook: AudioHook) -> None:
        """Register a lifecycle event hook."""
        if hook not in self._hooks:
            self._hooks.append(hook)

    def unregister_hook(self, hook: AudioHook) -> bool:
        """Unregister a lifecycle event hook."""
        if hook in self._hooks:
            self._hooks.remove(hook)
            return True
        return False

    def clear(self) -> None:
        """Clear all registered processors and hooks."""
        self._processors.clear()
        self._hooks.clear()

    @property
    def processors(self) -> list[AudioFrameProcessor]:
        return [p[1] for p in self._processors]

    @property
    def hooks(self) -> list[AudioHook]:
        return list(self._hooks)

    def apply_input_frame(self, frame: bytes) -> bytes | None:
        current: bytes | None = frame
        for _, processor in self._processors:
            if current is None:
                break
            try:
                current = processor.process_input_frame(current)
            except Exception:
                # Extension failures must never crash audio pipeline
                continue
        return current

    def apply_output_frame(self, frame: bytes) -> bytes | None:
        current: bytes | None = frame
        for _, processor in self._processors:
            if current is None:
                break
            try:
                current = processor.process_output_frame(current)
            except Exception:
                continue
        return current

    def dispatch_state_change(self, state: str) -> None:
        for hook in self._hooks:
            try:
                hook.on_state_change(state)
            except Exception:
                continue

    def dispatch_barge_in(self) -> None:
        for hook in self._hooks:
            try:
                hook.on_barge_in()
            except Exception:
                continue

    def dispatch_turn_started(self) -> None:
        for hook in self._hooks:
            try:
                hook.on_turn_started()
            except Exception:
                continue

    def dispatch_turn_completed(self) -> None:
        for hook in self._hooks:
            try:
                hook.on_turn_completed()
            except Exception:
                continue


class ExtendedAudioEngine:
    """Composition wrapper around NativeAudioEngine providing non-invasive extensibility.

    Leaves NativeAudioEngine completely unmodified while enabling arbitrary
    upstream/downstream DSP filters, taps, and lifecycle hooks.
    """

    def __init__(
        self,
        base_engine: NativeAudioEngine | None = None,
        registry: AudioExtensionRegistry | None = None,
        **engine_kwargs: Any,
    ) -> None:
        self.registry = registry or AudioExtensionRegistry()
        user_on_barge_in = engine_kwargs.pop("on_barge_in", None)
        user_on_state_change = engine_kwargs.pop("on_state_change", None)

        def _combined_barge_in() -> None:
            if user_on_barge_in:
                try:
                    user_on_barge_in()
                except Exception:
                    pass
            self.registry.dispatch_barge_in()

        def _combined_state_change(state: str) -> None:
            if user_on_state_change:
                try:
                    user_on_state_change(state)
                except Exception:
                    pass
            self.registry.dispatch_state_change(state)

        if base_engine is not None:
            self._engine = base_engine
        else:
            self._engine = NativeAudioEngine(
                on_barge_in=_combined_barge_in,
                on_state_change=_combined_state_change,
                **engine_kwargs,
            )

    @property
    def base_engine(self) -> NativeAudioEngine:
        """The underlying, unmodified NativeAudioEngine."""
        return self._engine

    def register_processor(self, processor: AudioFrameProcessor, *, priority: int = 100) -> None:
        """Register an extension processor."""
        self.registry.register_processor(processor, priority=priority)

    def register_hook(self, hook: AudioHook) -> None:
        """Register an extension lifecycle hook."""
        self.registry.register_hook(hook)

    async def get_processed_input(self) -> bytes:
        """Read next captured frame from async_input_queue with processor pipeline applied."""
        while True:
            raw_frame = await self._engine.async_input_queue.get()
            processed = self.registry.apply_input_frame(raw_frame)
            if processed is not None:
                return processed

    def put_processed_output(self, frame: bytes) -> None:
        """Process PCM and submit it through the engine's generation-safe API."""
        generation = self._engine.active_generation
        processed = self.registry.apply_output_frame(frame)
        if processed is not None:
            self._engine.enqueue_playback(processed, generation=generation)

    def mark_turn_started(self) -> None:
        self._engine.mark_turn_started()
        self.registry.dispatch_turn_started()

    def mark_turn_complete(self) -> None:
        self._engine.mark_turn_complete()
        self.registry.dispatch_turn_completed()

    def __getattr__(self, name: str) -> Any:
        """Forward all other calls directly to the underlying NativeAudioEngine."""
        return getattr(self._engine, name)
