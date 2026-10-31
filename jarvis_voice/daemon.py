"""Sovereign Voice Daemon for JARVIS OS.

Full-duplex Gemini Live voice streaming over PipeWire with local speech gating
and hard interruption.
"""
from __future__ import annotations

import argparse
import asyncio
import contextlib
import getpass
import json
import logging
import os
import re
import signal
import struct
import sys
import time
from pathlib import Path

from .config import load as load_config, load_env
from .ipc import ControlServer
from .microphone import read_microphone_state
from .playback import Playback, MicrophoneBacklogError, stop_process, audio_environment
from .recovery import ConnectionRecovery
from .speech import SpeechTurnGate, SileroSpeechDetector, SpokenInterruption, GateFrame

log = logging.getLogger('jarvis_voice')
INPUT_BYTES = 640  # 20ms at 16kHz mono s16le (320 samples)
CAPTURE_QUEUE_FRAMES = 200
RESPONSE_WARNING_SECONDS = 15
RESPONSE_TIMEOUT_SECONDS = 45
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
                fns = t.get('function_declarations') or t.get('functionDeclarations') or []
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
        "5. Speak only in response to the user. Give one concise reply per turn, then wait silently.\n"
        "6. WEB SEARCH: Use 'web_search' only when the user explicitly asks to search the web, check current news, or lookup real-time live events. For general knowledge, concepts, conversation, and questions you know, answer directly and concisely without calling web_search. NEVER call 'open_page' or launch a browser unless the user explicitly asks to open or show a web page on their desktop screen."
    )
    if 'omarchy_help' in active_tools:
        from jarvis_control.omarchy_skill import ROUTING
        inst += ROUTING
    if 'camera_view' in active_tools:
        from jarvis_control.vision import ROUTING
        inst += ROUTING
    if 'task_submit' in active_tools:
        from jarvis_control.tasks import ROUTING
        # Completion is retrieved explicitly until voice notices are connected.
        inst += ROUTING.replace('completion is announced separately.',
                                'check task_status when the user asks for progress.')
    return inst


