"""Prioritize fresh microphone frames on the single Live transport writer."""
from __future__ import annotations

import asyncio
from collections import deque
from contextlib import asynccontextmanager
import heapq
import itertools
import time


class SendStalled(ConnectionError):
    """A cancelled transport write requires closing the current session."""


class VideoFrameDropped(Exception):
    """Optional video was rejected before writing; the session is still usable."""


class AudioSendScheduler:
    AUDIO, CONTROL, VIDEO = range(3)

    def __init__(self, *, control_budget=.5, audio_budget=1.0, video_budget=.1):
        self.control_budget = control_budget
        self.audio_budget = audio_budget
        self.video_budget = video_budget
        self._locked = False
        self._waiters = []
        self._sequence = itertools.count()
        self._context = None
        self._failed = asyncio.Event()
        self._audio_waits = deque(maxlen=256)
        self.timeouts = 0
        self._active_generation = 0
        self._owner_task = None
        self._owner_priority = None
        self._owner_generation = None
        self._audio_backlog = 0
        self.video_choke = False
        self.dropped_video_frames = 0
        self.latency_threshold_ms = 20.0

    @property
    def active_generation(self):
        return self._active_generation

    def update_generation(self, generation):
        if type(generation) is not int or generation < self._active_generation:
            raise ValueError('audio generation must be a monotonically increasing integer')
        if generation == self._active_generation:
            return
        self._active_generation = generation
        active = []
        for ticket in self._waiters:
            if ticket[0] == self.VIDEO:
                if not ticket[2].done():
                    ticket[2].set_exception(VideoFrameDropped('Video generation became obsolete'))
                    self.dropped_video_frames += 1
            else:
                active.append(ticket)
        self._waiters = active
        heapq.heapify(self._waiters)
        if (self._owner_priority == self.VIDEO and self._owner_task is not None
                and self._owner_generation < generation):
            # An in-flight websocket send cannot be safely reused after cancel.
            self.fail()
            self._owner_task.cancel()

    def set_audio_backpressure(self, queued_frames):
        self._audio_backlog = max(0, queued_frames) if type(queued_frames) is int else 0

    def should_choke_video(self):
        ordered = sorted(self._audio_waits)
        p95 = ordered[int((len(ordered) - 1) * .95)] if ordered else 0
        self.video_choke = (p95 > self.latency_threshold_ms or self._audio_backlog > 1 or
                            any(priority < self.VIDEO for priority, _, _ in self._waiters))
        return self.video_choke

    def _drop_video(self, reason):
        self.dropped_video_frames += 1
        raise VideoFrameDropped(reason)

    def locked(self):
        return self._locked

    async def acquire(self, priority=CONTROL, generation=None):
        if self._failed.is_set():
            raise SendStalled('Live transport must reconnect before sending')
        generation = self._active_generation if generation is None else generation
        if type(generation) is not int or generation < 0:
            raise ValueError('audio generation must be a nonnegative integer')
        if priority == self.VIDEO:
            if generation != self._active_generation:
                self._drop_video('Video generation became obsolete')
            # Video never joins a queue behind required traffic.
            if self._locked or self._waiters or self.should_choke_video():
                self._drop_video('Video deferred for audio/control backpressure')
        started = time.monotonic()
        if not self._locked and not self._waiters:
            self._locked = True
        else:
            future = asyncio.get_running_loop().create_future()
            ticket = (priority, next(self._sequence), future)
            heapq.heappush(self._waiters, ticket)
            try:
                await future
            except asyncio.CancelledError:
                if not future.cancelled():
                    # The lock was granted just before cancellation.
                    self.release()
                else:
                    if ticket in self._waiters:
                        self._waiters.remove(ticket)
                        heapq.heapify(self._waiters)
                raise
        if self._failed.is_set():
            self.release()
            raise SendStalled('Live transport must reconnect before sending')
        if priority == self.AUDIO:
            self._audio_waits.append((time.monotonic() - started) * 1000)
        self._owner_task = asyncio.current_task()
        self._owner_priority = priority
        self._owner_generation = generation
        return True

    def release(self):
        if not self._locked:
            raise RuntimeError('Send scheduler is not acquired')
        self._locked = False
        self._owner_task = self._owner_priority = self._owner_generation = None
        while self._waiters:
            _, _, future = heapq.heappop(self._waiters)
            if not future.done():
                self._locked = True
                future.set_result(True)
                break

    def fail(self):
        # Set before releasing ownership: queued writers cannot use a socket
        # whose cancelled write may have left delivery or framing uncertain.
        self._failed.set()

    @asynccontextmanager
    async def hold(self, priority=CONTROL, *, budget=None, generation=None):
        await self.acquire(priority, generation)
        try:
            if budget is None:
                budget = {self.AUDIO: self.audio_budget, self.CONTROL: self.control_budget,
                          self.VIDEO: self.video_budget}[priority]
            async with asyncio.timeout(budget):
                yield self
        except TimeoutError as error:
            self.timeouts += 1
            self.fail()
            raise SendStalled('Live transport write exceeded its scheduling budget') from error
        except asyncio.CancelledError:
            self.fail()
            if priority == self.VIDEO and self._owner_generation < self._active_generation:
                raise SendStalled('Video write interrupted by a newer audio generation') from None
            raise
        except Exception:
            self.fail()
            raise
        finally:
            self.release()

    def audio(self, generation=None):
        # Generation fences cancel optional video, never a fresh correction.
        return self.hold(self.AUDIO, budget=self.audio_budget, generation=generation)

    def video(self, generation=None, *, budget=None):
        return self.hold(self.VIDEO, budget=budget, generation=generation)

    async def __aenter__(self):
        context = self.hold()
        await context.__aenter__()
        self._context = context
        return self

    async def __aexit__(self, *args):
        context, self._context = self._context, None
        return await context.__aexit__(*args)

    async def monitor(self):
        await self._failed.wait()
        raise SendStalled('Live transport write stalled; reconnecting')

    def reset(self):
        if self._locked or self._waiters:
            raise RuntimeError('Cannot reset a scheduler with active sends')
        self._failed = asyncio.Event()
        self._audio_backlog = 0
        self.video_choke = False
        self._audio_waits.clear()

    def metrics(self):
        ordered = sorted(self._audio_waits)
        def percentile(fraction):
            return round(ordered[min(len(ordered) - 1, int((len(ordered) - 1) * fraction))], 3) if ordered else 0
        return {
            'audio_send_wait_p50_ms': percentile(.50),
            'audio_send_wait_p95_ms': percentile(.95),
            'audio_send_wait_p99_ms': percentile(.99),
            'network_send_timeouts': self.timeouts,
            'network_send_waiters': len(self._waiters),
            'dropped_video_frames': self.dropped_video_frames,
            'active_generation': self._active_generation,
            'video_choke': self.video_choke,
        }
