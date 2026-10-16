"""Offline concurrency and shutdown checks for serial synchronous workers."""
import asyncio
import threading
import unittest

from core.workers import BoundedWorker, WorkerBusyError, WorkerClosedError, WorkerShutdownError


class WorkerTests(unittest.IsolatedAsyncioTestCase):
    async def wait_started(self, event):
        async with asyncio.timeout(2):
            while not event.is_set():
                await asyncio.sleep(.001)

    async def test_serial_thread_affinity_and_exception_propagation(self):
        worker = BoundedWorker('test-affinity')
        try:
            first, second = await asyncio.gather(
                worker.run(threading.get_ident), worker.run(threading.get_ident))
            self.assertEqual(first, second)
            self.assertNotEqual(first, threading.get_ident())
            def fail():
                raise ValueError('job failed')
            with self.assertRaisesRegex(ValueError, 'job failed'):
                await worker.run(fail)
            self.assertEqual(await worker.run(lambda: 42), 42)
        finally:
            await worker.close()

    async def test_canceled_running_job_retains_capacity_and_loop_is_responsive(self):
        worker = BoundedWorker('test-running', capacity=1)
        started, release = threading.Event(), threading.Event()
        def block():
            started.set()
            release.wait(3)
        task = asyncio.create_task(worker.run(block))
        try:
            await self.wait_started(started)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
            with self.assertRaises(WorkerBusyError):
                await worker.run(lambda: None)
            # Reaching this coroutine while block() is waiting demonstrates
            # that synchronous work did not occupy the event-loop thread.
            await asyncio.sleep(.005)
            self.assertFalse(release.is_set())
        finally:
            release.set()
            await worker.close()

    async def test_queued_cancellation_prevents_execution_and_releases_capacity(self):
        worker = BoundedWorker('test-queued', capacity=2)
        started, release, called = threading.Event(), threading.Event(), threading.Event()
        def block():
            started.set()
            release.wait(3)
        first = asyncio.create_task(worker.run(block))
        queued = None
        try:
            await self.wait_started(started)
            queued = asyncio.create_task(worker.run(called.set))
            await asyncio.sleep(0)
            queued.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await queued
            replacement = asyncio.create_task(worker.run(lambda: 'replacement'))
            await asyncio.sleep(0)
            release.set()
            self.assertEqual(await replacement, 'replacement')
            await first
            self.assertFalse(called.is_set())
        finally:
            release.set()
            await worker.close()
            await asyncio.gather(first, *([queued] if queued else []), return_exceptions=True)

    async def test_shutdown_timeout_retains_finalizer_order_and_repeated_close(self):
        worker = BoundedWorker('test-close', capacity=2)
        started, release = threading.Event(), threading.Event()
        records = []
        def block():
            started.set()
            release.wait(3)
            records.append(('job', threading.get_ident()))
        task = asyncio.create_task(worker.run(block))
        await self.wait_started(started)
        queued = asyncio.create_task(worker.run(lambda: records.append(('canceled', 0))))
        await asyncio.sleep(0)
        def finalizer():
            records.append(('finalizer', threading.get_ident()))
        try:
            with self.assertRaises(WorkerShutdownError):
                await worker.close(finalizer, timeout=.01)
            with self.assertRaises(WorkerClosedError):
                await worker.run(lambda: None)
            self.assertEqual(records, [])
        finally:
            release.set()
            await worker.close(lambda: records.append(('wrong-finalizer', 0)))
            await asyncio.gather(task, queued, return_exceptions=True)
        self.assertEqual([item[0] for item in records], ['job', 'finalizer'])
        self.assertEqual(records[0][1], records[1][1])
        await worker.close()

    async def test_close_cancellation_does_not_cancel_cleanup(self):
        worker = BoundedWorker('test-close-cancel')
        started, release, finalized = threading.Event(), threading.Event(), threading.Event()
        def block():
            started.set()
            release.wait(3)
        job = asyncio.create_task(worker.run(block))
        await self.wait_started(started)
        closer = asyncio.create_task(worker.close(finalized.set))
        await asyncio.sleep(.005)
        closer.cancel()
        try:
            with self.assertRaises(asyncio.CancelledError):
                await closer
        finally:
            release.set()
            await worker.close()
            await job
        self.assertTrue(finalized.is_set())

    async def test_lazy_close_and_finalizer_errors(self):
        worker = BoundedWorker('test-unused')
        self.assertIsNone(worker._executor)
        await worker.close()
        await worker.close()
        self.assertIsNone(worker._executor)
        with self.assertRaises(WorkerClosedError):
            await worker.run(lambda: None)
        failing = BoundedWorker('test-finalizer')
        def fail():
            raise ValueError('cleanup failed')
        with self.assertRaisesRegex(ValueError, 'cleanup failed'):
            await failing.close(fail)
        with self.assertRaisesRegex(ValueError, 'cleanup failed'):
            await failing.close()
