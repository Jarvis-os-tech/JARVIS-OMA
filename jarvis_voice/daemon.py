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
from .playback import Playback, MicrophoneBacklogError, stop_process, audio_environment
from .recovery import ConnectionRecovery
from .speech import SpeechTurnGate, SileroSpeechDetector, SpokenInterruption, GateFrame

log = logging.getLogger('jarvis_voice')
INPUT_BYTES = 640  # 20ms at 16kHz mono s16le (320 samples)
CAPTURE_QUEUE_FRAMES = 200
ECHO_TAIL_SECONDS = 0.35  # Half-duplex holdoff to suppress acoustic room echo


async def supervise(*workers):
    """Stop and await every session worker when any worker exits or fails."""
    tasks = [asyncio.create_task(worker) for worker in workers]
    try:
        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            task.result()
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


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

    inst = (
        "You are JARVIS, the sovereign voice-first AI operating system companion on JARVIS OS.\n"
        "Speak clearly in a warm, relaxed conversational voice. Use natural contractions.\n"
        "Answer the main point first, usually in one or two short sentences; expand when asked.\n"
        "Match the user's language and pace. Ask one brief question if clarification is needed.\n"
        "Avoid repeated greetings, filler, and reading lists or formatting aloud.\n"
        "Be honest that you are an AI if asked; never claim to be human.\n\n"
        f"{tool_status}\n\n"
        "GROUNDING & CAPABILITY SELF-AWARENESS RULES:\n"
        "1. Your real-world capabilities are strictly bounded by your declared tools in this session.\n"
        "2. If you have a tool for a requested action, call that tool to execute it.\n"
        "3. If the user asks for a capability or action that is NOT among your declared tools (for example, window manipulation, systemctl services, file editing, or live web search when no matching tool exists), be completely truthful: state clearly that this specific capability is not yet connected to your session.\n"
        "4. NEVER hallucinate or pretend an action succeeded on the computer without a successful tool invocation.\n"
        "5. Speak only in response to the user. Give one concise reply per turn, then wait silently."
    )
    return inst


def live_config(voice: str = 'Aoede', resume_handle: str | None = None, barge_in: bool = False, tools: list | None = None, skills=None, config=None) -> dict:
    instruction = build_instruction(tools)
    if skills is not None and hasattr(skills, 'memory_context'):
        memory_config = getattr(config, 'memory', None)
        if memory_config is None or memory_config.enabled:
            instruction += (
                '\nJARVIS has persistent memory. Use recall_memory and memory_status before answering '
                'questions about previous conversations or claiming no memory exists. '
                'Conversation text is retained continuously across restarts when continuous_history '
                'is enabled; provider connections do not reset that memory. Only relevant recent data '
                'is included here; search recall_memory for older context. Do not invent memories '
                'or assume that unsaved conversations can be recovered.'
            )
        mem_ctx = skills.memory_context()
        if mem_ctx:
            instruction += f"\n\nActive Memory Context:\n{mem_ctx}"

    cfg = {
        'response_modalities': ['AUDIO'],
        'system_instruction': instruction,
        'speech_config': {'voice_config': {'prebuilt_voice_config': {'voice_name': voice}}},
        'input_audio_transcription': {},
        'output_audio_transcription': {},
        'realtime_input_config': {
            'automatic_activity_detection': {'disabled': True},
            'activity_handling': 'START_OF_ACTIVITY_INTERRUPTS' if barge_in else 'NO_INTERRUPTION',
        },
    }
    if resume_handle:
        cfg['session_resumption'] = {'handle': resume_handle}
    if tools:
        cfg['tools'] = tools
    return cfg


