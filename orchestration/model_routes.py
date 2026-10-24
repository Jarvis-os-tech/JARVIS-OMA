"""Bounded text reasoning jobs, independent of the Live voice session."""
import asyncio
import os
import uuid


ROUTES = {
    'fast': ('gemini-3.5-flash-lite', 'gemini-3.1-flash-lite'),
    'background': ('gemini-3.6-flash', 'gemini-3.8-flash'),
    'reasoning': ('gemini-4-argon', 'gemini-3.6-flash'),
}


class ModelJobs:
    def __init__(self, keys, events, generate=None):
        self.keys = keys
        self.events = events
        self.jobs = {}
        self.workers = {}
        self.generate = generate

    def start(self, prompt, route):
        if route not in ROUTES or not isinstance(prompt, str) or not 1 <= len(prompt.strip()) <= 24000:
            raise ValueError('Choose fast, background or reasoning and a prompt of 1–24000 characters')
        if len(self.workers) >= 2:
            raise ValueError('Two model jobs are already running')
        if len(self.jobs) >= 100:
            for old in list(self.jobs):
                if old not in self.workers:
                    del self.jobs[old]
                    break
        key = 'model-' + uuid.uuid4().hex[:12]
        self.jobs[key] = {'id': key, 'route': route, 'status': 'queued'}
        self.workers[key] = asyncio.create_task(self._run(key, prompt.strip()))
        return dict(self.jobs[key])

    async def _run(self, key, prompt):
        job = self.jobs[key]
        job['status'] = 'running'
        try:
            models = ROUTES[job['route']]
            override = os.environ.get('JARVIS_' + job['route'].upper() + '_MODEL')
            if override:
                models = (override, *tuple(m for m in models if m != override))[:2]
            for index, model in enumerate(models):
                job['model'] = model
                try:
                    text = await asyncio.wait_for(self._generate(model, prompt), 60)
                    if not text or not text.strip():
                        raise ValueError('Empty model response')
                    job.update(status='completed', result=text[:16000])
                    break
                except Exception as error:
                    code = getattr(error, 'code', None)
                    retryable = isinstance(error, (TimeoutError, OSError)) or code in (404, 429, 500, 502, 503, 504)
                    if not retryable or index == len(models) - 1:
                        raise
        except asyncio.CancelledError:
            job['status'] = 'cancelled'
            raise
        except Exception as error:
            job.update(status='failed', error=type(error).__name__)
        finally:
            self.workers.pop(key, None)
            if self.events.full():
                self.events.get_nowait()
            self.events.put_nowait(dict(job))

    async def _generate(self, model, prompt):
        if self.generate is not None:
            return await self.generate(model, prompt)
        from google import genai
        keys = self.keys if isinstance(self.keys, (list, tuple)) else [self.keys]
        if not keys or not keys[0]:
            raise ValueError('Gemini API key unavailable')
        async with genai.Client(api_key=keys[0]).aio as client:
            response = await client.models.generate_content(
                model=model, contents=prompt,
                config={'max_output_tokens': 4096, 'system_instruction':
                        'Provide analysis only. You have no execution tools. Never claim computer actions were performed.'})
            return response.text

    async def close(self):
        tasks = list(self.workers.values())
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
