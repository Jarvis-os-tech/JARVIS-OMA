"""Sovereign Voice Daemon for JARVIS OS.

Full-duplex Gemini Live voice streaming over PipeWire with local speech gating
and hard interruption.
"""
from __future__ import annotations

import argparse
import asyncio
import contextlib
import getpass
import logging
import os
import signal
import struct
import sys
import time
from pathlib import Path

from .config import load as load_config, load_env
from .ipc import ControlServer
from .playback import Playback, stop_process, audio_environment
from .recovery import ConnectionRecovery
from .speech import SpeechTurnGate, SileroSpeechDetector, SpokenInterruption, GateFrame

log = logging.getLogger('jarvis_voice')
INPUT_BYTES = 640  # 20ms at 16kHz mono s16le (320 samples)
CAPTURE_QUEUE_FRAMES = 200


def build_instruction(tools: list | None = None) -> str:
    """Build dynamically grounded system instruction reflecting currently loaded capabilities."""
    active_tools = []
    if tools:
        for t in tools:
            if isinstance(t, dict):
                fns = t.get('function_declarations', [])
                active_tools.extend(fn.get('name') for fn in fns if 'name' in fn)
            elif hasattr(t, 'function_declarations'):
                for fn in t.function_declarations:
                    name = getattr(fn, 'name', None) or (fn.get('name') if isinstance(fn, dict) else '')
                    if name:
                        active_tools.append(name)
            elif isinstance(t, str):
                active_tools.append(t)

    if active_tools:
        tool_status = (
            f"CURRENT ATTACHED OS TOOLS ({len(active_tools)} available): {', '.join(active_tools)}.\n"
            "You CAN and SHOULD invoke these declared functions when the user asks for actions they support."
        )
    else:
        tool_status = (
            "CURRENT OS TOOLS: None attached yet (Foundational Voice Phase).\n"
            "Desktop control and external actuators are currently being integrated step-by-step."
        )

    return (
        "You are JARVIS, the sovereign voice-first AI operating system companion on JARVIS OS.\n"
        "Speak concisely, naturally, and directly.\n\n"
        f"{tool_status}\n\n"
        "GROUNDING & CAPABILITY SELF-AWARENESS RULES:\n"
        "1. Your real-world capabilities are strictly bounded by your declared tools in this session.\n"
        "2. If you have a tool for a requested action, call that tool to execute it.\n"
        "3. If the user asks for a capability or action that is NOT among your declared tools (for example, window manipulation, systemctl services, file editing, or live web search when no matching tool exists), be completely truthful: state clearly that this specific capability is not yet connected to your session.\n"
        "4. NEVER hallucinate or pretend an action succeeded on the computer without a successful tool invocation.\n"
        "5. Speak only in response to the user. Give one concise reply per turn, then wait silently."
    )


def live_config(voice: str = 'Aoede', resume_handle: str | None = None, barge_in: bool = True, tools: list | None = None) -> dict:
    config = {
        'response_modalities': ['AUDIO'],
        'system_instruction': build_instruction(tools),
        'speech_config': {'voice_config': {'prebuilt_voice_config': {'voice_name': voice}}},
        'input_audio_transcription': {},
        'output_audio_transcription': {},
        'realtime_input_config': {
            'automatic_activity_detection': {'disabled': True},
            'activity_handling': 'START_OF_ACTIVITY_INTERRUPTS' if barge_in else 'NO_INTERRUPTION',
        },
    }
    if resume_handle:
        config['session_resumption'] = {'handle': resume_handle}
    if tools:
        config['tools'] = tools
    return config


