"""Standalone Gemini Live voice conversation on an Omarchy/PipeWire desktop.

Capture, server events and playback run concurrently. No Omarchy package imports,
local language models, action tools, wake words or conversation files are needed.
"""
from __future__ import annotations

import argparse
import asyncio
import contextlib
import getpass
import logging
import os
import shutil
import signal
import sys
import time
import struct
from pathlib import Path

from core.monitor_echo import MonitorEchoCancellation as EchoCancellation
from audio.plugins.spoken_interrupt import PlaybackReference, SpokenInterruption
from skills import DesktopSkills, SkillError
from core.ipc import JarvisIPCServer
from core.secret_env import sanitized_subprocess_env
from core.speech_turn import SpeechTurnGate, SileroSpeechDetector, GateFrame
from core.stable_recovery import ConnectionRecovery
from core.connection import connect_live, ToolCallCache, ToolCallConflict
from core.config import load_config
from core.harness_config import live_config as harness_config

log = logging.getLogger('gemini_voice')
INPUT_BYTES = 640  # 20 ms, 16 kHz, mono signed little-endian PCM16
OUTPUT_BYTES = 960  # 20 ms, 24 kHz, mono signed little-endian PCM16
SOURCE_REVISION = '2319135'
CAPTURE_QUEUE_FRAMES = 200  # Four seconds; individual sends time out at three.
PLAYBACK_MAX_BYTES = 48000 * 60  # Bounded PCM backlog; 60 seconds at 24 kHz.


class MicrophoneBacklogError(BufferError):
    """Active microphone traffic cannot advance through the transport."""


class PlaybackBacklogError(BufferError):
    """The provider exceeded the bounded playback backlog."""


def audio_environment():
    env = sanitized_subprocess_env()
    for name in ('PIPEWIRE_LATENCY', 'PIPEWIRE_QUANTUM', 'PIPEWIRE_NODE', 'PULSE_SOURCE', 'PULSE_SINK'):
        env.pop(name, None)
    return env


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


async def supervise(*workers):
    """Any worker ending tears down its sibling tasks before returning."""
    tasks = [asyncio.create_task(worker) for worker in workers]
    try:
        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            task.result()
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


class Playback:
    """Bounded PCM playback, with generation fences for interruption races."""

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

    @property
    def busy(self):
        return ((self._writing and self._writing_generation == self.generation)
                or not self.queue.empty() or time.monotonic() < self.playback_until)

    def enqueue(self, data):
        if len(data) % 2:
            raise ValueError('Gemini output contains an incomplete PCM16 sample')
        chunks = (len(data) + OUTPUT_BYTES - 1) // OUTPUT_BYTES
        if (chunks > self.queue.maxsize - self.queue.qsize()
                or self.queued_bytes + len(data) > PLAYBACK_MAX_BYTES):
            # Never block receiving interruption events behind a full queue.
            raise PlaybackBacklogError('Provider audio exceeded bounded playback backlog')
        if data and self.first_enqueued_at is None:
            self.first_enqueued_at = time.monotonic()
        for offset in range(0, len(data), OUTPUT_BYTES):
            chunk = data[offset:offset + OUTPUT_BYTES]
            self.queue.put_nowait((self.generation, chunk))
            self.queued_bytes += len(chunk)
        self._arrival.set()

    def cancel_pending(self):
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
        """Absorb short provider gaps, without waiting for an entire response."""
        deadline = time.monotonic() + .12
        while (generation == self.generation and not self.reply_complete
               and first_bytes + self.queued_bytes < 3840):  # 80 ms at 24 kHz.
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
        """Open playback before a reply so its first chunk avoids process startup."""
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
        while True:
            generation, data = await self.queue.get()
            self.queued_bytes -= len(data)
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
            # Feed a small cushion without dumping a whole reply into PipeWire.
            await asyncio.sleep(max(0.0, self.playback_until - now - 0.08))


class RenewConnection(Exception):
    """The service requested a new transport connection."""


