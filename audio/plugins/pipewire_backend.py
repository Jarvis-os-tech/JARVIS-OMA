"""Reference pw-record/pw-play transport behind the main JARVIS engine API.

Keeps one bounded capture queue and one paced playback worker. No extra DSP or
local speech gate: Gemini handles interruptions, as in the saved working copy.
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import struct
import time

from audio.engine import StreamLostError
from audio.plugins.native_backend import CaptureQueue
from core.secret_env import sanitized_subprocess_env


async def stop_process(process):
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


async def verify_route(pid, target, *, capture):
    """Confirm the explicit PipeWire link; never silently accept a raw fallback."""
    for _ in range(20):
        proc = await asyncio.create_subprocess_exec(
            'pw-dump', stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
            env=sanitized_subprocess_env())
        try:
            raw, _ = await asyncio.wait_for(proc.communicate(), 2)
        except BaseException:
            await stop_process(proc)
            raise
        items = json.loads(raw)
        clients = {item['id']: (item.get('info') or {}).get('props', {})
                   for item in items if item.get('type', '').endswith(':Client')}
        nodes, streams, links = set(), set(), []
        for item in items:
            props = (item.get('info') or {}).get('props', {})
            if item.get('type', '').endswith(':Node'):
                if props.get('node.name') == target:
                    nodes.add(item['id'])
                owner = props.get('application.process.id',
                                  clients.get(props.get('client.id'), {}).get('application.process.id'))
                if str(owner) == str(pid):
                    streams.add(item['id'])
            elif item.get('type', '').endswith(':Link'):
                links.append(props)
        for link in links:
            out_node, in_node = link.get('link.output.node'), link.get('link.input.node')
            if ((out_node in nodes and in_node in streams) if capture else
                    (out_node in streams and in_node in nodes)):
                return
        await asyncio.sleep(.05)
    raise StreamLostError('PipeWire reference transport did not bind its AEC target')


class PipeWireProcessEngine:
    continuous_capture = True
    # pw-play does not expose hardware render acknowledgements or xrun counts.
    playback_sample_clock = output_underflows = output_callback_errors = None
    playback_rebuffers = playback_drains = None

    def __init__(self, loop=None, *, input_rate=16000, output_rate=24000,
                 input_frame_ms=20, output_frame_ms=20, queue_max_seconds=10, **kwargs):
        if (input_rate, output_rate, input_frame_ms, output_frame_ms) != (16000, 24000, 20, 20):
            raise ValueError('PipeWire transport requires 16/24 kHz and 20 ms frames')
        if type(queue_max_seconds) is not int or not 1 <= queue_max_seconds <= 60:
            raise ValueError('PipeWire playback backlog must be 1..60 seconds')
        self.loop = loop or asyncio.get_running_loop()
        self.input_rate, self.output_rate = input_rate, output_rate
        self.input_frame_ms, self.output_frame_ms = input_frame_ms, output_frame_ms
        self.output_frame_bytes = 960
        self.async_input_queue = CaptureQueue()
        self._playback_queue = asyncio.Queue(maxsize=queue_max_seconds * 50)
        self.active_generation = 0
        self.muted = self.allow_barge_in = False
        self.state = 'idle'
        self.input_rms = self.output_rms = 0.0
        self.voice_rms_threshold = kwargs.get('voice_rms_threshold', 450)
        self.on_state_change = self.on_barge_in = None
        self._capture = self._output = None
        self._tasks, self._stops = [], set()
        self._ready = asyncio.Event()
        self._failed = None
        self._playback_until = 0.0
        self._writing = False
        self._captured = self._dropped = 0
        self._aec_input_bound = False
        self._playback_prebuffer_frames = 4  # Reference's 80 ms pacing cushion.

    @property
    def speaking(self):
        return self._writing or not self._playback_queue.empty() or time.monotonic() < self._playback_until

    @property
    def capture_sample_clock(self):
        return self._captured

    @property
    def capture_dropped_frames(self):
        return self._dropped + self.async_input_queue.expired_frames

    def _state(self, state):
        if self.state != state:
            self.state = state
            if callable(self.on_state_change):
                self.on_state_change(state)

    def _environment(self):
        env = sanitized_subprocess_env()
        for key in ('PIPEWIRE_QUANTUM', 'PIPEWIRE_LATENCY', 'PIPEWIRE_NODE', 'PULSE_SOURCE', 'PULSE_SINK'):
            env.pop(key, None)
        return env

    async def _guard(self, operation):
        try:
            await operation
        except asyncio.CancelledError:
            raise
        except Exception as error:
            self._failed = type(error).__name__
            self._ready.set()

    def start(self, source, sink):
        if self._tasks:
            raise RuntimeError('PipeWire transport is already started')
        self._source, self._sink = source, sink
        self._failed = None
        self._ready.clear()
        self._aec_input_bound = False
        self._tasks = [self.loop.create_task(self._guard(self._capture_audio())),
                       self.loop.create_task(self._guard(self._play_audio()))]

    async def wait_ready(self, source, sink, timeout=8):
        await asyncio.wait_for(self._ready.wait(), timeout)
        if self._failed:
            raise StreamLostError('PipeWire capture failed: ' + self._failed)

    async def _capture_audio(self):
        self._capture = await asyncio.create_subprocess_exec(
            'pw-record', '--rate', '16000', '--channels', '1', '--format', 's16',
            '--latency', '20ms', '--target', self._source, '-a', '-',
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
            limit=6400, env=self._environment())
        await verify_route(self._capture.pid, self._source, capture=True)
        self._aec_input_bound = True
        while True:
            pcm = await self._capture.stdout.readexactly(640)
            self._captured += 320
            pcm = bytes(640) if self.muted else pcm
            samples = struct.unpack('<320h', pcm)
            self.input_rms = (sum(x*x for x in samples) / 320) ** .5 / 32768
            if self.async_input_queue.full():
                asyncio.Queue.get_nowait(self.async_input_queue)
                self._dropped += 1
            asyncio.Queue.put_nowait(self.async_input_queue, (time.monotonic_ns(), pcm))
            self._ready.set()
            if not self.speaking:
                self._state('listening')

    async def _play_audio(self):
        while True:
            if self._playback_queue.empty():
                await asyncio.sleep(max(0, self._playback_until - time.monotonic()))
                if self._playback_queue.empty():
                    self._state('listening')
            generation, data = await self._playback_queue.get()
            if generation != self.active_generation or self.muted:
                continue
            self._writing = True
            try:
                if self._output is None:
                    process = await asyncio.create_subprocess_exec(
                        'pw-play', '--rate', '24000', '--channels', '1', '--format', 's16',
                        '--latency', '40ms', '--target', self._sink, '-a', '-',
                        stdin=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
                        env=self._environment())
                    if generation != self.active_generation or self.muted:
                        await stop_process(process)
                        continue
                    self._output = process
                    await verify_route(process.pid, self._sink, capture=False)
                if generation != self.active_generation or self.muted:
                    continue
                process = self._output
                if process.returncode is not None:
                    raise StreamLostError('PipeWire playback exited')
                process.stdin.write(data)
                try:
                    await process.stdin.drain()
                except (BrokenPipeError, ConnectionResetError):
                    if generation != self.active_generation:
                        continue
                    raise
                now = time.monotonic()
                self._playback_until = max(self._playback_until, now) + len(data) / 48000
                self._state('speaking')
            finally:
                self._writing = False
            await asyncio.sleep(max(0, self._playback_until - time.monotonic() - .08))

    def enqueue_output(self, generation, frame):
        if generation != self.active_generation or self.muted:
            return
        if len(frame) != 960:
            raise ValueError('PipeWire output requires one 20 ms PCM16 frame')
        if self._playback_queue.full():
            raise StreamLostError('PipeWire playback backlog exceeded its limit')
        self._playback_queue.put_nowait((generation, frame))
        self._state('speaking')

    def handle_barge_in(self):
        self.active_generation += 1
        self._playback_until = 0
        while not self._playback_queue.empty():
            self._playback_queue.get_nowait()
        process, self._output = self._output, None
        if process is not None:
            task = self.loop.create_task(stop_process(process))
            self._stops.add(task)
            task.add_done_callback(self._stop_done)
        self._state('listening')

    def _stop_done(self, task):
        self._stops.discard(task)
        if not task.cancelled() and task.exception() is not None:
            self._failed = 'PlaybackCleanupError'

    def set_muted(self, muted):
        if self.muted != bool(muted):
            self.muted = bool(muted)
            self.handle_barge_in()
            self.set_reconnect_buffering(True)

    def set_reconnect_buffering(self, enabled):
        while not self.async_input_queue.empty():
            with contextlib.suppress(asyncio.QueueEmpty):
                self.async_input_queue.get_nowait()

    def mark_turn_started(self):
        pass

    def mark_turn_complete(self):
        pass

    async def stop_speaking(self):
        self.handle_barge_in()

    async def monitor_health(self):
        while True:
            if self._failed:
                raise StreamLostError('PipeWire transport failed: ' + self._failed)
            await asyncio.sleep(.1)

    def terminate(self):
        for task in self._tasks:
            task.cancel()
        for process in (self._capture, self._output):
            if process is not None and process.returncode is None:
                with contextlib.suppress(ProcessLookupError):
                    process.terminate()

    async def aclose(self):
        self.terminate()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
        await stop_process(self._capture)
        await stop_process(self._output)
        if self._stops:
            await asyncio.gather(*self._stops, return_exceptions=True)
        self._capture = self._output = None
        self._writing = False
        self.handle_barge_in()
