"""Probe configured Gemini credentials without printing secrets or error bodies."""
import asyncio
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from connectors.credentials import read_env
from google import genai
from orchestration.model_routes import ROUTES


async def main():
    env = read_env(Path(__file__).resolve().parents[1] / '.env')
    names = ['GEMINI_API_KEY', *(f'GEMINI_API_KEY_{i}' for i in range(1, 21))]
    keys = {name: (os.environ.get(name) or env.get(name)) for name in names
            if os.environ.get(name) or env.get(name)}
    if not keys:
        print(json.dumps({'error': 'No configured Gemini API key'}))
        return
    models = sys.argv[1:] or ['gemini-3.5-flash-lite']
    for name, key in keys.items():
        status = 'working'
        code = None
        try:
            async with genai.Client(api_key=key).aio as client:
                for model in models:
                    try:
                        response = await asyncio.wait_for(client.models.generate_content(
                            model=model, contents='Reply with OK.',
                            config={'max_output_tokens': 16}), 20)
                        if not response.text:
                            status = 'empty'
                    except Exception as error:
                        code = getattr(error, 'code', None)
                        if code == 429:
                            status = 'quota_limited'
                        elif code in (400, 401, 403):
                            status = 'invalid'
                        elif isinstance(error, (TimeoutError, asyncio.TimeoutError)):
                            status = 'timeout'
                        else:
                            status = 'error'
                        break
        except Exception as error:
            code = getattr(error, 'code', None)
            status = 'invalid' if code in (400, 401, 403) else 'error'
        print(json.dumps({'key': name, 'status': status, 'code': code}), flush=True)

    if sys.argv[1:]:
        return
    # Probe the selected key for route diagnostics after the credential sweep.
    key = next(iter(keys.values()))
    async with genai.Client(api_key=key).aio as client:
        for model in list(dict.fromkeys(m for chain in ROUTES.values() for m in chain)):
            try:
                response = await asyncio.wait_for(client.models.generate_content(
                    model=model, contents='Reply with OK.',
                    config={'max_output_tokens': 128}), 25)
                print(json.dumps({'model': model, 'status': 'ok' if response.text else 'empty'}), flush=True)
            except Exception as error:
                print(json.dumps({'model': model, 'status': 'failed',
                                  'type': type(error).__name__,
                                  'code': getattr(error, 'code', None)}), flush=True)
        for model in ('gemini-3.8-live', 'gemini-3.1-flash-live-preview'):
            try:
                async with asyncio.timeout(20):
                    async with client.live.connect(model=model, config={'response_modalities': ['AUDIO']}):
                        print(json.dumps({'model': model, 'status': 'connected'}), flush=True)
            except Exception as error:
                print(json.dumps({'model': model, 'status': 'failed',
                                  'type': type(error).__name__,
                                  'code': getattr(error, 'code', None)}), flush=True)


if __name__ == '__main__':
    asyncio.run(main())
