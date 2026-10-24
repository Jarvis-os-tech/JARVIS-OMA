import asyncio
import unittest
from orchestration.model_routes import ModelJobs


class RoutingTests(unittest.IsolatedAsyncioTestCase):
    async def test_transient_failure_uses_fallback_and_publishes_result(self):
        calls = []
        async def generate(model, prompt):
            calls.append(model)
            if len(calls) == 1:
                raise TimeoutError()
            return 'Verified analysis'
        events = asyncio.Queue()
        jobs = ModelJobs(None, events, generate)
        item = jobs.start('Analyze', 'reasoning')
        event = await asyncio.wait_for(events.get(), 1)
        self.assertEqual(event['id'], item['id'])
        self.assertEqual(event['status'], 'completed')
        self.assertEqual(calls, ['gemini-4-argon', 'gemini-3.6-flash'])

    async def test_background_job_returns_immediately_and_shutdown_cancels(self):
        async def generate(model, prompt):
            await asyncio.Event().wait()
        jobs = ModelJobs(None, asyncio.Queue(), generate)
        item = jobs.start('Analyze', 'background')
        await asyncio.sleep(0)
        self.assertEqual(jobs.jobs[item['id']]['status'], 'running')
        await jobs.close()
        self.assertEqual(jobs.jobs[item['id']]['status'], 'cancelled')
        self.assertFalse(jobs.workers)

    async def test_permanent_failure_does_not_retry(self):
        calls = []
        async def generate(model, prompt):
            calls.append(model)
            raise ValueError('bad configuration')
        events = asyncio.Queue()
        jobs = ModelJobs(None, events, generate)
        jobs.start('Analyze', 'fast')
        event = await asyncio.wait_for(events.get(), 1)
        self.assertEqual(event['status'], 'failed')
        self.assertEqual(len(calls), 1)