class LiveVoice:
    def __init__(self, player, *, transcripts=False, skills=None, speech_gate=None, barge_in=True):
        self.player = player
        self.transcripts = transcripts
        self.skills = skills
        self.resume_handle = None
        self.send_lock = asyncio.Lock()
        self.tool_tasks = {}
        self.tool_cache = ToolCallCache()
        self.tool_responses = self.tool_cache.responses
        self.connected = False
        self.muted = False
        self.model = ''
        self.microphone_rms = 0.0
        self.microphone_frames_sent = self.provider_audio_bytes = 0
        self.recognized_input_events = self.provider_interruptions = 0
        self._waiting = self._drop_response = self._model_active = False
        self._controls = set()
        self.broadcast = None
        self.gate = speech_gate or SpeechTurnGate(silence_frames=20)
        self.barge_in_enabled = bool(barge_in)
        self.barge_gate = SpokenInterruption(player.reference, detector=self.gate.detector)
        self.local_interruptions = 0
        self._barge_pending = self._barge_turn = False
        self._barge_started_at = None
        self._reply_authorized = self._reply_started = False
        self._last_progress = time.monotonic()
        self.ignored_provider_audio_bytes = 0
        self._needs_turn_reset = False
        self.memory_enabled = False
        self.memory_context = ''
        self._user_text = self._assistant_text = ''
        # HUD polling must not rescan command paths on the audio event loop.
        self.registered_tools = len(getattr(skills, 'declarations', ())) if skills else 0
        self._speech_opened_at = self._speech_closed_at = None
        self.last_reply_after_local_end_ms = None
        self.response_timeouts = 0
        self._capture_queue = None
        self._first_upstream_at = None
        self.first_speech_upload_ms = None
        if skills is not None:
            skills.assistant_status_provider = self.status

    def status(self):
        speaking = self.player.busy
        state = ('connecting' if not self.connected else 'speaking' if speaking else
                 'listening' if self.gate.active and not self.muted else
                 'thinking' if self._waiting else 'idle')
        return {'state': state, 'connection_state': 'listening' if self.connected else 'connecting',
                'muted': self.muted, 'model': self.model, 'active_jobs': len(self.tool_tasks),
                'memory_enabled': self.memory_enabled,
                'registered_tools': self.registered_tools,
                'last_reply_after_local_end_ms': self.last_reply_after_local_end_ms,
                'response_timeouts': self.response_timeouts,
                'speech_pipeline': 'concurrent_capture_send_receive_playback',
                'capture_queue_frames': self._capture_queue.qsize() if self._capture_queue else 0,
                'playback_backlog_ms': round(self.player.queued_bytes / 48),
                'first_speech_upload_ms': self.first_speech_upload_ms,
                'first_audio_chunk_to_write_ms': self.player.first_chunk_write_ms,
                'activity': {'connecting': 'Connecting', 'speaking': 'Speaking',
                             'thinking': 'Thinking', 'listening': 'Listening', 'idle': 'Ready'}[state],
                'audio_backend': 'pipewire-monitor-aec', 'audio_source_revision': SOURCE_REVISION,
                'microphone_rms': self.microphone_rms, 'level_available': self.connected,
                'microphone_frames_sent': self.microphone_frames_sent,
                'provider_audio_bytes': self.provider_audio_bytes,
                'recognized_input_events': self.recognized_input_events,
                'provider_interruptions': self.provider_interruptions,
                'accepted_speech_turns': self.gate.accepted_turns,
                'suppressed_microphone_frames': self.gate.suppressed_frames,
                'ignored_provider_audio_bytes': self.ignored_provider_audio_bytes,
                'input_gate_active': self.gate.active,
                'reply_pending': self._reply_authorized,
                'response_drop_pending': self._drop_response,
                'voice_probability': self.gate.last_probability,
                'unadmitted_voice_peak': self.gate.peak_unadmitted_probability,
                'input_hold_ms': round(max(0, self.gate._hold_until - time.monotonic()) * 1000),
                'turn_protection': 'one_reply_per_speech_turn', 'automatic_barge_in': self.barge_in_enabled,
                'local_interruptions': self.local_interruptions,
                'interruption_pending': self._barge_pending,
                'echo_rejected_frames': self.barge_gate.rejected_echo_frames,
                'standby': False, 'vision_mode': 'off', 'skills_enabled': self.skills is not None}

    def interrupt(self):
        self._barge_pending = self._barge_turn = False
        self.barge_gate.reset()
        suppress_remaining = self._waiting or self._model_active
        process = self.player.cancel_pending()
        self._drop_response = suppress_remaining
        self._waiting = False
        self._reply_authorized = self._reply_started = False
        self._last_progress = time.monotonic()
        self._user_text = self._assistant_text = ''
        if suppress_remaining:
            self._needs_turn_reset = True
            self.connected = False
        self.gate.reset(hold_until=time.monotonic() + self.gate.tail_seconds)
        self._stop_playback_process(process)

    def _stop_playback_process(self, process):
        task = asyncio.create_task(stop_process(process))
        self._controls.add(task)
        def finished(done):
            self._controls.discard(done)
            if not done.cancelled() and done.exception() is not None:
                log.warning('Playback cleanup failed: %s', type(done.exception()).__name__)
        task.add_done_callback(finished)

    def _accept_interruption(self):
        """Cut local sound now; drain the old provider turn before new output."""
        # A thinking-only turn may never produce an interrupted/complete pair.
        # Waiting for that nonexistent acknowledgement discarded the new reply.
        self._barge_pending = bool(self._model_active or self._reply_started)
        self._barge_turn = True
        self._barge_started_at = time.monotonic()
        self._stop_playback_process(self.player.cancel_pending())
        self._reply_authorized = self._waiting = True
        self._reply_started = self._drop_response = self._model_active = False
        self._user_text = self._assistant_text = ''
        self._last_progress = self._barge_started_at
        self.gate.admit_interruption()
        self.local_interruptions += 1
        log.info('Local spoken interruption accepted count=%d', self.local_interruptions)

    def set_muted(self, muted):
        if self.muted != muted:
            self.muted = muted
            if muted:
                self.microphone_rms = 0.0
                self.interrupt()
        return self.muted

    async def publish_status(self):
        while True:
            if callable(self.broadcast):
                self.broadcast(self.status())
            await asyncio.sleep(.1)

    async def _capture_audio(self, reader, queue):
        """Capture and detect speech independently of websocket backpressure."""
        activity_open = False
        try:
            while True:
                try:
                    chunk = await reader.readexactly(INPUT_BYTES)
                except asyncio.IncompleteReadError as error:
                    raise EOFError('Microphone stream ended') from error
                samples = struct.unpack('<320h', chunk)
                self.microphone_rms = 0.0 if self.muted else (sum(x*x for x in samples) / 320) ** .5 / 32768
                now = time.monotonic()
                occupied = self.player.busy or (self._reply_authorized and not self.gate.active)
                frame = None
                if (self.barge_in_enabled and occupied and not self.muted and not self._drop_response
                        and not self._barge_pending):
                    if self.barge_gate.detector is None and self.gate.detector is not None:
                        self.barge_gate.detector = self.gate.detector
                    frame = self.barge_gate.process(chunk, now)
                    if frame is not None:
                        self._accept_interruption()
                else:
                    self.barge_gate.reset()
                if frame is None:
                    frame = self.gate.process(chunk, now=now,
                        blocked=self.muted or occupied or self._drop_response)
                if frame.opened:
                    if not frame.barge_in:
                        self._barge_pending = self._barge_turn = False
                    self._speech_opened_at = now
                    self._speech_closed_at = None
                    self._reply_authorized = self._waiting = True
                    self._user_text = self._assistant_text = ''
                    self._reply_started = self._drop_response = self._model_active = False
                    self._last_progress = now
                    log.info('Accepted local speech turn id=%d', self.gate.accepted_turns)
                if frame.closed:
                    self._speech_closed_at = now
                    self._last_progress = now
                if frame.opened:
                    activity_open = True
                if not activity_open:
                    # Explicit activity detection needs no idle PCM stream.
                    # Sending silence at 50 Hz filled the queue during stalls.
                    continue
                if not self.gate.active and not frame.closed:
                    frame = GateFrame(bytes(INPUT_BYTES), closed=True)
                try:
                    queue.put_nowait((frame, self.player.generation))
                except asyncio.QueueFull:
                    raise MicrophoneBacklogError('Active microphone backlog exceeded four seconds') from None
                if frame.closed:
                    activity_open = False
        except asyncio.CancelledError:
            raise
        except Exception as error:
            await queue.put(error)

    async def send_audio(self, session, reader):
        from google.genai import types

        queue = asyncio.Queue(maxsize=CAPTURE_QUEUE_FRAMES)
        self._capture_queue = queue
        capture = asyncio.create_task(self._capture_audio(reader, queue), name='jarvis-microphone-capture')
        activity_open = False
        try:
            while True:
                item = await queue.get()
                if isinstance(item, Exception):
                    raise item
                frame, generation = item
                stale = generation != self.player.generation
                chunk = frame.pcm
                async with self.send_lock:
                    blocked = self.muted or self.player.busy or self._drop_response or stale
                    if blocked:
                        chunk = bytes(len(chunk))
                    elif frame.opened:
                        if activity_open:
                            await asyncio.wait_for(session.send_realtime_input(
                                activity_end=types.ActivityEnd()), 3)
                            activity_open = False
                        await asyncio.wait_for(session.send_realtime_input(
                            activity_start=types.ActivityStart()), 3)
                        activity_open = True
                    await asyncio.wait_for(session.send_realtime_input(
                        audio=types.Blob(data=chunk, mime_type='audio/pcm;rate=16000')), 3)
                    self.microphone_frames_sent += len(chunk) // INPUT_BYTES
                    if frame.opened and not blocked:
                        self._first_upstream_at = time.monotonic()
                        self.first_speech_upload_ms = round(
                            (self._first_upstream_at - self._speech_opened_at) * 1000)
                    if activity_open and (frame.closed or blocked):
                        await asyncio.wait_for(session.send_realtime_input(
                            activity_end=types.ActivityEnd()), 3)
                        activity_open = False
        finally:
            capture.cancel()
            await asyncio.gather(capture, return_exceptions=True)
            self._capture_queue = None

    async def monitor_response(self):
        while True:
            await asyncio.sleep(.25)
            if self._needs_turn_reset:
                self._needs_turn_reset = False
                self.resume_handle = None
                self._drop_response = False
                self._reply_authorized = self._reply_started = self._waiting = False
                self.gate.reset(hold_until=time.monotonic() + self.gate.tail_seconds)
                raise ConnectionError('Resetting voice session after manual stop')
            if (self._barge_pending and self._barge_started_at is not None and
                    time.monotonic() - self._barge_started_at > 5):
                self.resume_handle = None
                self._barge_pending = self._barge_turn = False
                raise ConnectionError('Spoken interruption acknowledgement timeout')
            if (self._reply_authorized and not self.gate.active and not self.player.busy
                    and not self.tool_tasks
                    and time.monotonic() - self._last_progress > 20):
                self.response_timeouts += 1
                log.warning('No provider reply within 20 seconds of local turn end; renewing session')
                self.resume_handle = None
                self._reply_authorized = self._reply_started = self._waiting = False
                raise ConnectionError('Provider response timeout')

    async def _send_tool_response(self, session, response):
        async with self.send_lock:
            await asyncio.wait_for(session.send_tool_response(function_responses=response), 5)
        self._last_progress = time.monotonic()
        self.tool_cache.delivered(response.id)

    async def _execute_tool(self, session, call):
        from google.genai import types

        try:
            result = await self.skills.execute(call.name, call.args or {})
            # Existing screen tools return a private capture path plus OCR. Feed
            # that requested frame to Live as well, without starting a camera.
            if isinstance(result, dict) and result.get('status') in ('inspected', 'captured'):
                from core.stable_capabilities import read_visual_frame as _read_visual_frame
                frame = await asyncio.to_thread(_read_visual_frame, result.get('screenshot_path'))
                result['visual_input'] = 'ocr_only'
                if frame:
                    async with self.send_lock:
                        await asyncio.wait_for(session.send_realtime_input(
                            video=types.Blob(data=frame, mime_type=(
                                'image/png' if str(result.get('screenshot_path')).endswith('.png')
                                else 'image/jpeg'))), 3)
                    result['visual_input'] = 'frame_submitted'
            body = {'output': result}
        except SkillError as error:
            body = {'error': str(error)}
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception('Desktop skill failed unexpectedly: %s', call.name)
            body = {'error': 'desktop skill failed unexpectedly'}
        response = types.FunctionResponse(
            id=call.id, name=call.name, response=body)
        self.tool_cache.store(call.id, response)
        await self._send_tool_response(session, response)

    def _tool_done(self, call_id, task):
        if self.tool_tasks.get(call_id) is task:
            self.tool_tasks.pop(call_id, None)
        if not task.cancelled():
            error = task.exception()
            if error:
                log.warning('Could not return desktop skill result: %s', type(error).__name__)

    async def cancel_tools(self):
        tasks = list(self.tool_tasks.values())
        self.tool_tasks.clear()
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        # Keep completed results and uncertain-action tombstones across resume.
        self.tool_cache.disconnect()

    async def handle(self, event, session=None):
        update = event.session_resumption_update
        if update is not None:
            if update.resumable and update.new_handle:
                self.resume_handle = update.new_handle
            elif update.resumable is False:
                self.resume_handle = None
        content = event.server_content
        if content is not None:
            if self._barge_pending:
                self.provider_interruptions += int(bool(content.interrupted))
                if getattr(content, 'turn_complete', False):
                    self._barge_pending = False
                    self._model_active = False
                else:
                    for part in (content.model_turn.parts or []) if content.model_turn else ():
                        if part.inline_data is not None and part.inline_data.data:
                            self.ignored_provider_audio_bytes += len(part.inline_data.data)
                # This event belongs to the cancelled response, not new speech.
                return
            incoming = getattr(content, 'input_transcription', None)
            if incoming is not None and incoming.text:
                self.recognized_input_events += 1
                if self._reply_authorized:
                    self._user_text += incoming.text
                if self._reply_authorized and not self._reply_started:
                    self._waiting = True
            if content.interrupted:
                self.provider_interruptions += 1
                if self._barge_turn:
                    self._barge_pending = not bool(getattr(content, 'turn_complete', False))
                    self._model_active = False
                    return
                log.warning('Provider interrupted a response count=%d', self.provider_interruptions)
                self._waiting = self._drop_response = self._model_active = False
                self._reply_authorized = self._reply_started = False
                self.gate.reset(hold_until=time.monotonic() + self.gate.tail_seconds)
                await self.player.interrupt()
                # Audio in the same interrupted event belongs to the old turn.
                return
            if content.model_turn:
                self._model_active = self._reply_authorized
                for part in content.model_turn.parts or []:
                    blob = part.inline_data
                    if blob is not None and blob.data:
                        self.provider_audio_bytes += len(blob.data)
                        if blob.mime_type not in ('audio/pcm;rate=24000', 'audio/pcm'):
                            raise ValueError('Unexpected Gemini audio output format')
                        self._waiting = False
                        if not self.muted and not self._drop_response and self._reply_authorized:
                            self._barge_turn = False
                            if not self._reply_started:
                                self.player.begin_reply()
                                self.last_reply_after_local_end_ms = (
                                    round((time.monotonic() - self._speech_closed_at) * 1000)
                                    if self._speech_closed_at is not None else None)
                                log.info('First reply audio: after_local_end_ms=%s',
                                         self.last_reply_after_local_end_ms)
                            self._reply_started = True
                            self._last_progress = time.monotonic()
                            self.player.enqueue(blob.data)
                        else:
                            self.ignored_provider_audio_bytes += len(blob.data)
            outgoing = getattr(content, 'output_transcription', None)
            if outgoing is not None and outgoing.text and self._reply_authorized and not self._barge_turn:
                self._assistant_text += outgoing.text
            if getattr(content, 'turn_complete', False) and not event.tool_call and not self.tool_tasks:
                self.player.finish_reply()
                self._drop_response = self._model_active = False
                if self._reply_started or content.model_turn is not None or not self.gate.active:
                    had_reply = self._reply_started or bool(self._assistant_text)
                    self._waiting = False
                    self._reply_authorized = self._reply_started = False
                    self._barge_turn = False
                    if self.memory_enabled and had_reply:
                        self.skills.queue_memory_exchange(self._user_text, self._assistant_text)
                    self._user_text = self._assistant_text = ''
            if self.transcripts:
                for label, value in [('You', content.input_transcription),
                                     ('Gemini', content.output_transcription)]:
                    if value and value.text:
                        print(f'{label}: {value.text}', flush=True)
        if event.go_away is not None:
            raise RenewConnection()
        cancellation = event.tool_call_cancellation
        if cancellation is not None:
            for call_id in cancellation.ids or []:
                task = self.tool_tasks.pop(call_id, None)
                if task is not None:
                    task.cancel()
        tool_call = event.tool_call
        if tool_call is not None:
            if not self._reply_authorized or self.muted or self._drop_response or self._barge_pending:
                log.warning('Ignoring tool request outside an authorized user turn')
                return
            if self.skills is None:
                raise RuntimeError('Gemini requested a desktop skill while skills are disabled')
            if session is None:
                raise RuntimeError('A live session is required to execute desktop skills')
            for call in tool_call.function_calls or []:
                if not call.id or not call.name:
                    raise ValueError('Gemini sent a desktop skill call without an id or name')
                try:
                    claimed = self.tool_cache.claim(call.id, call.name, call.args or {})
                except ToolCallConflict as error:
                    from google.genai import types
                    await self._send_tool_response(session, types.FunctionResponse(
                        id=call.id, name=call.name, response={'error': str(error)}))
                    continue
                if call.id in self.tool_tasks:
                    continue
                if call.id in self.tool_responses:
                    task = asyncio.create_task(
                        self._send_tool_response(session, self.tool_responses[call.id]))
                elif claimed == 'new':
                    task = asyncio.create_task(self._execute_tool(session, call))
                else:
                    from google.genai import types
                    task = asyncio.create_task(self._send_tool_response(session,
                        types.FunctionResponse(id=call.id, name=call.name, response={
                            'error': 'Prior action outcome unknown; inspect real state before retrying.'})))
                self.tool_tasks[call.id] = task
                task.add_done_callback(
                    lambda finished, call_id=call.id: self._tool_done(call_id, finished))

    async def receive(self, session):
        # SDK receive() can end at turn_complete, so re-enter for the next turn.
        try:
            while True:
                received = False
                async for event in session.receive():
                    received = True
                    await self.handle(event, session)
                if not received:
                    raise ConnectionError('Gemini connection closed')
        finally:
            await self.cancel_tools()

    async def send_input_bar(self, session):
        """User-submitted input shares the same single-response budget as speech."""
        from google.genai import types
        while True:
            # Leave submissions queued until the preceding conversation is idle.
            if not self.skills or self._reply_authorized or self.player.busy or self.muted:
                await asyncio.sleep(.1)
                continue
            item = self.skills.test_bar.pop()
            if item is None:
                await asyncio.sleep(.1)
                continue
            parts = []
            if item.get('text'):
                parts.append(types.Part(text=item['text']))
            if item.get('data'):
                parts.append(types.Part.from_bytes(data=item['data'], mime_type=item['mime']))
            if not parts:
                continue
            async with self.send_lock:
                self._reply_authorized = self._waiting = True
                self._speech_opened_at = self._speech_closed_at = None
                self._reply_started = False
                self._user_text = item.get('text', '')
                self._assistant_text = ''
                self._last_progress = time.monotonic()
                await session.send_client_content(
                    turns=types.Content(role='user', parts=parts), turn_complete=True)