class LiveVoice:
    def __init__(self, player: Playback, *, transcripts: bool = False, speech_gate: SpeechTurnGate | None = None, barge_in: bool = True):
        self.player = player
        self.transcripts = transcripts
        self.resume_handle: str | None = None
        self.send_lock = asyncio.Lock()
        self.connected = False
        self.muted = False
        self.model = ''
        self.microphone_rms = 0.0
        self.microphone_frames_sent = 0
        self.provider_audio_bytes = 0
        self.recognized_input_events = 0
        self.provider_interruptions = 0
        self.local_interruptions = 0
        self._waiting = False
        self._drop_response = False
        self._model_active = False
        self._reply_authorized = False
        self._reply_started = False
        self._barge_pending = False
        self._barge_turn = False
        self._barge_started_at: float | None = None
        self._last_progress = time.monotonic()
        self._speech_opened_at: float | None = None
        self._speech_closed_at: float | None = None
        self.broadcast = None
        self.gate = speech_gate or SpeechTurnGate(silence_frames=20)
        self.barge_in_enabled = bool(barge_in)
        self.barge_gate = SpokenInterruption(player.reference, detector=self.gate.detector)
        self._user_text = ''
        self._assistant_text = ''
        self._capture_queue: asyncio.Queue | None = None

    def status(self) -> dict:
        speaking = self.player.busy
        state = ('connecting' if not self.connected else
                 'speaking' if speaking else
                 'listening' if self.gate.active and not self.muted else
                 'thinking' if self._waiting else 'idle')
        return {
            'state': state,
            'connection_state': 'listening' if self.connected else 'connecting',
            'listening': self.gate.active and not self.muted,
            'connected': self.connected,
            'muted': self.muted,
            'model': self.model,
            'microphone_rms': self.microphone_rms,
            'automatic_barge_in': self.barge_in_enabled,
            'provider_audio_bytes': self.provider_audio_bytes,
            'provider_interruptions': self.provider_interruptions,
            'local_interruptions': self.local_interruptions,
            'accepted_speech_turns': self.gate.accepted_turns,
        }

    def set_muted(self, muted: bool) -> bool:
        if self.muted != muted:
            self.muted = muted
            if muted:
                self.microphone_rms = 0.0
                self.interrupt()
        return self.muted

    def interrupt(self):
        self._barge_pending = self._barge_turn = False
        self.barge_gate.reset()
        suppress = self._waiting or self._model_active
        process = self.player.cancel_pending()
        self._drop_response = suppress
        self._waiting = False
        self._reply_authorized = self._reply_started = False
        self._last_progress = time.monotonic()
        self.gate.reset(hold_until=time.monotonic() + self.gate.tail_seconds)
        if process is not None:
            asyncio.create_task(stop_process(process))

    def _accept_interruption(self):
        self._barge_pending = bool(self._model_active or self._reply_started)
        self._barge_turn = True
        self._barge_started_at = time.monotonic()
        process = self.player.cancel_pending()
        self._reply_authorized = self._waiting = True
        self._reply_started = self._drop_response = self._model_active = False
        self._last_progress = self._barge_started_at
        self.gate.admit_interruption()
        self.local_interruptions += 1
        log.info('Local barge-in accepted (count=%d)', self.local_interruptions)
        if process is not None:
            asyncio.create_task(stop_process(process))

    async def handle(self, event, session=None):
        update = getattr(event, 'session_resumption_update', None)
        if update is not None:
            if getattr(update, 'resumable', False) and getattr(update, 'new_handle', None):
                self.resume_handle = update.new_handle
            elif getattr(update, 'resumable', None) is False:
                self.resume_handle = None

        content = getattr(event, 'server_content', None)
        if content is not None:
            if self._barge_pending:
                if getattr(content, 'turn_complete', False):
                    self._barge_pending = False
                    self._model_active = False
                return

            incoming = getattr(content, 'input_transcription', None)
            if incoming is not None and getattr(incoming, 'text', None):
                self.recognized_input_events += 1
                if self._reply_authorized:
                    self._user_text += incoming.text
                if self._reply_authorized and not self._reply_started:
                    self._waiting = True

            outgoing = getattr(content, 'output_transcription', None)
            if outgoing is not None and getattr(outgoing, 'text', None) and self._reply_authorized and not self._barge_turn:
                self._assistant_text += outgoing.text

            if getattr(content, 'interrupted', False):
                self.provider_interruptions += 1
                self._waiting = self._drop_response = self._model_active = False
                self._reply_authorized = self._reply_started = False
                self.gate.reset(hold_until=time.monotonic() + self.gate.tail_seconds)
                await self.player.interrupt()
                return

            model_turn = getattr(content, 'model_turn', None)
            if model_turn is not None:
                self._model_active = self._reply_authorized
                for part in getattr(model_turn, 'parts', []) or []:
                    blob = getattr(part, 'inline_data', None)
                    if blob is not None and getattr(blob, 'data', None):
                        self.provider_audio_bytes += len(blob.data)
                        self._waiting = False
                        if not self.muted and not self._drop_response and self._reply_authorized:
                            self._barge_turn = False
                            if not self._reply_started:
                                self.player.begin_reply()
                            self._reply_started = True
                            self._last_progress = time.monotonic()
                            self.player.enqueue(blob.data)

            if getattr(content, 'turn_complete', False):
                if self._user_text.strip():
                    log.info('User: "%s"', self._user_text.strip())
                if self._assistant_text.strip():
                    log.info('JARVIS: "%s"', self._assistant_text.strip())
                self._user_text = ''
                self._assistant_text = ''
                self.player.finish_reply()
                self._drop_response = self._model_active = False
                self._waiting = False
                self._reply_authorized = self._reply_started = False
                self._barge_turn = False

    async def _capture_audio(self, reader, queue):
        activity_open = False
        try:
            while True:
                try:
                    chunk = await reader.readexactly(INPUT_BYTES)
                except asyncio.IncompleteReadError:
                    raise EOFError('Microphone stream ended')
                samples = struct.unpack('<320h', chunk)
                self.microphone_rms = 0.0 if self.muted else (sum(x * x for x in samples) / 320) ** 0.5 / 32768
                now = time.monotonic()
                occupied = self.player.busy or (self._reply_authorized and not self.gate.active)
                frame = None
                if (self.barge_in_enabled and occupied and not self.muted and not self._drop_response
                        and not self._barge_pending):
                    frame = self.barge_gate.process(chunk, now)
                    if frame is not None:
                        self._accept_interruption()
                else:
                    self.barge_gate.reset()
                if frame is None:
                    frame = self.gate.process(chunk, now=now, blocked=self.muted or occupied or self._drop_response)
                if frame.opened:
                    self._speech_opened_at = now
                    self._reply_authorized = self._waiting = True
                    self._reply_started = self._drop_response = self._model_active = False
                    self._last_progress = now
                    activity_open = True
                    log.info('Accepted local speech turn id=%d', self.gate.accepted_turns)
                if frame.closed:
                    self._speech_closed_at = now
                    self._last_progress = now
                if not activity_open:
                    continue
                if not self.gate.active and not frame.closed:
                    frame = GateFrame(bytes(INPUT_BYTES), closed=True)
                try:
                    queue.put_nowait((frame, self.player.generation))
                except asyncio.QueueFull:
                    pass
                if frame.closed:
                    activity_open = False
        except asyncio.CancelledError:
            raise

    async def send_audio(self, session, reader):
        from google.genai import types

        queue = asyncio.Queue(maxsize=CAPTURE_QUEUE_FRAMES)
        self._capture_queue = queue
        capture = asyncio.create_task(self._capture_audio(reader, queue))
        activity_open = False
        try:
            while True:
                frame, generation = await queue.get()
                stale = generation != self.player.generation
                chunk = frame.pcm
                async with self.send_lock:
                    blocked = self.muted or self.player.busy or self._drop_response or stale
                    if blocked:
                        chunk = bytes(len(chunk))
                    elif frame.opened:
                        if activity_open:
                            await asyncio.wait_for(session.send_realtime_input(activity_end=types.ActivityEnd()), 3)
                            activity_open = False
                        await asyncio.wait_for(session.send_realtime_input(activity_start=types.ActivityStart()), 3)
                        activity_open = True
                    await asyncio.wait_for(session.send_realtime_input(
                        audio=types.Blob(data=chunk, mime_type='audio/pcm;rate=16000')), 3)
                    self.microphone_frames_sent += len(chunk) // INPUT_BYTES
                    if activity_open and (frame.closed or blocked):
                        await asyncio.wait_for(session.send_realtime_input(activity_end=types.ActivityEnd()), 3)
                        activity_open = False
        finally:
            capture.cancel()
            await asyncio.gather(capture, return_exceptions=True)
            self._capture_queue = None

    async def receive(self, session):
        while True:
            received = False
            async for event in session.receive():
                received = True
                await self.handle(event, session)
            if not received:
                raise ConnectionError('Gemini connection closed')

    async def publish_status(self):
        while True:
            if callable(self.broadcast):
                self.broadcast(self.status())
            await asyncio.sleep(0.1)

    async def monitor_response(self):
        while True:
            await asyncio.sleep(0.25)
            if (self._barge_pending and self._barge_started_at is not None and
                    time.monotonic() - self._barge_started_at > 5):
                self.resume_handle = None
                self._barge_pending = self._barge_turn = False
                raise ConnectionError('Barge-in acknowledgement timeout')
            if (self._reply_authorized and not self.gate.active and not self.player.busy
                    and time.monotonic() - self._last_progress > 20):
                log.warning('No response from provider in 20s, resetting session')
                self.resume_handle = None
                self._reply_authorized = self._reply_started = self._waiting = False
                raise ConnectionError('Provider response timeout')


