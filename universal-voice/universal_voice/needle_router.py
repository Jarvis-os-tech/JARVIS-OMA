"""Optional offline intent routing. Needle proposes one bounded local action only."""
from __future__ import annotations

import asyncio
import base64
import json
import math
import os
from pathlib import Path
import re
import sys

from .local_speech import normalize


def schemas(apps):
    def tool(name, description, properties):
        return {'name': name, 'description': description, 'parameters': {
            'type': 'object', 'properties': properties, 'required': list(properties), 'additionalProperties': False}}
    bounded = lambda low, high: {'type': 'integer', 'minimum': low, 'maximum': high}
    tools = [
        tool('set_volume', 'Set speaker volume to an explicitly requested percentage.', {'value': bounded(0, 100)}),
        tool('set_brightness', 'Set screen brightness to an explicitly requested percentage.', {'value': bounded(1, 100)}),
        tool('increase_volume', 'Make the speakers louder.', {}),
        tool('decrease_volume', 'Make the speakers quieter or softer.', {}),
        tool('increase_brightness', 'Make the screen brighter.', {}),
        tool('decrease_brightness', 'Make the screen dimmer.', {}),
        tool('switch_workspace', 'Switch to a numbered desktop workspace.', {'workspace': bounded(1, 10)}),
    ]
    if apps:
        tools.append(tool('open_application', 'Open an installed app explicitly named by the user.',
                          {'app': {'type': 'string', 'enum': sorted(set(apps.values()))}}))
    return tools


def _numbers(text):
    ones = dict(zip('zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen'.split(), range(20)))
    tens = dict(zip('twenty thirty forty fifty sixty seventy eighty ninety'.split(), range(20, 100, 10)))
    tokens = re.findall(r'\d+|[a-z]+', text)
    values = {int(token) for token in tokens if token.isdigit()}
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if token in tens:
            value = tens[token]
            if i+1 < len(tokens) and tokens[i+1] in ones and ones[tokens[i+1]] < 10:
                i += 1
                value += ones[tokens[i]]
            values.add(value)
        elif token in ones:
            if i+1 < len(tokens) and tokens[i+1] == 'hundred':
                values.add(ones[token] * 100)
                i += 1
            else:
                values.add(ones[token])
        elif token == 'hundred':
            values.add(100)
        i += 1
    return values


def eligible_text(text):
    text = normalize(text.replace("'", ''))
    if (not text or len(text) > 240 or re.search(
            r'\b(dont|do not|not|never|avoid|except|unless|if|why|explain|what|how|whether|and|then|or)\b', text)):
        return False
    text = re.sub(r'^(?:hey )?jarvis ', '', text)
    text = re.sub(r'^(?:can|could|would|will) you (?:please )?', '', text)
    text = re.sub(r'^i (?:want|need|would like) (?:you )?to ', '', text)
    text = re.sub(r'^please ', '', text)
    return bool(re.match(r'^(open|launch|start|make|turn|set|put|switch|go|move|increase|decrease|raise|lower|brighten|dim|volume|brightness|workspace)\b', text))


def validate_prediction(result, text, apps, minimum_confidence=.8):
    """Model confidence never bypasses argument bounds, explicit targets or negation."""
    if not eligible_text(text):
        return None
    text = normalize(text.replace("'", ''))
    confidence = result.get('confidence')
    if (isinstance(confidence, bool) or not isinstance(confidence, (int, float))
            or not math.isfinite(confidence) or confidence < minimum_confidence or confidence > 1):
        return None
    calls = result.get('function_calls')
    if not isinstance(calls, list) or len(calls) != 1:
        return None
    call = calls[0]
    if not isinstance(call, dict):
        return None
    name, args = call.get('name'), call.get('arguments')
    if not isinstance(args, dict):
        return None
    if name in ('set_volume', 'set_brightness'):
        noun = 'volume' if name == 'set_volume' else 'brightness'
        value = args.get('value')
        if (set(args) != {'value'} or type(value) is not int or noun not in text
                or value not in _numbers(text) or not (0 if noun == 'volume' else 1) <= value <= 100):
            return None
        return 'system_control', {'action': noun + '_set', 'value': value}
    if name in ('increase_volume', 'decrease_volume', 'increase_brightness', 'decrease_brightness'):
        if args:
            return None
        direction = 'up' if name.startswith('increase') else 'down'
        name = 'change_volume' if name.endswith('volume') else 'change_brightness'
        args = {'direction': direction}
    if name in ('change_volume', 'change_brightness'):
        direction = args.get('direction')
        if set(args) != {'direction'} or direction not in ('up', 'down') or _numbers(text):
            return None
        noun = 'volume' if name == 'change_volume' else 'brightness'
        words = ({'up': r'louder|increase|raise|up', 'down': r'quieter|softer|decrease|lower|down'}
                 if noun == 'volume' else {'up': r'brighter|increase|raise|up', 'down': r'dimmer|decrease|lower|down'})
        if not re.search(r'\b(' + words[direction] + r')\b', text):
            return None
        target = (r'volume|sound|audio|speaker|louder|quieter|softer' if noun == 'volume'
                  else r'brightness|screen|display|brighter|dimmer')
        if not re.search(r'\b(' + target + r')\b', text):
            return None
        return 'system_control', {'action': noun + '_adjust', 'value': 5 if direction == 'up' else -5}
    if name == 'switch_workspace':
        value = args.get('workspace')
        if (set(args) == {'workspace'} and type(value) is int and 1 <= value <= 10
                and value in _numbers(text) and 'workspace' in text):
            return 'system_control', {'action': 'workspace_switch', 'workspace': str(value)}
    if name == 'open_application' and set(args) == {'app'} and isinstance(args['app'], str):
        if not re.search(r'\b(open|launch|start)\b', text):
            return None
        for alias, identity in apps.items():
            if identity == args['app'] and re.search(r'\b' + re.escape(alias) + r'\b', text):
                return 'launch_app', {'app': identity}
    return None