def live_config(voice, resume_handle=None, skills=None, *, settings=None, memory_context="", barge_in=None):
    if barge_in is None:
        barge_in = settings.audio.local_barge_in if settings is not None else True
    instruction = 'You are Jarvis, the user’s personal voice assistant. Speak clearly and briefly.'
    config = {
        'response_modalities': ['AUDIO'],
        'system_instruction': instruction,
        'speech_config': {'voice_config': {'prebuilt_voice_config': {'voice_name': voice}}},
        'input_audio_transcription': {},
        'output_audio_transcription': {},
        'realtime_input_config': {
            'automatic_activity_detection': {
                # Local admission already identifies complete protected turns.
                'disabled': True,
            },
            'activity_handling': 'START_OF_ACTIVITY_INTERRUPTS' if barge_in else 'NO_INTERRUPTION',
        },
        'session_resumption': {'handle': resume_handle},
        'context_window_compression': {'sliding_window': {}},
    }
    if skills is not None:
        shared = harness_config(voice, resume_handle, skills, config=settings,
                                memory_context=memory_context)
        config['tools'] = shared['tools']
        config['system_instruction'] = shared['system_instruction']
        config['system_instruction'] += (
            ' Continuous screen/camera streaming is unavailable in this recovery runtime; '
            'use on-demand screen inspection instead. Camera capture requires an explicit request. '
            'Background job status is available through status tools and the HUD; do not promise '
            'unsolicited spoken alerts. Your name is JARVIS; Gemini is your model provider.')
    config['system_instruction'] += (' Only speak in response to the user. Give one concise reply '
                                     'per request, then wait silently. Never fill silence or start '
                                     'a new conversation without a new user request.')
    return config