def live_config(voice: str = 'Aoede', resume_handle: str | None = None, barge_in: bool = False, tools: list | None = None, skills=None, config=None, memory_context: str | None = None) -> dict:
    instruction = build_instruction(tools)
    if skills is not None and hasattr(skills, 'memory_context'):
        memory_config = getattr(config, 'memory', None)
        if memory_config is None or memory_config.enabled:
            instruction += (
                '\nCONTINUOUS MEMORY RULES:\n'
                '1. JARVIS possesses persistent, continuous memory across all time without session boundaries. Every conversation turn is saved.\n'
                '2. You have tools: "recall_conversation", "recall_memory", and "memory_status".\n'
                '3. When the user asks what was discussed earlier, what was talked about yesterday, or about past interactions, ALWAYS call recall_conversation or recall_memory first to retrieve the real dialogue history.\n'
                '4. Conversation text is retained continuously across restarts when continuous_history is enabled; provider connections do not reset that memory. NEVER claim you have no memory, never claim your memory clears or resets on reboot/RAM reset, and never claim you lack tools to view past conversations.\n'
                '5. Only recent conversation turns are in the active prompt context below; use recall_conversation with a keyword or empty query to fetch older history.'
            )
        mem_ctx = memory_context if memory_context is not None else skills.memory_context()
        if mem_ctx:
            instruction += f"\n\nActive Memory Context:\n{mem_ctx}"

    cfg = {
        'response_modalities': ['AUDIO'],
        'session_resumption': {},
        'thinking_config': {'thinking_budget': 0},
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
        self.microphone_state = dict(source='', muted=None, volume_percent=None, issue='')
        self.microphone_frames_sent = 0
        self.provider_audio_bytes = 0
        self.recognized_input_events = 0
        self.provider_interruptions = 0
        self.local_interruptions = 0
        self._waiting = False
        self.response_delayed = False
        self.last_error = ''
        self._tool_response_pending = False
        self._tools_in_flight = 0
        self._confirmation_gate_turn = None
        self._tool_results = {}
        self._greeting_active = False
        self._active_tool = ''
        self._last_tool = None
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
        self.activity_end_sent_at: float | None = None
        self.provider_first_audio_ms: int | None = None
        self.broadcast = None
        self.gate = speech_gate or SpeechTurnGate(silence_frames=15, tail_seconds=.20)
        self.barge_in_enabled = bool(barge_in)
        ref = getattr(player, 'reference', None)
        detector = getattr(self.gate, 'detector', None) if self.gate else None
        min_rms = getattr(config, 'barge_in_min_rms', 0.008) if config else 0.008
        echo_th = getattr(config, 'barge_in_echo_threshold', 0.35) if config else 0.35
        vad_th = getattr(config, 'barge_in_vad_threshold', 0.85) if config else 0.85
        self.barge_gate = SpokenInterruption(
            ref, detector=detector,
            min_rms=min_rms,
            echo_threshold=echo_th,
            vad_threshold=vad_th,
            min_voiced=8,
            min_positives=6,
        ) if ref else None
        self._user_text = ''
        self._assistant_text = ''
        self._capture_queue: asyncio.Queue | None = None

    def status(self) -> dict:
        speaking = self.player.busy
        input_state = ('microphone_muted' if self.microphone_state['muted'] is True else
                       'microphone_silent' if self.microphone_state['volume_percent'] == 0 else '')
        input_issue = self.microphone_state['issue'] if input_state and self.connected else ''
        state = ('connecting' if not self.connected else
                 'speaking' if speaking else
                 'muted' if self.muted else
                 input_state if input_state else
                 'listening' if self.gate.active and not self.muted else
                 'thinking' if self._waiting else 'idle')
        return {
            'state': state,
            'connection_state': ('connecting' if not self.connected else 'muted' if self.muted else 'speaking' if speaking else input_state or 'listening'),
            'listening': self.connected and not self.muted and not speaking and not input_state,
            'connected': self.connected,
            'muted': self.muted,
            'model': self.model,
            'microphone_rms': self.microphone_rms,
            'microphone': dict(self.microphone_state),
            'automatic_barge_in': self.barge_in_enabled,
            'provider_audio_bytes': self.provider_audio_bytes,
            'provider_interruptions': self.provider_interruptions,
            'local_interruptions': self.local_interruptions,
            'accepted_speech_turns': self.gate.accepted_turns,
            'response_delayed': self.response_delayed,
            'error': input_issue or self.last_error,
            'memory_enabled': bool(self.skills and getattr(getattr(self.config, 'memory', None), 'enabled', False)),
            'tools_in_flight': self._tools_in_flight,
            'active_tool': self._active_tool,
            'last_tool': self._last_tool,
            'control_enabled': bool(self.skills and getattr(self.skills, 'control', None)),
            'tool_count': len(self.skills.declarations) if self.skills else 0,
            'latency': {
                'speech_end_to_first_audio_ms': self.response_first_audio_ms,
                'first_audio_chunk_to_write_ms': self.player.first_chunk_write_ms,
                'activity_end_to_first_audio_ms': self.provider_first_audio_ms,
                'speech_active': self.gate.active,
                'speech_probability': self.gate.last_probability,
                'capture_queue_frames': self._capture_queue.qsize() if self._capture_queue else 0,
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
        self._greeting_active = False
        self.response_delayed = False
        self.last_error = ''
        self._tool_response_pending = False
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
        # ActivityStart also interrupts a reply that is still being generated.
        # Drain its interrupted -> turn_complete boundary without revoking the
        # new user's authorization, even if no old audio has arrived yet.
        self._barge_pending = bool(self._reply_authorized or self._waiting
                                   or self._model_active or self._reply_started)
        self._barge_turn = True
        self._barge_started_at = time.monotonic()
        process = self.player.cancel_pending()
        self._reply_authorized = self._waiting = True
        self._reply_started = self._drop_response = self._model_active = False
        self._last_progress = self._barge_started_at
        self.gate.admit_interruption()
        self.local_interruptions += 1
        last_corr = getattr(self.barge_gate, 'last_correlation', 0.0) if self.barge_gate else 0.0
        log.info('Local barge-in accepted (count=%d, correlation=%.3f)', self.local_interruptions, last_corr)
        if process is not None:
            asyncio.create_task(stop_process(process))

    async def send_greeting(self, session):
        """Send an initial user turn prompt on session start so JARVIS greets the user out loud."""
        from google.genai import types

        if not self.greet_on_start or self._greeted or self.muted:
            return
        self._greeted = True
        self._greeting_active = True
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
            # Input transcription is independent of model-turn ordering. It can
            # arrive while the previous answer's interruption boundary drains.
            incoming = getattr(content, 'input_transcription', None)
            if incoming is not None and getattr(incoming, 'text', None):
                self.recognized_input_events += 1
                self._memory_user = (self._memory_user + incoming.text)[-16000:]
                if self._reply_authorized:
                    self._user_text += incoming.text
                if self._reply_authorized and not self._reply_started:
                    self._waiting = True

            if self._barge_pending:
                if getattr(content, 'interrupted', False):
                    self.provider_interruptions += 1
                if getattr(content, 'turn_complete', False):
                    self._barge_pending = False
                    self._model_active = False
                return

            if getattr(content, 'interrupted', False):
                self.provider_interruptions += 1
                self._tool_response_pending = False
                self._waiting = self._drop_response = self._model_active = False
                self._reply_authorized = self._reply_started = False
                self.gate.reset(hold_until=time.monotonic() + self.gate.tail_seconds)
                await self.player.interrupt()
                return

            outgoing = getattr(content, 'output_transcription', None)
            if outgoing is not None and getattr(outgoing, 'text', None):
                self._memory_assistant = (self._memory_assistant + outgoing.text)[-16000:]
                if self._reply_authorized and not self._barge_turn:
                    self._assistant_text += outgoing.text

        tool_call = getattr(event, 'tool_call', None)
        if tool_call is not None:
            event_token = (self.gate.accepted_turns, self.player.generation)
            await self.handle_tools(tool_call, session)
            if event_token != (self.gate.accepted_turns, self.player.generation):
                return  # An old event must not complete or speak over a new turn.

        if content is not None:
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
                            self._tool_response_pending = False
                            self.response_delayed = False
                            self.last_error = ''
                            if not self._reply_started:
                                if self.activity_end_sent_at is not None:
                                    self.provider_first_audio_ms = max(0, round(
                                        (time.monotonic() - self.activity_end_sent_at) * 1000))
                                log.info('First response audio: local_end_ms=%s provider_ms=%s',
                                         None if self._speech_closed_at is None else round(
                                             (time.monotonic() - self._speech_closed_at) * 1000),
                                         self.provider_first_audio_ms)
                                if self._speech_closed_at is not None:
                                    self.response_first_audio_ms = max(0, round(
                                        (time.monotonic() - self._speech_closed_at) * 1000))
                                self.player.begin_reply()
                            self._reply_started = True
                            self._last_progress = time.monotonic()
                            self.player.enqueue(blob.data)

            if getattr(content, 'turn_complete', False):
                # Live emits an intermediate boundary after a function call;
                # its spoken answer arrives in the following receive cycle.
                if self._tool_response_pending and not self._reply_started:
                    return
                self.response_delayed = False
                self.last_error = ''
                self._greeting_active = False
                memory_config = getattr(self.config, 'memory', None)
                if self.skills is not None and memory_config and memory_config.enabled and (
                        memory_config.record_sessions or memory_config.auto_capture or
                        memory_config.structured_capture):
                    if hasattr(self.skills, 'queue_memory_exchange'):
                        self.skills.queue_memory_exchange(self._memory_user, self._memory_assistant)
                    self._memory_user = ''
                    self._memory_assistant = ''
                if self.transcripts and self._user_text.strip():
                    log.info('User: "%s"', self._user_text.strip())
                if self.transcripts and self._assistant_text.strip():
                    log.info('JARVIS: "%s"', self._assistant_text.strip())
                self._user_text = ''
                self._assistant_text = ''
                if hasattr(self.player, 'finish_reply'):
                    self.player.finish_reply()
                self._drop_response = self._model_active = False
                self._waiting = False
                self._reply_authorized = self._reply_started = False
                self._barge_turn = False

    async def handle_tools(self, tool_call, session):
        """Authorize, execute and report attached tool calls for one speech turn."""
        from google.genai import types

        if session is None:
            raise RuntimeError('Tool call received without an active provider session')
        responses = []
        batch_token = (self.gate.accepted_turns, self.player.generation)
        stop_batch = False
        for call in getattr(tool_call, 'function_calls', []) or []:
            name = call.name
            call_id = getattr(call, 'id', None)
            if stop_batch or batch_token != (self.gate.accepted_turns, self.player.generation):
                response = {'ok': False, 'status': 'not_run',
                            'error': 'Earlier action failed, needs confirmation, or its speech turn ended. Inspect state before continuing.'}
            elif self.muted or self._drop_response or self._barge_pending or not self._reply_authorized or self._greeting_active:
                response = {'ok': False, 'status': 'rejected',
                            'error': 'No active authorized user speech turn for this action.'}
            else:
                started = time.monotonic()
                signature = None
                cached = None
                try:
                    allowed = {tool['name'] for tool in self.skills.declarations} if self.skills else set()
                    if name not in allowed:
                        raise ValueError(f'Tool is not attached: {name}')
                    if call.args is not None and not isinstance(call.args, dict):
                        raise ValueError('Tool arguments must be an object')
                    arguments = dict(call.args or {})
                    signature = (name, json.dumps(arguments, sort_keys=True))
                    cached = self._tool_results.get(call_id) if call_id else None
                    if cached:
                        old_signature, old_response = cached
                        if signature != old_signature:
                            raise ValueError('Tool call ID reused with different arguments; action was not repeated.')
                        response = dict(old_response, cached=True)
                    else:
                        if name == 'confirm_last':
                            heard = re.sub(r'[^\w]+', ' ', str(arguments.get('heard_phrase', '')).casefold()).strip()
                            actual = re.sub(r'[^\w]+', ' ', self._user_text.casefold()).strip()
                            if not heard or heard != actual or self._confirmation_gate_turn == self.gate.accepted_turns:
                                raise ValueError('Confirmation requires a matching user transcript from a new spoken turn.')
                        timeout = (90 if name in {'web_search', 'open_page', 'read_page_text', 'read_screen',
                                                  'browser_task', 'compose_windows', 'run_in_terminal'}
                                   else 30 if name == 'system_control' else 15)
                        self._tools_in_flight += 1
                        self._active_tool = name
                        log.info('Executing tool %s: %s', name, json.dumps(arguments))
                        try:
                            result = await asyncio.wait_for(self.skills.execute(name, arguments), timeout=timeout)
                        finally:
                            self._tools_in_flight -= 1
                            self._active_tool = ''
                            if self._barge_pending and not self._tools_in_flight:
                                self._barge_started_at = self._last_progress = time.monotonic()
                        log.info('Tool %s finished in %.2fs', name, time.monotonic() - started)
                        if isinstance(result, str) and result.startswith('ERROR:'):
                            detail = result[len('ERROR:'):].strip()
                            held = 'needs spoken confirmation' in detail
                            response = {'ok': False, 'status': 'needs_confirmation' if held else 'failed',
                                        'error': detail, 'result': result}
                            if held:
                                self._confirmation_gate_turn = self.gate.accepted_turns
                        else:
                            response = {'ok': True, 'status': 'completed', 'result': result}
                except TimeoutError:
                    response = {'ok': False, 'status': 'unknown',
                                'error': 'Tool timed out; outcome is unknown. Inspect current state before retrying any action.'}
                except Exception as error:
                    log.warning('Tool %s failed: %s', name, type(error).__name__)
                    response = {'ok': False, 'status': 'failed', 'error': str(error)}
                if call_id and signature is not None and cached is None:
                    self._tool_results[call_id] = (signature, response)
                    if len(self._tool_results) > 64:
                        self._tool_results.pop(next(iter(self._tool_results)))
                self._last_tool = {'name': name, 'ok': response['ok'], 'status': response['status'],
                                   'duration_ms': max(0, round((time.monotonic() - started) * 1000))}
            if not response['ok']:
                stop_batch = True
            responses.append(types.FunctionResponse(id=call_id, name=name, response=response))
        if responses:
            current_turn = batch_token == (self.gate.accepted_turns, self.player.generation)
            if current_turn and self._reply_authorized:
                self._tool_response_pending = True
            async with self.send_lock:
                await asyncio.wait_for(session.send_tool_response(function_responses=responses), 3)
            if current_turn:
                self._last_progress = time.monotonic()

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
                occupied = playing or (self._model_active and not self.gate.active)
                frame = None
                playback_starting = (playing and getattr(self.player, 'first_write_at', None) is not None
                                     and now - self.player.first_write_at < 0.25)
                if (self.barge_in_enabled and self.barge_gate is not None and occupied and not playback_starting
                        and not self.muted and not self._drop_response and not self._barge_pending):
                    frame = self.barge_gate.process(chunk, now)
                    if frame is not None:
                        self._accept_interruption()
                elif self.barge_gate is not None:
                    self.barge_gate.reset()
                if frame is None:
                    frame = self.gate.process(chunk, now=now, blocked=self.muted or occupied or self._drop_response)
                if frame.opened:
                    if not getattr(frame, 'barge_in', False):
                        self._barge_pending = self._barge_turn = False
                    self._greeting_active = False
                    self._speech_opened_at = now
                    self._speech_closed_at = None
                    self.response_first_audio_ms = None
                    self.response_delayed = False
                    self.last_error = ''
                    self._tool_response_pending = False
                    self.activity_end_sent_at = None
                    self.provider_first_audio_ms = None
                    self._user_text = self._assistant_text = ''
                    self._reply_authorized = self._waiting = True
                    self._reply_started = self._drop_response = self._model_active = False
                    self._last_progress = now
                    activity_open = True
                    log.info('Accepted local speech turn id=%d', self.gate.accepted_turns)
                if frame.closed:
                    self._speech_closed_at = now
                    log.info('Local speech closed after %.0f ms',
                             (now - self._speech_opened_at) * 1000 if self._speech_opened_at else 0)
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
            chunk = frame.pcm
            async with self.send_lock:
                # Interruption can change generations while this sender waits
                # for another audio/tool message to release the transport.
                stale = generation != self.player.generation
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
                    self.activity_end_sent_at = time.monotonic()
                    log.info('Speech uploaded; waiting for provider audio')
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

    async def monitor_microphone(self):
        """Report the actual capture route without changing a user's mute setting."""
        while True:
            previous = self.microphone_state
            self.microphone_state = await read_microphone_state()
            if self.microphone_state['issue'] != previous['issue']:
                if self.microphone_state['issue']:
                    log.warning('%s', self.microphone_state['issue'])
                elif previous['issue']:
                    log.info('Microphone input is available again')
            await asyncio.sleep(2)

    async def monitor_response(self):
        while True:
            await asyncio.sleep(0.25)
            if (self._barge_pending and not self._tools_in_flight and self._barge_started_at is not None and
                    time.monotonic() - self._barge_started_at > 5):
                self.resume_handle = None
                self._barge_pending = self._barge_turn = False
                raise ConnectionError('Barge-in acknowledgement timeout')
            if (self._reply_authorized and not self._tools_in_flight and not self.gate.active and not self.player.busy
                    and time.monotonic() - self._last_progress > RESPONSE_WARNING_SECONDS):
                self.response_delayed = True
                self.last_error = 'The response is taking longer than expected.'
                if time.monotonic() - self._last_progress > RESPONSE_TIMEOUT_SECONDS:
                    self.resume_handle = None
                    raise ConnectionError('Voice response timed out; reconnecting. Please repeat your question.')


async def run(args, key: str):
    from jarvis_memory.skills import MemorySkills
    from jarvis_control.skills import ControlSkills, UnifiedSkills

    config = getattr(args, 'config_obj', None) or load_config()
    config.validate()
    mem_skills = MemorySkills(config=config, api_key=key)
    ctrl_skills = ControlSkills(config=config) if getattr(config, 'enable_tools', True) else None
    skills = UnifiedSkills(memory_skills=mem_skills, control_skills=ctrl_skills)
    try:
        await skills.start()
        await _run_voice(args, key, config, skills)
    finally:
        await skills.close_agent_jobs()


async def _run_voice(args, key: str, config, skills):
    from google import genai

    model = getattr(args, 'model', None) or config.model
    voice_name = getattr(args, 'voice', None) or config.voice
    device = getattr(args, 'device', None) or config.device

    player = Playback(sink=config.output_device or 'default')
    voice = LiveVoice(
        player,
        transcripts=getattr(args, 'transcripts', False),
        barge_in=config.barge_in,
        greet_on_start=getattr(config, 'greet_on_start', True),
        skills=skills, config=config,
    )
    voice.model = model
    voice.muted = not config.autostart_listening

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
                if not attempted_resume:
                    voice._tool_results.clear()
                context = await skills.context_async()
                tools = [{'function_declarations': skills.declarations}] if skills.declarations else None
                session_cfg = live_config(voice=voice_name, resume_handle=voice.resume_handle,
                                          barge_in=voice.barge_in_enabled, tools=tools,
                                          skills=skills, config=config, memory_context=context)
                async with genai.Client(api_key=key).aio as client:
                    async with client.live.connect(model=model, config=session_cfg) as session:
                        session_opened = True
                        voice.connected = True
                        voice.last_error = ''
                        log.info('Connected to Gemini Live — streaming audio')
                        await player.prepare()

                        mic_args = ['pw-record', '--rate', '16000', '--channels', '1',
                                    '--format', 's16', '--latency', '20ms',
                                    '--properties', 'application.id=jarvis-voice node.name=jarvis-microphone']
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
                            voice.monitor_microphone(),
                            voice.monitor_response(),
                        )
            except Exception as error:
                voice.last_error = str(error)
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
                voice._tool_response_pending = False
                voice._user_text = voice._assistant_text = ''
                voice._speech_closed_at = None
                voice.activity_end_sent_at = None
                voice.response_first_audio_ms = None
                voice.provider_first_audio_ms = None
                voice.response_delayed = False
                voice.microphone_state = dict(source='', muted=None, volume_percent=None, issue='')
                voice.gate.reset()
                if voice.barge_gate is not None:
                    voice.barge_gate.reset()
                await player.interrupt()
            await asyncio.sleep(retry_delay)
    finally:
        await ipc.close()


def main(args=None):
    try:
        config = load_config()
    except (ValueError, OSError) as error:
        print(f'Voice config error: {error}', file=sys.stderr)
        return 1
    load_env(config.api_key_env)
    from .config import control_config
    control = control_config(config)
    load_env(control.api_key_env)
    load_env(control.vision_api_key_env or control.api_key_env)
    if args is not None:
        args.config_obj = config
    key = os.environ.get(config.api_key_env) or os.environ.get('GEMINI_API_KEY') or os.environ.get('GOOGLE_API_KEY')
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