class NeedleRouter:
    def __init__(self, config):
        self.config = config
        self.process = None
        self.ready = False
        self.error = ''
        self.last_inference_ms = None
        self.apps = {}
        self._lock = asyncio.Lock()

    async def start(self, apps):
        self.apps = dict(apps)
        if not self.config.needle_enabled:
            return
        root = Path(os.environ.get('JARVIS_NEEDLE_HOME', Path.home() / '.local/share/universal-voice/needle'))
        if not all((root / name).exists() for name in ('python/needle', 'needle3.cact', 'libneedle.so')):
            self.error = 'Needle runtime is not installed'
            return
        env = dict(os.environ, PYTHONPATH=str(root / 'python'), JARVIS_NEEDLE_HOME=str(root),
                   NEEDLE3_LIB_PATH=str(root / 'libneedle.so'), NEEDLE_TELEMETRY='0', DO_NOT_TRACK='1',
                   HF_HUB_OFFLINE='1', OMP_NUM_THREADS='2', OPENBLAS_NUM_THREADS='1')
        try:
            self.process = await asyncio.create_subprocess_exec(
                sys.executable, str(Path(__file__).with_name('needle_worker.py')),
                stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL, env=env, limit=1048576)
            self.process.stdin.write((json.dumps({'tools': schemas(apps)}) + '\n').encode())
            await self.process.stdin.drain()
            self.ready = json.loads(await asyncio.wait_for(self.process.stdout.readline(), 15)).get('ready') is True
            if not self.ready:
                raise RuntimeError('Needle initialization failed')
            self.error = ''
        except asyncio.CancelledError:
            await self.close()
            raise
        except Exception as error:
            await self.close()
            self.error = type(error).__name__

    async def route(self, text):
        if not self.ready or not text or not eligible_text(text):
            return None
        async with self._lock:
            try:
                async with asyncio.timeout(self.config.needle_timeout):
                    candidates = sorted({identity for alias, identity in self.apps.items()
                                         if re.search(r'\b' + re.escape(alias) + r'\b', normalize(text))})
                    self.process.stdin.write((json.dumps({'text': text, 'app_candidates': candidates}) + '\n').encode())
                    await self.process.stdin.drain()
                    result = json.loads(await self.process.stdout.readline())
                self.last_inference_ms = result.get('elapsed_ms')
                return validate_prediction(result, text, self.apps, self.config.needle_minimum_confidence)
            except asyncio.CancelledError:
                await self.close()
                raise
            except Exception as error:
                await self.close()
                self.error = type(error).__name__
                return None

    async def synthesize(self, text):
        if not self.ready:
            return None
        async with self._lock:
            try:
                async with asyncio.timeout(3):
                    self.process.stdin.write((json.dumps({'speak': text}) + '\n').encode())
                    await self.process.stdin.drain()
                    result = json.loads(await self.process.stdout.readline())
                pcm = base64.b64decode(result['pcm'], validate=True)
                return pcm if 0 < len(pcm) <= 48000 * 10 and len(pcm) % 2 == 0 else None
            except asyncio.CancelledError:
                await self.close()
                raise
            except Exception as error:
                await self.close()
                self.error = type(error).__name__
                return None

    async def maintain(self):
        while True:
            await asyncio.sleep(30)
            if self.config.needle_enabled and not self.ready:
                await self.start(self.apps)

    async def close(self):
        self.ready = False
        process, self.process = self.process, None
        if process is not None:
            if process.returncode is None:
                process.kill()
            await process.wait()
