"""Persistence contention and reconnect cancellation must not stall voice I/O."""
import asyncio
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import patch

from proactive.events import EventStatus
from proactive.runtime import ProactiveRuntime


class FakeOrchestrator:
    def __init__(self):
        self.jobs, self.workers, self.calls = {}, {}, []

    def delegate(self, agent, prompt, workspace, timeout):
        self.calls.append(threading.get_ident())
        key = f'job-{len(self.calls)}'
        self.jobs[key] = {'id': key, 'state': 'running'}
        return {'job': {'id': key}}

    async def cancel(self, key):
        self.jobs[key]['state'] = 'cancelled'


class RuntimeWorkerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.orchestrator = FakeOrchestrator()
        self.runtime = ProactiveRuntime(Path(self.tmp.name) / 'state', self.orchestrator)
        self.addAsyncCleanup(self.runtime.close)

    async def test_sqlite_write_contention_does_not_block_event_loop(self):
        connection = sqlite3.connect(self.runtime.bus.path, check_same_thread=False)
        connection.execute('BEGIN IMMEDIATE')
        entered, released = threading.Event(), threading.Event()
        original_claim = self.runtime.bus.claim
        beats = []

        def claim(**kwargs):
            entered.set()
            return original_claim(**kwargs)

        def release():
            connection.rollback()
            released.set()

        async def heartbeat():
            while not released.is_set():
                if entered.is_set():
                    beats.append(True)
                await asyncio.sleep(.005)

        timer = threading.Timer(.25, release)
        timer.start()
        heartbeat_task = asyncio.create_task(heartbeat())
        try:
            with patch.object(self.runtime.bus, 'claim', side_effect=claim):
                await self.runtime.tick()
            await heartbeat_task
            self.assertGreaterEqual(len(beats), 3)
        finally:
            timer.join()
            connection.close()
            if not heartbeat_task.done():
                heartbeat_task.cancel()
                await asyncio.gather(heartbeat_task, return_exceptions=True)

    async def test_cancelled_observer_retains_claim_and_single_dispatch(self):
        queued = await self.runtime.call('enqueue', 'Implement parser', self.tmp.name, authorized=True)
        entered, release = threading.Event(), threading.Event()
        original_claim = self.runtime.bus.claim
        count = []

        def claim(**kwargs):
            count.append(True)
            entered.set()
            if not release.wait(2):
                raise RuntimeError('test did not release claim')
            return original_claim(**kwargs)

        with patch.object(self.runtime.bus, 'claim', side_effect=claim):
            first = asyncio.create_task(self.runtime.tick())
            while not entered.is_set():
                await asyncio.sleep(.005)
            first.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await first
            second = asyncio.create_task(self.runtime.tick())
            await asyncio.sleep(0)
            release.set()
            result = await second
        self.assertEqual(len(count), 1)
        self.assertEqual(result['results'][0]['status'], 'delegated')
        self.assertEqual(self.orchestrator.calls, [threading.get_ident()])
        event = await self.runtime.call(self.runtime.bus.get, queued['event_id'])
        self.assertEqual(event.status, EventStatus.COMPLETED)

    async def test_close_timeout_preserves_inflight_tick_before_worker_close(self):
        entered, release = threading.Event(), threading.Event()
        original_claim = self.runtime.bus.claim

        def claim(**kwargs):
            entered.set()
            if not release.wait(2):
                raise RuntimeError('test did not release claim')
            return original_claim(**kwargs)

        with patch.object(self.runtime.bus, 'claim', side_effect=claim):
            task = asyncio.create_task(self.runtime.tick())
            while not entered.is_set():
                await asyncio.sleep(.005)
            try:
                with self.assertRaises(TimeoutError):
                    await self.runtime.close(timeout=.01)
                with self.assertRaisesRegex(RuntimeError, 'closing'):
                    await self.runtime.tick()
                with self.assertRaisesRegex(RuntimeError, 'closing'):
                    await self.runtime.call('status')
            finally:
                release.set()
            self.assertEqual((await task)['status'], 'active')
            await self.runtime.close()