class LiveVoice:
    def __init__(self, player: Playback, *, transcripts: bool = False, speech_gate: SpeechTurnGate | None = None, barge_in: bool = False, greet_on_start: bool = True, skills=None, config=None):
        self.player = player
        self.transcripts = transcripts
        self.resume_handle: str | None = None
        self.send_lock = asyncio.Lock()
        self.connected = False
        self.muted = False
        self.model = ''
        self.greet_on_start = bool(greet_on_start)
        self._greeted = False
        self.skills = skills
        self.config = config
        self._memory_user = ''
        self._memory_assistant = ''
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
        self.response_first_audio_ms: int | None = None
        self.broadcast = None
        self.gate = speech_gate or SpeechTurnGate(silence_frames=20)
        self.barge_in_enabled = bool(barge_in)
        ref = getattr(player, 'reference', None)
        detector = getattr(self.gate, 'detector', None) if self.gate else None
        self.barge_gate = SpokenInterruption(ref, detector=detector) if ref else None
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
            'latency': {
                'speech_end_to_first_audio_ms': self.response_first_audio_ms,
                'first_audio_chunk_to_write_ms': self.player.first_chunk_write_ms,
            },
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
        if self.barge_gate is not None:
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

    async def send_greeting(self, session):
        """Send an initial user turn prompt on session start so JARVIS greets the user out loud."""
        from google.genai import types

        if not self.greet_on_start or self._greeted:
            return
        self._greeted = True
        self._reply_authorized = self._waiting = True
        self._reply_started = self._drop_response = self._model_active = False
        self._last_progress = time.monotonic()
        log.info('Triggering realtime startup greeting...')
        try:
            await asyncio.sleep(0.15)
            await session.send_client_content(
                turns=[types.Content(role='user', parts=[types.Part.from_text(
                    text='You are booting up on JARVIS OS. Greet the user warmly and concisely in one short sentence as JARVIS, and let them know you are online and listening.'
                )])],
                turn_complete=True,
            )
        except Exception as exc:
            log.warning('Failed to send startup greeting: %s', exc)

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
                self._memory_user = (self._memory_user + incoming.text)[-16000:]
                if self._reply_authorized:
                    self._user_text += incoming.text
                if self._reply_authorized and not self._reply_started:
                    self._waiting = True

            outgoing = getattr(content, 'output_transcription', None)
            if outgoing is not None and getattr(outgoing, 'text', None):
                self._memory_assistant = (self._memory_assistant + outgoing.text)[-16000:]
                if self._reply_authorized and not self._barge_turn:
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
                                if self._speech_closed_at is not None:
                                    self.response_first_audio_ms = max(0, round(
                                        (time.monotonic() - self._speech_closed_at) * 1000))
                                self.player.begin_reply()
                            self._reply_started = True
                            self._last_progress = time.monotonic()
                            self.player.enqueue(blob.data)

            if getattr(content, 'turn_complete', False):
                memory_config = getattr(self.config, 'memory', None)
                if self.skills is not None and memory_config and memory_config.enabled and (
                        memory_config.record_sessions or memory_config.auto_capture or
                        memory_config.structured_capture):
                    if hasattr(self.skills, 'queue_memory_exchange'):
                        self.skills.queue_memory_exchange(self._memory_user, self._memory_assistant)
                    self._memory_user = ''
                    self._memory_assistant = ''
                if self._user_text.strip():
                    log.info('User: "%s"', self._user_text.strip())
                if self._assistant_text.strip():
                    log.info('JARVIS: "%s"', self._assistant_text.strip())
                self._user_text = ''
                self._assistant_text = ''
                if hasattr(self.player, 'finish_reply'):
                    self.player.finish_reply()
                self._drop_response = self._model_active = False
                self._waiting = False
                self._reply_authorized = self._reply_started = False
                self._barge_turn = False

    async def _capture_audio(self, reader, queue):
        activity_open = False
        held_frames = 0
        try:
            while True:
                try:
                    chunk = await reader.readexactly(INPUT_BYTES)
                except asyncio.IncompleteReadError:
                    raise EOFError('Microphone stream ended')
                samples = struct.unpack('<320h', chunk)
                now = time.monotonic()
                playing = self.player.is_playing(ECHO_TAIL_SECONDS)

                # Half-duplex holdoff: while the assistant's voice is in the room/speakers,
                # suppress microphone input to prevent self-interruption and echo loops.
                held = not self.barge_in_enabled and playing
                if held:
                    held_frames += 1
                    self.microphone_rms = 0.0
                    self.gate.process(chunk, now=now, blocked=True)
                    if self.barge_gate is not None:
                        self.barge_gate.reset()
                    continue

                if held_frames:
                    log.info('Microphone held %d frames while assistant was speaking', held_frames)
                    held_frames = 0

                self.microphone_rms = 0.0 if self.muted else (sum(x * x for x in samples) / 320) ** 0.5 / 32768
                occupied = playing or (self._reply_authorized and not self.gate.active)
                frame = None
                if (self.barge_in_enabled and self.barge_gate is not None and occupied and not self.muted and not self._drop_response
                        and not self._barge_pending):
                    frame = self.barge_gate.process(chunk, now)
                    if frame is not None:
                        self._accept_interruption()
                elif self.barge_gate is not None:
                    self.barge_gate.reset()
                if frame is None:
                    frame = self.gate.process(chunk, now=now, blocked=self.muted or occupied or self._drop_response)
                if frame.opened:
                    self._speech_opened_at = now
                    self._speech_closed_at = None
                    self.response_first_audio_ms = None
                    self._user_text = self._assistant_text = ''
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
                    raise MicrophoneBacklogError(
                        'Active microphone backlog exceeded four seconds') from None
                if frame.closed:
                    activity_open = False
        except asyncio.CancelledError:
            raise

    async def send_audio(self, session, reader):
        queue = asyncio.Queue(maxsize=CAPTURE_QUEUE_FRAMES)
        self._capture_queue = queue
        try:
            await supervise(self._capture_audio(reader, queue), self._send_frames(session, queue))
        finally:
            self._capture_queue = None

    async def _send_frames(self, session, queue):
        from google.genai import types

        activity_open = False
        while True:
            frame, generation = await queue.get()
            stale = generation != self.player.generation
            chunk = frame.pcm
            async with self.send_lock:
                blocked = self.muted or self.player.is_playing(ECHO_TAIL_SECONDS) or self._drop_response or stale
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
                    and time.monotonic() - self._last_progress > 15):
                log.info('Turn wait timeout after 15s; settling back to idle')
                self._reply_authorized = self._reply_started = self._waiting = False
                self._drop_response = False


