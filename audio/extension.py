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

        Return same-length PCM16 bytes to alter the stream, the original bytes
        to pass through, or None to drop the frame. Processing is synchronous
        on the conversation loop; processors must not block or perform I/O.
        """
        return frame

    def process_output_frame(self, frame: bytes) -> bytes | None:
        """Process or inspect a downstream 24 kHz playback PCM frame.

        Return same-length PCM16 bytes to alter the stream, the original bytes
        to pass through, or None to drop the frame.
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
        self.processor_errors = 0
        self.invalid_results = 0

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
        return self._apply_frame(frame, 'process_input_frame')

    def apply_output_frame(self, frame: bytes) -> bytes | None:
        return self._apply_frame(frame, 'process_output_frame')

    def _apply_frame(self, frame: bytes, method: str) -> bytes | None:
        """Keep valid PCM and its timing when a processor fails its contract."""
        current: bytes | None = frame
        # Extensions may register/unregister themselves while processing.
        for _, processor in tuple(self._processors):
            if current is None:
                break
            try:
                result = getattr(processor, method)(current)
            except Exception:
                self.processor_errors += 1
                continue
            if result is not None and (not isinstance(result, bytes) or len(result) != len(frame)):
                self.invalid_results += 1
                continue
            current = result
        return current

    def dispatch_state_change(self, state: str) -> None:
        for hook in tuple(self._hooks):
            try:
                hook.on_state_change(state)
            except Exception:
                continue

    def dispatch_barge_in(self) -> None:
        for hook in tuple(self._hooks):
            try:
                hook.on_barge_in()
            except Exception:
                continue

    def dispatch_turn_started(self) -> None:
        for hook in tuple(self._hooks):
            try:
                hook.on_turn_started()
            except Exception:
                continue

    def dispatch_turn_completed(self) -> None:
        for hook in tuple(self._hooks):
            try:
                hook.on_turn_completed()
            except Exception:
                continue


