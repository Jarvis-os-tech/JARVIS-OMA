"""Opt-in native PipeWire companion; no protected engine methods are changed.

The subprocess owns device deadlines. This adapter owns bounded, nonblocking
pipe transport on the asyncio loop and implements the conversation audio API.
"""
from __future__ import annotations

import asyncio
from collections import deque
import json
import logging
import os
from pathlib import Path
import struct
import subprocess
import time

from audio.engine import StreamLostError

log = logging.getLogger('jarvis.audio.native')
MAGIC = 0x3141564A
HEADER = struct.Struct('<IIII')
MAX_PAYLOAD = 32768
AUDIO, FLUSH, MUTE, COMPLETE, STOP = range(1, 6)
CAPTURE, READY, STATS = 101, 102, 103
HELPER = Path(__file__).with_name('native') / 'jarvis-audio'


class CaptureQueue(asyncio.Queue):
    """Expire captured PCM at consumption as well as on arrival."""
    def __init__(self):
        super().__init__(maxsize=8)
        self.expired_frames = 0

    def empty(self):
        # Consumers such as the wake listener drain with empty()/get_nowait().
        # Prune before reporting non-empty, so expired frames cannot break that.
        now = time.monotonic_ns()
        while self._queue and now - self._queue[0][0] > 150_000_000:
            self._queue.popleft()
            self.expired_frames += 1
            self._wakeup_next(self._putters)
        return not self._queue

    def get_nowait(self):
        while True:
            captured_ns, pcm = super().get_nowait()
            if time.monotonic_ns() - captured_ns <= 150_000_000:
                return pcm
            self.expired_frames += 1

    async def get(self):
        while True:
            try:
                return await super().get()
            except asyncio.QueueEmpty:
                continue