async def run(args, key: str):
    from google import genai

    config = getattr(args, 'config_obj', None) or load_config()
    model = getattr(args, 'model', None) or config.model
    voice_name = getattr(args, 'voice', None) or config.voice
    device = getattr(args, 'device', None) or config.device

    player = Playback(sink=config.output_device or 'default')
    voice = LiveVoice(
        player,
        transcripts=getattr(args, 'transcripts', False),
        barge_in=config.barge_in,
        greet_on_start=getattr(config, 'greet_on_start', True),
    )
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
        while True:
            started = time.monotonic()
            session_opened = False
            attempted_resume = bool(voice.resume_handle)
            microphone = None
            retry_delay = 0.0
            try:
                log.info('Connecting to %s (voice=%s)%s', model, voice_name,
                         ' [resuming]' if voice.resume_handle else '')
                session_cfg = live_config(voice=voice_name, resume_handle=voice.resume_handle, barge_in=voice.barge_in_enabled)
                async with genai.Client(api_key=key).aio as client:
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

                        async def greet_and_wait():
                            await voice.send_greeting(session)
                            await asyncio.Event().wait()

                        await supervise(
                            greet_and_wait(),
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
                retry_delay = decision.delay
            finally:
                voice.connected = False
                if microphone is not None:
                    await stop_process(microphone)
                voice._reply_authorized = voice._reply_started = voice._waiting = False
                voice._drop_response = voice._model_active = False
                voice._barge_pending = voice._barge_turn = False
                voice._user_text = voice._assistant_text = ''
                voice._speech_closed_at = None
                voice.gate.reset()
                voice.barge_gate.reset()
                await player.interrupt()
            await asyncio.sleep(retry_delay)
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