async def run(args, key: str):
    from google import genai

    config = getattr(args, 'config_obj', None) or load_config()
    model = getattr(args, 'model', None) or config.model
    voice_name = getattr(args, 'voice', None) or config.voice
    device = getattr(args, 'device', None) or config.device

    player = Playback(sink=device or 'default')
    voice = LiveVoice(player, transcripts=getattr(args, 'transcripts', False), barge_in=config.barge_in)
    voice.model = model

    ipc = ControlServer(
        status_provider=voice.status,
        toggle_mute_cb=lambda: voice.set_muted(not voice.muted),
        set_mute_cb=voice.set_muted,
        interrupt_cb=voice.interrupt,
    )
    await ipc.start()
    voice.broadcast = ipc.broadcast_state

    recovery = ConnectionRecovery(retry_budget=getattr(args, 'retries', 5))

    try:
        async with genai.Client(api_key=key).aio as client:
            while True:
                started = time.monotonic()
                session_opened = False
                attempted_resume = bool(voice.resume_handle)
                microphone = None
                try:
                    log.info('Connecting to %s (voice=%s)%s', model, voice_name,
                             ' [resuming]' if voice.resume_handle else '')
                    session_cfg = live_config(voice=voice_name, resume_handle=voice.resume_handle, barge_in=voice.barge_in_enabled)
                    async with client.live.connect(model=model, config=session_cfg) as session:
                        session_opened = True
                        voice.connected = True
                        log.info('Connected to Gemini Live — streaming audio')
                        await player.prepare()

                        mic_args = ['pw-record', '--rate', '16000', '--channels', '1',
                                    '--format', 's16', '--latency', '20ms']
                        if device:
                            mic_args.extend(['--target', device])
                        mic_args.extend(['-a', '-'])

                        microphone = await asyncio.create_subprocess_exec(
                            *mic_args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
                            env=audio_environment())

                        await asyncio.gather(
                            voice.send_audio(session, microphone.stdout),
                            voice.receive(session),
                            player.run(),
                            voice.publish_status(),
                            voice.monitor_response(),
                        )
                except Exception as error:
                    decision = recovery.decide(
                        error, attempted_resume=attempted_resume,
                        session_opened=session_opened, session_seconds=time.monotonic() - started)
                    if decision.fresh_session:
                        voice.resume_handle = None
                    if decision.fatal:
                        raise RuntimeError(f'Fatal voice error: {error}') from error
                    log.warning('Voice session disconnected (%s), retry in %.2fs', error, decision.delay)
                    await asyncio.sleep(decision.delay)
                finally:
                    voice.connected = False
                    if microphone is not None:
                        await stop_process(microphone)
                    await player.interrupt()
    finally:
        await ipc.close()


def main(args=None):
    load_env()
    key = os.environ.get('GEMINI_API_KEY') or os.environ.get('GOOGLE_API_KEY')
    if not key:
        if not sys.stdin.isatty():
            print('GEMINI_API_KEY is required', file=sys.stderr)
            return 1
        key = getpass.getpass('Gemini API key: ').strip()
        if not key:
            return 1

    logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s %(name)s: %(message)s')

    async def _run():
        await run(args, key)

    try:
        asyncio.run(_run())
        return 0
    except (KeyboardInterrupt, asyncio.CancelledError):
        return 0
    except Exception as e:
        print(f'Error: {e}', file=sys.stderr)
        return 1
