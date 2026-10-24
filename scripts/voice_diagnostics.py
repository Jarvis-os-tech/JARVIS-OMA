"""Metadata-only voice diagnostics: no microphone recordings are persisted."""
from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


async def provider_test():
    from google import genai
    from google.genai import types
    from core.config import load_config
    names = ['GEMINI_API_KEY', *(f'GEMINI_API_KEY_{i}' for i in range(1, 21))]
    key = next((os.environ[name] for name in names if os.environ.get(name)), '')
    if not key:
        for line in (Path(__file__).resolve().parents[1] / '.env').read_text().splitlines():
            name, sep, value = line.strip().partition('=')
            if sep and name in names:
                key = value.strip().strip('"').strip("'")
                break
    if not key:
        raise RuntimeError('No Gemini key configured')
    config = load_config()
    started = time.monotonic()
    pcm_bytes = 0
    first_audio = None
    async with asyncio.timeout(25), genai.Client(api_key=key).aio as client:
        async with client.live.connect(model=config.agent.model, config={
                'response_modalities': ['AUDIO'],
                'speech_config': {'voice_config': {'prebuilt_voice_config': {
                    'voice_name': config.agent.voice}}}}) as session:
            await session.send_client_content(turns=types.Content(role='user', parts=[
                types.Part(text='Say exactly: Jarvis is ready.')]), turn_complete=True)
            async for event in session.receive():
                content = event.server_content
                if content and content.model_turn:
                    for part in content.model_turn.parts or []:
                        if part.inline_data and part.inline_data.data:
                            pcm_bytes += len(part.inline_data.data)
                            if first_audio is None:
                                first_audio = round(time.monotonic() - started, 3)
                if content and content.turn_complete:
                    break
    return {'test': 'provider_text_to_audio', 'pcm_bytes': pcm_bytes,
            'first_audio_seconds': first_audio}


async def levels(source, sink, seconds):
    from audio.plugins.native_backend import NativeCompanionEngine
    engine = NativeCompanionEngine()
    maximum = 0.0
    frames = 0
    try:
        engine.start(source, sink)
        await engine.wait_ready(source, sink)
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            async with asyncio.timeout(2):
                await engine.async_input_queue.get()
            maximum = max(maximum, engine.input_rms)
            frames += 1
        return {'test': 'microphone_levels', 'source': source, 'frames': frames,
                'maximum_rms': round(maximum, 6), 'links_verified': engine._aec_input_bound}
    finally:
        await engine.aclose()


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('test', choices=['provider', 'levels', 'service'])
    parser.add_argument('--source')
    parser.add_argument('--sink')
    parser.add_argument('--compare-source')
    parser.add_argument('--seconds', type=float, default=4)
    args = parser.parse_args()
    if args.test == 'levels' and (not args.source or not args.sink or not 0 < args.seconds <= 30):
        parser.error('levels requires --source, --sink and 0 < seconds <= 30')
    try:
        if args.test == 'provider':
            result = await provider_test()
        elif args.test == 'service':
            from scripts.jarvisctl import send_command, default_socket_path
            result = await send_command(default_socket_path(), {'command': 'test_voice'})
        elif args.compare_source:
            result = await asyncio.gather(levels(args.source, args.sink, args.seconds),
                                          levels(args.compare_source, args.sink, args.seconds))
        else:
            result = await levels(args.source, args.sink, args.seconds)
        print(json.dumps(result))
    except Exception as error:
        # SDK exception strings can contain sensitive response details.
        code = getattr(error, 'code', None)
        print(json.dumps({'error_type': type(error).__name__, 'code': code if isinstance(code, int) else None}))
        raise SystemExit(1) from None


if __name__ == '__main__':
    asyncio.run(main())
