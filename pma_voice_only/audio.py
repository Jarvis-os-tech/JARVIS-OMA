"""PMA audio primitives extracted unchanged from the collected voice source."""
import array
import asyncio
import contextlib
import math
import time
from collections import deque
METER_SLICE = 0.05

def frame_level(chunk: bytes) -> float:
    """Loudness of one PCM16 frame as 0..1, shaped for an eye not a meter.

    Every fourth sample is enough for a glow and keeps this off the hot path of
    the audio pump. The square root matters: speech RMS sits low in a linear
    scale, so a linear orb barely moves while someone talks normally. The curve
    lifts speech into a range that reads as motion without letting room tone
    look like conversation.
    """
    usable = len(chunk) // 2 * 2
    if usable < 2:
        return 0.0
    samples = array.array("h")
    samples.frombytes(chunk[:usable])
    window = samples[::4] or samples
    rms = math.sqrt(sum(s * s for s in window) / len(window)) / 32768.0
    # Calibrated against tones: silence and room tone land on 0, quiet speech
    # ~0.36, normal ~0.61, loud ~0.87, clipping 1.0. The earlier 1.8 with no
    # gate saturated at normal speech and let room tone twitch the orb.
    value = (rms ** 0.5) * 1.28
    return 0.0 if value < 0.10 else min(1.0, (value - 0.10) / 0.90)


class Speaker:
    """Model audio out, through pw-cat.

    One long-lived process fed PCM16 as it arrives. `interrupt` kills it, which
    is the point: terminating the process drops whatever PipeWire had buffered,
    so a barge-in stops the reply mid-word instead of finishing the sentence
    over the top of the user.
    """

    def __init__(self, rate: int):
        self.rate = rate
        self._proc: asyncio.subprocess.Process | None = None
        # Playback runs on its own task. pw-cat drinks audio at real time while
        # the model sends it far faster, so draining its pipe inline stalled
        # whoever was writing — and that was the single loop reading the
        # websocket. A spoken reply therefore froze event handling, tool calls
        # included, for as long as it took to say it. Queueing hands the wait to
        # a task nobody else is waiting on.
        self._queue: asyncio.Queue[bytes] = asyncio.Queue()
        self._pump: asyncio.Task | None = None
        # When the audio handed over so far will have finished coming out of
        # the speakers. The model sends a reply far faster than it is spoken,
        # so "is the queue empty" is not the question — the question is whether
        # sound is still in the room.
        self._plays_until = 0.0
        # (starts_at, ends_at, loudness) for audio booked and not yet played.
        # The same reasoning as _plays_until, one step further: the meter wants
        # to know how loud she is *right now*, and "right now" is nowhere near
        # the chunk arriving off the socket.
        self._envelope: deque[tuple[float, float, float]] = deque()

    def is_playing(self, tail: float = 0.0) -> bool:
        return time.monotonic() < self._plays_until + tail

    def level_now(self) -> float:
        """How loud she is at this instant, 0..1, on the same scale as the mic.

        Without this the orb has nothing to show while she talks — and the
        microphone gate makes that worse, not better, because it deliberately
        pins the input meter to zero for the whole of every reply. A meter that
        goes flat exactly when the assistant is speaking reads as "it stopped".
        """
        now = time.monotonic()
        while self._envelope and self._envelope[0][1] <= now:
            self._envelope.popleft()
        if self._envelope and self._envelope[0][0] <= now:
            return self._envelope[0][2]
        return 0.0

    async def _ensure(self) -> asyncio.subprocess.Process:
        if self._proc is None or self._proc.returncode is not None:
            self._proc = await asyncio.create_subprocess_exec(
                "pw-cat", "--playback", "--raw",
                "--rate", str(self.rate), "--channels", "1", "--format", "s16", "-",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
        return self._proc

    async def write(self, pcm: bytes) -> None:
        """Hand a chunk to the player. Never waits on playback."""
        if self._pump is None or self._pump.done():
            self._pump = asyncio.create_task(self._pump_loop())
        # PCM16 mono: two bytes a sample. Book the time this will occupy on the
        # way out, so the microphone gate knows when the room goes quiet again.
        seconds = len(pcm) / 2 / self.rate
        starts_at = max(self._plays_until, time.monotonic())
        self._plays_until = starts_at + seconds
        # Book the loudness on the same clock, in slices. One level for a whole
        # delta would make the meter a staircase — deltas arrive in whatever
        # size the server feels like, and half a second of speech is not one
        # amplitude. METER_SLICE is roughly a syllable's worth of detail.
        # Drop what has already been played. level_now() prunes too, but only
        # the microphone loop calls it and that runs only while listening is
        # on — a typed `say` with the mic shut would otherwise book slices that
        # nothing ever collects.
        now = time.monotonic()
        while self._envelope and self._envelope[0][1] <= now:
            self._envelope.popleft()
        step = int(self.rate * METER_SLICE) * 2
        for offset in range(0, len(pcm), max(step, 2)):
            slice_ = pcm[offset:offset + step]
            at = starts_at + (offset / 2 / self.rate)
            self._envelope.append(
                (at, at + len(slice_) / 2 / self.rate, frame_level(slice_)))
        self._queue.put_nowait(pcm)

    async def _pump_loop(self) -> None:
        while True:
            pcm = await self._queue.get()
            try:
                proc = await self._ensure()
                if proc.stdin is None:
                    continue
                proc.stdin.write(pcm)
                await proc.stdin.drain()
            except (BrokenPipeError, ConnectionResetError):
                self._proc = None
            except asyncio.CancelledError:
                raise
            finally:
                self._queue.task_done()

    def _drop_queued(self) -> None:
        """Throw away audio not yet played. Barge-in must not be finished later."""
        self._plays_until = 0.0
        self._envelope.clear()
        while True:
            try:
                self._queue.get_nowait()
            except asyncio.QueueEmpty:
                return
            self._queue.task_done()

    async def interrupt(self) -> None:
        await self.close()

    async def close(self) -> None:
        pump, self._pump = self._pump, None
        if pump is not None and not pump.done():
            pump.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await pump
        self._drop_queued()
        proc, self._proc = self._proc, None
        if proc is None or proc.returncode is not None:
            return
        if proc.stdin is not None:
            try:
                proc.stdin.close()
            except (BrokenPipeError, ConnectionResetError, RuntimeError):
                pass
        await _terminate(proc)


async def _terminate(proc: asyncio.subprocess.Process) -> None:
    """SIGTERM, then SIGKILL if it will not go, then reap."""
    try:
        proc.terminate()
    except ProcessLookupError:
        return
    try:
        await asyncio.wait_for(proc.wait(), timeout=2)
        return
    except (asyncio.TimeoutError, TimeoutError):
        pass
    try:
        proc.kill()
    except ProcessLookupError:
        return
    try:
        await asyncio.wait_for(proc.wait(), timeout=1)
    except (asyncio.TimeoutError, TimeoutError, ProcessLookupError):
        pass