class ExtendedAudioEngine:
    """Composition around either native backend at the live PCM boundaries.

    The base capture queue is deliberately exposed unchanged: draining stale
    audio and detecting a local wake word must not run cloud-input processors.
    LiveVoice calls process_input_frame immediately before sending a frame;
    DownstreamRouter calls enqueue_output for each complete playback frame.
    """

    def __init__(
        self,
        base_engine: Any = None,
        registry: AudioExtensionRegistry | None = None,
        **engine_kwargs: Any,
    ) -> None:
        self.registry = registry or AudioExtensionRegistry()
        self._engine = base_engine if base_engine is not None else NativeAudioEngine(**engine_kwargs)
        self._on_barge_in = engine_kwargs.get('on_barge_in', getattr(self._engine, 'on_barge_in', None))
        self._on_state_change = engine_kwargs.get('on_state_change', getattr(self._engine, 'on_state_change', None))
        self._turn_active = False
        self._last_barge_generation = None
        # These are the base engine's documented mutable callbacks, not
        # replacements for any locked core method.
        self._engine.on_barge_in = self._dispatch_barge_in
        self._engine.on_state_change = self._dispatch_state_change

    @property
    def base_engine(self) -> Any:
        """The underlying, unmodified device/transport engine."""
        return self._engine

    @property
    def async_input_queue(self):
        return self._engine.async_input_queue

    @property
    def on_barge_in(self) -> Callable[[], None] | None:
        return self._on_barge_in

    @on_barge_in.setter
    def on_barge_in(self, callback: Callable[[], None] | None) -> None:
        self._on_barge_in = callback

    @property
    def on_state_change(self) -> Callable[[str], None] | None:
        return self._on_state_change

    @on_state_change.setter
    def on_state_change(self, callback: Callable[[str], None] | None) -> None:
        self._on_state_change = callback

    @property
    def muted(self) -> bool:
        return self._engine.muted

    @muted.setter
    def muted(self, value: bool) -> None:
        self.set_muted(value)

    @property
    def allow_barge_in(self) -> bool:
        return self._engine.allow_barge_in

    @allow_barge_in.setter
    def allow_barge_in(self, value: bool) -> None:
        self._engine.allow_barge_in = bool(value)

    @property
    def active_generation(self) -> int:
        return self._engine.active_generation

    def _dispatch_state_change(self, state: str) -> None:
        try:
            if callable(self._on_state_change):
                self._on_state_change(state)
        except Exception:
            pass
        self.registry.dispatch_state_change(state)

    def _notify_barge_hooks(self) -> None:
        generation = self._engine.active_generation
        self._turn_active = False
        if generation != self._last_barge_generation:
            self._last_barge_generation = generation
            self.registry.dispatch_barge_in()

    def _dispatch_barge_in(self) -> None:
        try:
            if callable(self._on_barge_in):
                self._on_barge_in()
        except Exception:
            pass
        self._notify_barge_hooks()

    def register_processor(self, processor: AudioFrameProcessor, *, priority: int = 100) -> None:
        """Register an extension processor."""
        self.registry.register_processor(processor, priority=priority)

    def register_hook(self, hook: AudioHook) -> None:
        """Register an extension lifecycle hook."""
        self.registry.register_hook(hook)

    def process_input_frame(self, frame: bytes) -> bytes | None:
        """Process cloud-bound PCM without changing the base capture queue."""
        frame_bytes = (getattr(self._engine, 'input_rate', 16000)
                       * self._engine.input_frame_ms // 1000 * 2)
        if not isinstance(frame, bytes) or len(frame) != frame_bytes:
            return None
        # Muting is authoritative even if an extension synthesizes new PCM.
        if self._engine.muted:
            return bytes(frame_bytes)
        processed = self.registry.apply_input_frame(frame)
        return bytes(frame_bytes) if self._engine.muted else processed

    async def get_processed_input(self) -> bytes:
        """Read next captured frame from async_input_queue with processor pipeline applied."""
        while True:
            raw_frame = await self._engine.async_input_queue.get()
            processed = self.process_input_frame(raw_frame)
            if processed is not None:
                return processed

    def put_processed_output(self, frame: bytes) -> None:
        """Submit one output frame, capturing its generation before processing."""
        generation = self._engine.active_generation
        self.enqueue_output(generation, frame)

    def enqueue_output(self, generation: int, frame: bytes) -> None:
        """Intercept the actual router path without retagging interrupted audio."""
        if generation != self._engine.active_generation or self._engine.muted:
            return
        if not isinstance(frame, bytes) or len(frame) != self._engine.output_frame_bytes:
            raise ValueError('extension output requires one complete PCM16 frame')
        processed = self.registry.apply_output_frame(frame)
        if processed is None or generation != self._engine.active_generation or self._engine.muted:
            return
        self._engine.enqueue_output(generation, processed)

    def handle_barge_in(self) -> None:
        self._engine.handle_barge_in()
        self._notify_barge_hooks()

    def trigger_barge_in(self, notify_orchestrator: bool = True) -> None:
        self.handle_barge_in()
        if notify_orchestrator:
            self._dispatch_barge_in()

    async def stop_speaking(self) -> None:
        await self._engine.stop_speaking()
        self._notify_barge_hooks()

    def set_muted(self, muted: bool):
        result = self._engine.set_muted(muted)
        if muted:
            self._turn_active = False
        return result

    def mark_turn_started(self) -> None:
        if not self._turn_active:
            self._turn_active = True
            self._engine.mark_turn_started()
            self.registry.dispatch_turn_started()

    def mark_turn_complete(self) -> None:
        self._engine.mark_turn_complete()
        if self._turn_active:
            self._turn_active = False
            self.registry.dispatch_turn_completed()

    def __getattr__(self, name: str) -> Any:
        """Forward all other calls directly to the underlying NativeAudioEngine."""
        return getattr(self._engine, name)
