"""Bounded offline recognition and exact short-command routing.

Audio stays in memory. A separate, single-request worker owns Whistle's
non-thread-safe native runtime; deadlines terminate it rather than leaving
inference running on the audio loop.
"""
from __future__ import annotations

import asyncio
import base64
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import sys
import time


@dataclass
class LocalSpeechConfig:
    enabled: bool = False
    max_command_seconds: float = 2.5
    decode_timeout: float = .35
    minimum_word_probability: float = .65

    def validate(self):
        if type(self.enabled) is not bool:
            raise ValueError('local_speech.enabled must be a boolean')
        for name, low, high in (('max_command_seconds', 1, 5),
                                ('decode_timeout', .05, 1),
                                ('minimum_word_probability', .5, 1)):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not low <= value <= high:
                raise ValueError(f'local_speech.{name} must be between {low} and {high}')
        return self


def normalize(text):
    return re.sub(r'[^a-z0-9% ]', '', text.casefold()).strip()


def app_names(rows):
    """Only exact, unambiguous installed application names become commands."""
    aliases = {}
    for identity, description in rows:
        for name in (normalize(description.split(';')[0]), normalize(identity)):
            aliases.setdefault(name, set()).add(identity)
    return {name: next(iter(ids)) for name, ids in aliases.items() if len(ids) == 1 and name}


def command_for(text, apps):
    text = normalize(text)
    text = re.sub(r'^(?:(?:hey |okay |ok )?jarvis )', '', text)
    text = re.sub(r'^please ', '', text)
    text = re.sub(r' please$', '', text)
    if text in ('stop', 'stop talking', 'stop speaking', 'be quiet'):
        return ('stop', {})
    if text in ('standby', 'stand by', 'go to standby', 'go to sleep'):
        return ('enter_standby', {})
    if text in ('mute', 'mute audio', 'mute the audio', 'mute speakers'):
        return ('system_control', {'action': 'mute_set', 'enabled': True})
    if text in ('unmute', 'unmute audio', 'unmute the audio', 'unmute speakers'):
        return ('system_control', {'action': 'mute_set', 'enabled': False})
    for noun in ('volume', 'brightness'):
        if text in (f'{noun} up', f'increase {noun}', f'turn up the {noun}'):
            return ('system_control', {'action': noun + '_adjust', 'value': 5})
        if text in (f'{noun} down', f'decrease {noun}', f'turn down the {noun}'):
            return ('system_control', {'action': noun + '_adjust', 'value': -5})
        match = re.fullmatch(rf'(?:set )?(?:the )?{noun}(?: to)? (\d{{1,3}})(?:%| percent)?', text)
        if match and (1 if noun == 'brightness' else 0) <= int(match[1]) <= 100:
            return ('system_control', {'action': noun + '_set', 'value': int(match[1])})
    numbers = {'one': '1', 'two': '2', 'three': '3', 'four': '4', 'five': '5',
               'six': '6', 'seven': '7', 'eight': '8', 'nine': '9', 'ten': '10'}
    match = re.fullmatch(r'(?:switch to |go to )?workspace ([1-9]|10|one|two|three|four|five|six|seven|eight|nine|ten)', text)
    if match:
        return ('system_control', {'action': 'workspace_switch', 'workspace': numbers.get(match[1], match[1])})
    match = re.fullmatch(r'(?:open|launch|start) (.+)', text)
    if match and match[1] in apps:
        return ('launch_app', {'app': apps[match[1]]})
    return None


def could_be_command(text):
    """Release conversational audio early; partial text never executes tools."""
    text = normalize(text)
    text = re.sub(r'^(?:(?:hey |okay |ok )?jarvis(?: |$))', '', text)
    text = re.sub(r'^please(?: |$)', '', text)
    return bool(text and text.split()[0] in {
        'open', 'launch', 'start', 'volume', 'brightness', 'set', 'increase',
        'decrease', 'turn', 'switch', 'workspace', 'go', 'stop', 'be',
        'standby', 'stand', 'mute', 'unmute'})


class WhistleClient:
    def __init__(self, config):
        self.config = config
        self.process = None
        self.ready = False
        self.error = ''
        self.last_decode_ms = None
        self._lock = asyncio.Lock()

    async def start(self):
        async with self._lock:
            await self._start()

    async def _start(self):
        if not self.config.enabled:
            return
        root = Path(os.environ.get('JARVIS_WHISTLE_HOME', str(Path.home() / '.local/share/jarvis-runtime/whistle')))
        if not all((root / name).exists() for name in ('python/needle', 'whistle.cact', 'libneedle.so')):
            self.error = 'Whistle runtime is not installed'
            return
        env = dict(os.environ, PYTHONPATH=str(root / 'python'),
                   NEEDLE_WHISTLE_WEIGHTS=str(root / 'whistle.cact'),
                   NEEDLE3_LIB_PATH=str(root / 'libneedle.so'),
                   NEEDLE_TELEMETRY='0', DO_NOT_TRACK='1', HF_HUB_OFFLINE='1',
                   OMP_NUM_THREADS='2', OPENBLAS_NUM_THREADS='1')
        try:
            self.process = await asyncio.create_subprocess_exec(
                sys.executable, str(Path(__file__).with_name('whistle_worker.py')),
                stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL, env=env, limit=262144)
            message = await asyncio.wait_for(self.process.stdout.readline(), 5)
            self.ready = json.loads(message).get('ready') is True
            if not self.ready:
                raise RuntimeError('Whistle did not become ready')
            self.error = ''
        except Exception as error:
            await self.close()
            self.error = type(error).__name__

    async def maintain(self):
        while True:
            await asyncio.sleep(30)
            if self.config.enabled and not self.ready:
                await self.start()

    async def transcribe(self, pcm):
        if not self.ready or not pcm or len(pcm) > 32000 * self.config.max_command_seconds:
            return None
        async with self._lock:
            started = time.monotonic()
            try:
                request = json.dumps({'pcm': base64.b64encode(pcm).decode()}).encode() + b'\n'
                async with asyncio.timeout(self.config.decode_timeout):
                    self.process.stdin.write(request)
                    await self.process.stdin.drain()
                    result = json.loads(await self.process.stdout.readline())
                self.last_decode_ms = round((time.monotonic() - started) * 1000)
                words = result.get('words') or []
                if (not words or any(float(word.get('probability', 0)) < self.config.minimum_word_probability
                                     for word in words)):
                    return None
                return result.get('text') or None
            except asyncio.CancelledError:
                await self.close()
                raise
            except Exception as error:
                await self.close()
                self.error = type(error).__name__
                return None

    async def close(self):
        self.ready = False
        process, self.process = self.process, None
        if process is not None:
            if process.returncode is None:
                process.kill()
            await process.wait()