class NativeCompanionEngine:
    """Device I/O in a native process, cloud/session orchestration in Python."""
    def __init__(self, loop=None, *, input_rate=16000, output_rate=24000,
                 input_frame_ms=20, output_frame_ms=20,
                 native_cushion_s=0.08, queue_max_seconds=10, helper=HELPER, **kwargs):
        if (input_rate, output_rate, input_frame_ms, output_frame_ms) != (16000, 24000, 20, 20):
            raise ValueError('native audio currently requires 16/24 kHz mono and 20 ms frames')
        if not 0 <= native_cushion_s <= 1 or not 1 <= queue_max_seconds <= 10:
            raise ValueError('native cushion must be 0..1 s and backlog 1..10 s')
        self.loop = loop or asyncio.get_running_loop()
        self.helper = Path(helper)
        self.output_frame_bytes = 960
        self.input_frame_ms = input_frame_ms
        self.output_frame_ms = output_frame_ms
        self.active_generation = 0
        self.muted = self.speaking = False
        self.state = 'idle'
        self.allow_barge_in = False  # Server-confirmed cancellation is the initial policy.
        self.on_barge_in = self.on_state_change = None
        self.async_input_queue = CaptureQueue()
        self.native_cushion_s = native_cushion_s
        self._max_pending = queue_max_seconds * 48000
        self._process = None
        self._pending = deque()
        self._pending_bytes = 0
        self._rx = bytearray()
        self._stderr_tail = bytearray()
        self._failed = None
        self._ready = asyncio.Event()
        self._nodes = None
        self._aec_input_bound = False
        self._rendered = self._starved = self._captured = self._capture_drops = 0
        self._generation_samples = 0
        self._render_baseline = 0
        self._native_queued = 0
        self._native_playing = False
        self._reaping = None
        self.callback_max_ns = 0
        self._last_message = time.monotonic()
        self.input_rms = self.output_rms = 0.0
        self.playback_rebuffers = self.playback_drains = 0
        self.output_underflows = self.output_callback_errors = 0
        self._playback_prebuffer_frames = round(native_cushion_s / .02)

    @property
    def capture_dropped_frames(self):
        return self._capture_drops // 320 + self.async_input_queue.expired_frames

    def _state(self, state):
        if self.state != state:
            self.state = state
            if callable(self.on_state_change):
                self.on_state_change(state)

    def start(self, source, sink):
        if self._process is not None:
            raise RuntimeError('native companion already started')
        if not self.helper.is_file():
            raise RuntimeError('Build native audio first: make -C audio/plugins/native')
        self._failed = None
        self._ready.clear()
        self._nodes = None
        self._rx.clear()
        self._stderr_tail.clear()
        self._last_message = time.monotonic()
        self._generation_samples = self._render_baseline = self._rendered = 0
        self._process = subprocess.Popen(
            [str(self.helper), source, sink, str(round(self.native_cushion_s * 1000))],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            bufsize=0, close_fds=True)
        for stream in (self._process.stdin, self._process.stdout, self._process.stderr):
            os.set_blocking(stream.fileno(), False)
        self.loop.add_reader(self._process.stdout.fileno(), self._read)
        self.loop.add_reader(self._process.stderr.fileno(), self._read_stderr)
        self._command(FLUSH, self.active_generation)
        self._command(MUTE, int(self.muted))

    async def wait_ready(self, source, sink, timeout=8):
        """Verify stream readiness and native graph links, including ownership."""
        async with asyncio.timeout(timeout):
            await self._ready.wait()
            if self._failed:
                raise StreamLostError(self._failed)
            while True:
                if self._failed:
                    raise StreamLostError(self._failed)
                process = await asyncio.create_subprocess_exec(
                    'pw-dump', stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
                try:
                    raw, _ = await asyncio.wait_for(process.communicate(), 2)
                except BaseException:
                    if process.returncode is None:
                        process.kill()
                    await process.wait()
                    raise
                if process.returncode:
                    raise StreamLostError('Cannot read PipeWire graph')
                if graph_ready(json.loads(raw), self._nodes, self._process.pid, source, sink):
                    self._aec_input_bound = True
                    self._state('listening')
                    log.info('Native capture and playback graph links verified')
                    return
                await asyncio.sleep(.1)

    def _error(self, message):
        self._failed = message
        self._ready.set()

    def _read_stderr(self):
        try:
            raw = os.read(self._process.stderr.fileno(), 4096)
            if not raw:
                self.loop.remove_reader(self._process.stderr.fileno())
                return
            self._stderr_tail.extend(raw)
            del self._stderr_tail[:-1024]
            log.warning('Native audio: %s', raw.decode(errors='replace').strip()[:1024])
        except BlockingIOError:
            pass
        except OSError:
            self.loop.remove_reader(self._process.stderr.fileno())

    def _command(self, kind, generation, payload=b''):
        if self._failed:
            raise StreamLostError(self._failed)
        packet = HEADER.pack(MAGIC, kind, generation & 0xffffffff, len(payload)) + payload
        if self._pending_bytes + len(packet) > self._max_pending + 65536:
            self._error('Native audio IPC backlog exceeded its limit')
            raise StreamLostError(self._failed)
        self._pending.append(memoryview(packet))
        self._pending_bytes += len(packet)
        if self._process:
            self.loop.add_writer(self._process.stdin.fileno(), self._write)

    def _write(self):
        try:
            # Bound each loop turn, so packet flushing cannot starve reception.
            for _ in range(16):
                if not self._pending:
                    self.loop.remove_writer(self._process.stdin.fileno())
                    return
                packet = self._pending[0]
                count = os.write(self._process.stdin.fileno(), packet)
                self._pending_bytes -= count
                if count == len(packet):
                    self._pending.popleft()
                else:
                    self._pending[0] = packet[count:]
                    return
        except BlockingIOError:
            return
        except OSError:
            self.loop.remove_writer(self._process.stdin.fileno())
            self._error('Native audio transport closed')

    def _read(self):
        try:
            raw = os.read(self._process.stdout.fileno(), 65536)
            if not raw:
                self.loop.remove_reader(self._process.stdout.fileno())
                self._error('Native audio process ended')
                return
            self._rx.extend(raw)
            while len(self._rx) >= HEADER.size:
                magic, kind, generation, length = HEADER.unpack_from(self._rx)
                if magic != MAGIC or length > MAX_PAYLOAD:
                    raise ValueError('invalid native audio packet')
                if len(self._rx) < HEADER.size + length:
                    break
                payload = bytes(self._rx[HEADER.size:HEADER.size+length])
                del self._rx[:HEADER.size+length]
                self._event(kind, generation, payload)
        except BlockingIOError:
            pass
        except (OSError, ValueError, struct.error) as error:
            self.loop.remove_reader(self._process.stdout.fileno())
            self._error(f'Native audio protocol failure: {type(error).__name__}')

    def _event(self, kind, generation, payload):
        self._last_message = time.monotonic()
        if kind == READY:
            self._nodes = struct.unpack('<II', payload)
            self._ready.set()
        elif kind == CAPTURE:
            if len(payload) != 648:
                raise ValueError('invalid capture size')
            captured_ns = struct.unpack_from('<Q', payload)[0]
            if time.monotonic_ns() - captured_ns > 150_000_000:
                self.async_input_queue.expired_frames += 1
                return
            if self.async_input_queue.full():
                # Evict by base API: expiry-aware get_nowait may already empty it.
                try:
                    asyncio.Queue.get_nowait(self.async_input_queue)
                    self.async_input_queue.expired_frames += 1
                except asyncio.QueueEmpty:
                    pass
            pcm = b'\0' * 640 if self.muted else payload[8:]
            samples = struct.unpack('<320h', pcm)
            self.input_rms = (sum(value * value for value in samples) / 320) ** .5 / 32768
            asyncio.Queue.put_nowait(self.async_input_queue, (captured_ns, pcm))
        elif kind == STATS:
            captured, rendered, starved, drops, max_ns, queued, playing, gen = struct.unpack('<8Q', payload)
            self._captured, self._capture_drops = captured, drops
            if gen == self.active_generation:
                self._rendered = rendered
            self.callback_max_ns = max_ns
            if starved > self._starved:
                self.playback_rebuffers += 1
            self._starved = starved
            self._native_queued, self._native_playing = queued, bool(playing)
            if gen == self.active_generation and self.speaking and (
                    rendered >= self._generation_samples and not queued and not playing):
                self.speaking = False
                self._state('listening')
        else:
            raise ValueError('unknown native event')

    def enqueue_output(self, generation, chunk):
        if generation != self.active_generation or self.muted:
            return
        if len(chunk) != self.output_frame_bytes:
            raise ValueError('native output requires one 20 ms PCM16 frame')
        outstanding = self._generation_samples - self._rendered
        if outstanding * 2 + len(chunk) > self._max_pending:
            self._error('Native playback backlog exceeded its limit')
            raise StreamLostError(self._failed)
        self._command(AUDIO, generation, chunk)
        self._generation_samples += len(chunk) // 2
        self.speaking = True
        self._state('speaking')

    def mark_turn_complete(self):
        self._command(COMPLETE, self.active_generation)

    def mark_turn_started(self):
        pass

    def handle_barge_in(self):
        self.active_generation += 1
        self._rendered = 0
        self._generation_samples = 0
        if self._process and not self._failed:
            self._command(FLUSH, self.active_generation)
        self.speaking = False
        self._state('listening')

    async def stop_speaking(self):
        self.handle_barge_in()

    def set_muted(self, muted):
        self.muted = bool(muted)
        self.handle_barge_in()
        if self._process and not self._failed:
            self._command(MUTE, int(self.muted))
        while not self.async_input_queue.empty():
            asyncio.Queue.get_nowait(self.async_input_queue)

    def set_reconnect_buffering(self, enabled):
        # Never replay seconds of old microphone speech after a network outage.
        while not self.async_input_queue.empty():
            asyncio.Queue.get_nowait(self.async_input_queue)

    async def monitor_health(self):
        while True:
            if self._failed or not self._process or self._process.poll() is not None:
                raise StreamLostError(self._failed or 'Native audio process stopped')
            if time.monotonic() - self._last_message > 2:
                raise StreamLostError('Native audio heartbeat timed out')
            await asyncio.sleep(.1)

    def terminate(self):
        process, self._process = self._process, None
        if process is None:
            return
        self.loop.remove_reader(process.stdout.fileno())
        self.loop.remove_writer(process.stdin.fileno())
        self.loop.remove_reader(process.stderr.fileno())
        process.stdin.close()
        process.stdout.close()
        process.stderr.close()
        # EOF requests native cleanup. Reap off-loop to avoid blocking audio/network.
        def reap():
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        self._reaping = self.loop.run_in_executor(None, reap)
        self._pending.clear()
        self._pending_bytes = 0
        self._aec_input_bound = False
        self.speaking = False
        self._state('idle')

    async def aclose(self):
        self.terminate()
        if self._reaping:
            await asyncio.shield(self._reaping)


def graph_ready(objects, nodes, pid, source, sink):
    """Resolve native node ownership through its PipeWire client, then links."""
    if not nodes:
        return False
    by_id = {item['id']: item for item in objects}
    props = lambda item: item.get('info', {}).get('props', {})
    targets = {props(item).get('node.name'): item['id'] for item in objects
               if item.get('type') == 'PipeWire:Interface:Node'}
    if source not in targets or sink not in targets:
        return False
    for node in nodes:
        item = by_id.get(node, {})
        client = by_id.get(int(props(item).get('client.id', -1)), {})
        owner = props(item).get('application.process.id', props(client).get('application.process.id'))
        if str(owner) != str(pid):
            return False
    links = {(item.get('info', {}).get('output-node-id'), item.get('info', {}).get('input-node-id'))
             for item in objects if item.get('type') == 'PipeWire:Interface:Link'
             and item.get('info', {}).get('state') == 'active'}
    return (targets[source], nodes[0]) in links and (nodes[1], targets[sink]) in links
