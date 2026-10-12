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

from echo_cancel import EchoCancellation
from skills import DesktopSkills, SkillError

log = logging.getLogger('gemini_voice')
INPUT_BYTES = 640  # 20 ms, 16 kHz, mono signed little-endian PCM16
OUTPUT_BYTES = 960  # 20 ms, 24 kHz, mono signed little-endian PCM16


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
        self.queue = asyncio.Queue(maxsize=500)  # At most ten seconds of PCM.
        self.generation = 0
        self.process = None
        self.playback_until = 0.0

    def enqueue(self, data):
        if len(data) % 2:
            raise ValueError('Gemini output contains an incomplete PCM16 sample')
        chunks = (len(data) + OUTPUT_BYTES - 1) // OUTPUT_BYTES
        if chunks > self.queue.maxsize - self.queue.qsize():
            # Never block receiving interruption events behind a full queue.
            raise BufferError('Audio output backlog exceeded ten seconds')
        for offset in range(0, len(data), OUTPUT_BYTES):
            self.queue.put_nowait((self.generation, data[offset:offset + OUTPUT_BYTES]))

    async def interrupt(self):
        self.generation += 1
        self.playback_until = 0.0
        while not self.queue.empty():
            self.queue.get_nowait()
        process, self.process = self.process, None
        await stop_process(process)

    async def run(self):
        while True:
            generation, data = await self.queue.get()
            if generation != self.generation:
                continue
            if self.process is None:
                process = await asyncio.create_subprocess_exec(
                    'pw-play', '--rate', '24000', '--channels', '1', '--format', 's16',
                    '--latency', '40ms', '--target', self.sink, '-a', '-',
                    stdin=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
                # An interruption can arrive while process creation is awaited.
                if generation != self.generation:
                    await stop_process(process)
                    continue
                self.process = process
            process = self.process
            if process.returncode is not None:
                raise RuntimeError('Audio output process exited unexpectedly')
            try:
                process.stdin.write(data)
                await process.stdin.drain()
            except (BrokenPipeError, ConnectionResetError):
                if generation != self.generation:
                    continue
                raise
            now = time.monotonic()
            self.playback_until = max(self.playback_until, now) + len(data) / 48000
            # Feed a small cushion without dumping a whole reply into PipeWire.
            await asyncio.sleep(max(0.0, self.playback_until - now - 0.08))


class RenewConnection(Exception):
    """The service requested a new transport connection."""


class LiveVoice:
    def __init__(self, player, *, transcripts=False, skills=None):
        self.player = player
        self.transcripts = transcripts
        self.skills = skills
        self.resume_handle = None
        self.send_lock = asyncio.Lock()
        self.tool_tasks = {}
        self.tool_responses = {}

    async def send_audio(self, session, reader):
        from google.genai import types

        while True:
            try:
                chunk = await reader.readexactly(INPUT_BYTES)
            except asyncio.IncompleteReadError as error:
                raise EOFError('Microphone stream ended') from error
            # No playback-state gate: speech continues upstream during replies.
            async with self.send_lock:
                await session.send_realtime_input(
                    audio=types.Blob(data=chunk, mime_type='audio/pcm;rate=16000'))

    async def _send_tool_response(self, session, response):
        async with self.send_lock:
            await session.send_tool_response(function_responses=response)

    async def _execute_tool(self, session, call):
        from google.genai import types

        try:
            result = await self.skills.execute(call.name, call.args or {})
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
        self.tool_responses[call.id] = response
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
        self.tool_responses.clear()

    async def handle(self, event, session=None):
        update = event.session_resumption_update
        if update is not None:
            if update.resumable and update.new_handle:
                self.resume_handle = update.new_handle
            elif update.resumable is False:
                self.resume_handle = None
        content = event.server_content
        if content is not None:
            if content.interrupted:
                await self.player.interrupt()
                # Audio in the same interrupted event belongs to the old turn.
                return
            if content.model_turn:
                for part in content.model_turn.parts or []:
                    blob = part.inline_data
                    if blob is not None and blob.data:
                        if blob.mime_type not in ('audio/pcm;rate=24000', 'audio/pcm'):
                            raise ValueError('Unexpected Gemini audio output format')
                        self.player.enqueue(blob.data)
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
            if self.skills is None:
                raise RuntimeError('Gemini requested a desktop skill while skills are disabled')
            if session is None:
                raise RuntimeError('A live session is required to execute desktop skills')
            for call in tool_call.function_calls or []:
                if not call.id or not call.name:
                    raise ValueError('Gemini sent a desktop skill call without an id or name')
                if call.id in self.tool_tasks:
                    continue
                if call.id in self.tool_responses:
                    task = asyncio.create_task(
                        self._send_tool_response(session, self.tool_responses[call.id]))
                else:
                    task = asyncio.create_task(self._execute_tool(session, call))
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


def live_config(voice, resume_handle=None, skills=None):
    instruction = (
        'You are Jarvis, a friendly voice assistant for an Omarchy desktop. '
        'Speak naturally, clearly and briefly, and match the user\'s language. '
        'Listen to corrections and interruptions. Use a declared desktop skill '
        'only when the user asks for that action. Never claim an action succeeded '
        'until its tool result says so. You cannot run arbitrary shell commands, '
        'access private files, install software, or perform destructive actions.'
        if skills is not None else
        'You are a friendly voice conversation assistant. Speak naturally, '
        'clearly and briefly. Match the user\'s language. Listen to corrections '
        'and interruptions. Ask a short clarification when needed. You can '
        'converse, but have no tools or access to the user\'s computer.'
    )
    config = {
        'response_modalities': ['AUDIO'],
        'system_instruction': instruction,
        'speech_config': {'voice_config': {'prebuilt_voice_config': {'voice_name': voice}}},
        'input_audio_transcription': {},
        'output_audio_transcription': {},
        'realtime_input_config': {
            'automatic_activity_detection': {
                'disabled': False,
                'start_of_speech_sensitivity': 'START_SENSITIVITY_HIGH',
                'end_of_speech_sensitivity': 'END_SENSITIVITY_LOW',
                'prefix_padding_ms': 200,
                'silence_duration_ms': 400,
            },
            'activity_handling': 'START_OF_ACTIVITY_INTERRUPTS',
        },
        'session_resumption': {'handle': resume_handle},
        'context_window_compression': {'sliding_window': {}},
    }
    if skills is not None:
        config['tools'] = [{'function_declarations': skills.declarations}]
    return config


async def run(args, key):
    from google import genai

    echo = EchoCancellation()
    try:
        # Failing closed prevents a raw speaker-to-microphone feedback loop.
        await echo.start(args.microphone)
        player = Playback(echo.sink)
        skills = (None if getattr(args, 'no_skills', False) else
                  DesktopSkills(getattr(args, 'skill_dir', None) or None))
        voice = LiveVoice(player, transcripts=args.transcripts, skills=skills)
        failures = 0
        async with genai.Client(api_key=key).aio as client:
            while True:
                microphone = None
                started = time.monotonic()
                delay = 0.25
                try:
                    log.info('Connecting to %s%s', args.model,
                             ' (resuming)' if voice.resume_handle else '')
                    async with client.live.connect(
                        model=args.model,
                        config=live_config(args.voice, voice.resume_handle, skills)
                    ) as session:
                        microphone = await asyncio.create_subprocess_exec(
                            'pw-record', '--rate', '16000', '--channels', '1',
                            '--format', 's16', '--latency', '20ms', '--target',
                            echo.source, '-a', '-', stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.DEVNULL, limit=INPUT_BYTES * 10)
                        log.info('LIVE — microphone streaming; speak naturally. Ctrl+C stops capture.')
                        await supervise(voice.send_audio(session, microphone.stdout),
                                        voice.receive(session), player.run())
                except RenewConnection:
                    failures = 0
                    log.info('Gemini requested connection renewal')
                except Exception as error:
                    code = getattr(error, 'code', None)
                    if code == 400 and voice.resume_handle:
                        voice.resume_handle = None
                        log.warning('Session resume rejected; next attempt starts a fresh conversation')
                    elif code in (400, 401, 403, 404):
                        raise RuntimeError(f'Gemini rejected configuration/credentials (HTTP {code})') from None
                    if time.monotonic() - started >= 60:
                        failures = 0
                    failures += 1
                    if failures > args.retries:
                        raise RuntimeError('Voice retry limit reached; check network, quota and audio devices') from None
                    delay = min(30, 2 ** (failures - 1))
                    # Avoid logging SDK errors that may contain request credentials.
                    log.warning('Connection ended (%s); reconnecting in %ss [%s/%s]',
                                type(error).__name__, delay, failures, args.retries)
                finally:
                    try:
                        await stop_process(microphone)
                    finally:
                        await player.interrupt()
                await asyncio.sleep(delay)
    finally:
        await echo.close()
        log.info('STOPPED — capture closed and private echo-cancellation routes released')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', default=os.getenv('GEMINI_LIVE_MODEL', 'gemini-3.8-live'))
    parser.add_argument('--voice', default='Aoede', help='Gemini prebuilt voice name')
    parser.add_argument('--microphone', help='Physical PipeWire/Pulse source name; default is system microphone')
    parser.add_argument('--retries', type=int, default=5, help='Consecutive failure retry budget')
    parser.add_argument('--transcripts', action='store_true', help='Print transcript fragments to this terminal')
    parser.add_argument('--no-skills', action='store_true', help='Disable all Omarchy desktop controls')
    parser.add_argument('--list-skills', action='store_true', help='List desktop skills and command availability')
    parser.add_argument('--skill-dir', action='append', metavar='DIR',
                        help='Load dynamic JSON skill manifests from DIR instead of bundled defaults')
    parser.add_argument('--check', action='store_true', help='Check dependencies without opening audio or network')
    args = parser.parse_args()
    if args.retries < 0:
        parser.error('--retries must be nonnegative')
    missing = [name for name in ('pw-record', 'pw-play', 'pactl') if shutil.which(name) is None]
    if missing:
        parser.error('Missing desktop audio commands: ' + ', '.join(missing))
    try:
        from google.genai import types
        check_skills = None if args.no_skills else DesktopSkills(args.skill_dir or None)
        types.LiveConnectConfig.model_validate(live_config(args.voice, skills=check_skills))
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
    key = os.getenv('GEMINI_API_KEY', '').strip()
    if not key:
        if not sys.stdin.isatty():
            parser.error('Set GEMINI_API_KEY or run interactively to enter it privately')
        key = getpass.getpass('Gemini API key (hidden, not saved): ').strip()
    if not key:
        parser.error('A Gemini API key is required')
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

    async def start():
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
