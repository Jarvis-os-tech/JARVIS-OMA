"""Bounded PCM playback with generation fences for interruption races.

Fix 6: Stale-generation chunks are silently discarded, never triggering
PlaybackBacklogError from cancelled generations.
"""
import asyncio
import contextlib
import time

from .speech import PlaybackReference

OUTPUT_BYTES = 960  # 20 ms at 24 kHz mono PCM16
PLAYBACK_MAX_BYTES = 48000 * 60  # 60 seconds


class MicrophoneBacklogError(BufferError):
    """Active microphone traffic cannot advance through the transport."""


class PlaybackBacklogError(BufferError):
    """The provider exceeded the bounded playback backlog."""


async def stop_process(process):
    """Terminate an owned audio process, escalating only if it will not exit."""
    if process is None:
        return
    if process.returncode is None:
        with contextlib.suppress(ProcessLookupError):
            process.terminate()
    if process.stdin is not None:
        process.stdin.close()
    try:
        await asyncio.wait_for(process.wait(), 1)
    except TimeoutError:
        with contextlib.suppress(ProcessLookupError):
            process.kill()
        await process.wait()


def audio_environment():
    """Subprocess environment with PipeWire overrides removed."""
    import os
    env = dict(os.environ)
    for name in ('PIPEWIRE_LATENCY', 'PIPEWIRE_QUANTUM', 'PIPEWIRE_NODE',
                 'PULSE_SOURCE', 'PULSE_SINK'):
        env.pop(name, None)
    return env


class Playback:
    """Bounded PCM playback with generation fences for interruption races."""

    def __init__(self, sink):
        self.sink = sink
        self.queue = asyncio.Queue(maxsize=6000)
        self.queued_bytes = 0
        self.generation = 0
        self.process = None
        self.playback_until = 0.0
        self._writing = False
        self._writing_generation = 0
        self.reference = PlaybackReference()
        self._spawn_lock = asyncio.Lock()
        self.first_write_at = None
        self.first_enqueued_at = None
        self.first_chunk_write_ms = None
        self._arrival = asyncio.Event()
        self.reply_complete = False

    def is_playing(self, tail: float = 0.0) -> bool:
        return ((self._writing and self._writing_generation == self.generation)
                or not self.queue.empty() or time.monotonic() < self.playback_until + tail)

    @property
    def busy(self):
        return self.is_playing(0.0)

    def enqueue(self, data):
        if len(data) % 2:
            raise ValueError('Gemini output contains an incomplete PCM16 sample')
        chunks = (len(data) + OUTPUT_BYTES - 1) // OUTPUT_BYTES
        if (chunks > self.queue.maxsize - self.queue.qsize()
                or self.queued_bytes + len(data) > PLAYBACK_MAX_BYTES):
            raise PlaybackBacklogError('Provider audio exceeded bounded playback backlog')
        if data and self.first_enqueued_at is None:
            self.first_enqueued_at = time.monotonic()
        for offset in range(0, len(data), OUTPUT_BYTES):
            chunk = data[offset:offset + OUTPUT_BYTES]
            self.queue.put_nowait((self.generation, chunk))
            self.queued_bytes += len(chunk)
        self._arrival.set()

    def cancel_pending(self):
        """Advance generation fence, flush queue, return old playback process."""
        self.generation += 1
        self.playback_until = 0.0
        self.begin_reply()
        while not self.queue.empty():
            self.queue.get_nowait()
        self.queued_bytes = 0
        self._arrival.set()
        process, self.process = self.process, None
        return process

    def begin_reply(self):
        self.first_enqueued_at = self.first_write_at = self.first_chunk_write_ms = None
        self.reply_complete = False

    def finish_reply(self):
        self.reply_complete = True
        self._arrival.set()

    async def _prime(self, generation, first_bytes):
        """Absorb short provider gaps without waiting for an entire response."""
        deadline = time.monotonic() + .12
        while (generation == self.generation and not self.reply_complete
               and first_bytes + self.queued_bytes < 3840):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            self._arrival.clear()
            try:
                await asyncio.wait_for(self._arrival.wait(), remaining)
            except TimeoutError:
                break
        return generation == self.generation

    async def interrupt(self):
        process = self.cancel_pending()
        await stop_process(process)

    async def prepare(self):
        """Open playback subprocess before first chunk to avoid startup latency."""
        generation = self.generation
        async with self._spawn_lock:
            if self.process is None:
                process = await asyncio.create_subprocess_exec(
                    'pw-play', '--rate', '24000', '--channels', '1', '--format', 's16',
                    '--latency', '40ms', '--target', self.sink, '-a', '-',
                    stdin=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
                    env=audio_environment())
                if generation != self.generation:
                    await stop_process(process)
                    return False
                self.process = process
            return generation == self.generation

    async def run(self):
        """Main playback loop — Fix 6: stale generations silently discarded."""
        while True:
            generation, data = await self.queue.get()
            self.queued_bytes -= len(data)

            # Fix 6: silently discard chunks from cancelled generations
            if generation != self.generation:
                continue

            self._writing = True
            self._writing_generation = generation
            try:
                if self.first_write_at is None and not await self._prime(generation, len(data)):
                    continue
                if not await self.prepare() or generation != self.generation:
                    continue
                process = self.process
                if process.returncode is not None:
                    raise RuntimeError(f'Audio output process exited (code={process.returncode})')
                try:
                    process.stdin.write(data)
                    self.reference.add(data)
                    await asyncio.wait_for(process.stdin.drain(), 2)
                except TimeoutError as error:
                    # Fix 6: check generation before raising
                    if generation != self.generation:
                        continue
                    raise PlaybackBacklogError('PipeWire playback stopped accepting PCM') from error
                except (BrokenPipeError, ConnectionResetError):
                    if generation != self.generation:
                        continue
                    raise
                if generation != self.generation:
                    continue
                now = time.monotonic()
                if self.first_write_at is None and self.first_enqueued_at is not None:
                    self.first_write_at = now
                    self.first_chunk_write_ms = round((now - self.first_enqueued_at) * 1000)
                self.playback_until = max(self.playback_until, now) + len(data) / 48000
            finally:
                self._writing = False
            await asyncio.sleep(max(0.0, self.playback_until - time.monotonic() - 0.08))