async def run(args, key):
    from google import genai

    echo = EchoCancellation()
    ipc = None
    voice = None
    skills = None
    capability_task = None
    settings = getattr(args, "settings", None) or load_config()
    try:
        # Failing closed prevents a raw speaker-to-microphone feedback loop.
        await echo.start(args.microphone)
        player = Playback(echo.sink)
        skills = (None if getattr(args, 'no_skills', False) else
                  DesktopSkills(getattr(args, 'skill_dir', None) or None, config=settings, api_key=key))
        voice = LiveVoice(player, transcripts=args.transcripts, skills=skills,
                          barge_in=settings.audio.local_barge_in and not getattr(args, 'no_barge_in', False))
        voice.set_muted(settings.audio.start_muted)
        from core.stable_capabilities import CapabilityServices
        services = CapabilityServices(skills, settings)
        if skills is not None:
            skills.on_vision_mode_change = services.reject_streaming
            capability_task = asyncio.create_task(services.run())
        detector = getattr(args, 'speech_detector', None)
        if detector is not None:
            voice.gate.detector = detector
            voice.barge_gate.detector = detector
        voice.model = args.model
        if not getattr(args, 'no_ipc', False):
            ipc = JarvisIPCServer(
                socket_path=Path(args.socket) if getattr(args, 'socket', None) else None,
                status_provider=voice.status,
                toggle_mute_cb=lambda: voice.set_muted(not voice.muted),
                set_mute_cb=voice.set_muted,
                interrupt_cb=voice.interrupt,
                set_vision_mode_cb=lambda mode: {'status': 'unavailable', 'vision_mode': 'off',
                                                'error': 'Use on-demand screen inspection; continuous streaming is unavailable'},
            )
            await ipc.start()
            voice.broadcast = ipc.broadcast_state
        recovery = ConnectionRecovery(retry_budget=args.retries)
        async with genai.Client(api_key=key).aio as client:
            while True:
                microphone = None
                started = time.monotonic()
                delay = 0.25
                session_opened = False
                attempted_resume = bool(voice.resume_handle)
                try:
                    log.info('Connecting to %s%s', args.model,
                             ' (resuming)' if voice.resume_handle else '')
                    async with connect_live(client,
                        model=args.model,
                        config=live_config(args.voice, voice.resume_handle, skills, settings=settings,
                                           memory_context=await services.context(), barge_in=voice.barge_in_enabled)
                    ) as session:
                        session_opened = True
                        await asyncio.wait_for(player.prepare(), 3)
                        microphone = await asyncio.create_subprocess_exec(
                            'pw-record', '--rate', '16000', '--channels', '1',
                            '--format', 's16', '--latency', '20ms', '--target',
                            echo.source, '-a', '-', stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.DEVNULL, limit=INPUT_BYTES * 10,
                            env=audio_environment())
                        voice.memory_enabled = services.memory_ready
                        voice.connected = True
                        log.info('LIVE — microphone streaming; speak naturally. Ctrl+C stops capture.')
                        await supervise(voice.send_audio(session, microphone.stdout),
                                        voice.receive(session), player.run(), voice.publish_status(),
                                        voice.monitor_response(), voice.send_input_bar(session))
                except RenewConnection:
                    log.info('Gemini requested connection renewal')
                except Exception as error:
                    decision = recovery.decide(error, attempted_resume=attempted_resume,
                                               session_opened=session_opened,
                                               session_seconds=time.monotonic() - started)
                    if decision.fresh_session:
                        voice.resume_handle = None
                        log.warning('Starting a fresh voice session; the previous audio turn will not be replayed')
                    if decision.fatal:
                        raise RuntimeError(f'Voice retry limit/configuration failure (code={decision.code})') from None
                    delay = decision.delay
                    log.warning('Connection ended type=%s code=%s resumed=%s; retry in %.2fs',
                                type(error).__name__, decision.code, attempted_resume, delay)
                finally:
                    voice.connected = False
                    voice._waiting = voice._drop_response = voice._model_active = False
                    voice._reply_authorized = voice._reply_started = False
                    voice._needs_turn_reset = False
                    voice._barge_pending = voice._barge_turn = False
                    voice.barge_gate.reset()
                    voice.gate.reset(hold_until=time.monotonic() + voice.gate.tail_seconds)
                    try:
                        await stop_process(microphone)
                    finally:
                        await player.interrupt()
                await asyncio.sleep(delay)
    finally:
        if capability_task is not None:
            capability_task.cancel()
            await asyncio.gather(capability_task, return_exceptions=True)
        if skills is not None:
            try:
                await skills.close_agent_jobs()
            except Exception as error:
                log.warning('Capability cleanup failed: %s', type(error).__name__)
        if ipc is not None:
            await ipc.close()
        if voice is not None and voice._controls:
            await asyncio.gather(*voice._controls, return_exceptions=True)
        await echo.close()
        log.info('STOPPED — capture closed and private echo-cancellation routes released')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', help='Path to configuration file')
    parser.add_argument('--agent-name', help='Assistant display name')
    parser.add_argument('--model', default=os.getenv('GEMINI_LIVE_MODEL', 'gemini-3.8-live'))
    parser.add_argument('--voice', default='Aoede', help='Gemini prebuilt voice name')
    parser.add_argument('--microphone', help='Physical PipeWire/Pulse source name; default is system microphone')
    parser.add_argument('--retries', type=int, default=5, help='Consecutive failure retry budget')
    parser.add_argument('--transcripts', action='store_true', help='Print transcript fragments to this terminal')
    parser.add_argument('--no-barge-in', action='store_true', help='Keep protected turn-taking without spoken interruption')
    parser.add_argument('--no-skills', action='store_true',
                        help='Explicitly disable desktop skills for speech-only recovery')
    parser.add_argument('--socket', help='Path to the JARVIS status/control socket')
    parser.add_argument('--no-ipc', action='store_true', help='Disable status/control socket')
    parser.add_argument('--list-skills', action='store_true', help='List desktop skills and command availability')
    parser.add_argument('--skill-dir', action='append', metavar='DIR',
                        help='Load dynamic JSON skill manifests from DIR instead of bundled defaults')
    parser.add_argument('--check', action='store_true', help='Check dependencies without opening audio or network')
    args = parser.parse_args()
    args.settings = load_config()
    args.no_skills = args.no_skills or not args.settings.skills.enabled
    if args.retries < 0:
        parser.error('--retries must be nonnegative')
    missing = [name for name in ('pw-record', 'pw-play', 'pactl', 'pw-cli') if shutil.which(name) is None]
    if missing:
        parser.error('Missing desktop audio commands: ' + ', '.join(missing))
    try:
        from google.genai import types
        check_skills = None if args.no_skills else DesktopSkills(args.skill_dir or None, config=args.settings)
        types.LiveConnectConfig.model_validate(live_config(args.voice, skills=check_skills, settings=args.settings))
    except ImportError:
        parser.error('Install the packages in requirements.txt first')
    except SkillError as error:
        parser.error(str(error))
    if args.list_skills:
        if check_skills is None:
            print('Desktop skills are disabled.')
            return 0
        print('Desktop skills: ' + ', '.join(item['name'] for item in check_skills.declarations))
        for command, available in check_skills.availability().items():
            print(f'  {command}: {"available" if available else "missing"}')
        return 0
    if args.check:
        state = 'disabled' if args.no_skills else 'enabled'
        print(f'PASS: audio commands and Gemini SDK configuration are available; skills {state}. No audio/network opened.')
        return 0
    key_names = ['GEMINI_API_KEY', *(f'GEMINI_API_KEY_{index}' for index in range(1, 21))]
    key = next((os.environ[name].strip() for name in key_names if os.environ.get(name, '').strip()), '')
    if not key:
        if not sys.stdin.isatty():
            parser.error('Set GEMINI_API_KEY or run interactively to enter it privately')
        key = getpass.getpass('Gemini API key (hidden, not saved): ').strip()
    if not key:
        parser.error('A Gemini API key is required')
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

    async def start():
        args.speech_detector = await asyncio.to_thread(SileroSpeechDetector)
        loop = asyncio.get_running_loop()
        task = asyncio.current_task()
        loop.add_signal_handler(signal.SIGTERM, task.cancel)
        try:
            await run(args, key)
        finally:
            loop.remove_signal_handler(signal.SIGTERM)

    try:
        asyncio.run(start())
    except (KeyboardInterrupt, asyncio.CancelledError):
        return 0
    except Exception as error:
        log.error('%s', str(error).replace(key, '[redacted]'))
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
