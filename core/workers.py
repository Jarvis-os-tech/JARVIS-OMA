"""Bounded, serial ownership for synchronous resources used by async callers."""
from __future__ import annotations

import asyncio
from concurrent.futures import Future, ThreadPoolExecutor
import threading
import time


class WorkerBusyError(RuntimeError):
    """The worker already owns its maximum number of outstanding jobs."""


class WorkerClosedError(RuntimeError):
    """The worker is shutting down and cannot accept another job."""


class WorkerShutdownError(TimeoutError):
    """Shutdown is still pending; calling close again will resume waiting."""


class BoundedWorker:
    """Run synchronous jobs serially, retaining ownership after cancellation.

    Capacity includes running and queued jobs. Cancellation can remove a queued
    job, but a running callable keeps its slot until it actually returns.
    """

    def __init__(self, name, capacity=16):
        if type(capacity) is not int or capacity < 1:
            raise ValueError('capacity must be a positive integer')
        self.name = name
        self.capacity = capacity
        self._lock = threading.RLock()
        self._executor = None
        self._jobs: set[Future] = set()
        self._closed = False
        self._shutdown_task = None

    def _get_executor(self):
        if self._executor is None:
            self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix=self.name)
        return self._executor

    def _finished(self, job):
        with self._lock:
            self._jobs.discard(job)

    async def run(self, fn, *args, **kwargs):
        with self._lock:
            if self._closed:
                raise WorkerClosedError(f'{self.name} is closed')
            if len(self._jobs) >= self.capacity:
                raise WorkerBusyError(f'{self.name} capacity ({self.capacity}) is full')
            job = self._get_executor().submit(fn, *args, **kwargs)
            self._jobs.add(job)
            job.add_done_callback(self._finished)
        try:
            wrapped = asyncio.wrap_future(job)
            while not wrapped.done():
                try:
                    await asyncio.wait_for(asyncio.shield(wrapped), .05)
                except asyncio.TimeoutError:
                    continue
            return wrapped.result()
        except asyncio.CancelledError:
            # Explicitly cancel now: wrap_future's cancellation propagation can
            # otherwise wait until the next event-loop callback is processed.
            job.cancel()
            raise

    async def close(self, finalizer=None, timeout=5):
        """Stop accepting jobs and wait for cleanup without blocking the loop.

        Only the first close's finalizer is used. It runs on the owning thread
        after the current job; queued ordinary jobs are canceled. A timeout
        leaves shutdown owned by this instance, so a later close can await it.
        """
        with self._lock:
            if self._shutdown_task is None:
                self._closed = True
                for job in tuple(self._jobs):
                    job.cancel()
                executor = self._executor
                if executor is None and finalizer is None:
                    return
                executor = self._get_executor()
                barrier = executor.submit(finalizer if finalizer is not None else lambda: None)
                # Reject submissions in the executor too, while allowing the
                # current job and the finalizer to complete in queue order.
                executor.shutdown(wait=False)

                def join():
                    executor.shutdown(wait=True)
                    return barrier.result()

                loop = asyncio.get_running_loop()
                done = loop.create_future()

                def finish_join():
                    try:
                        result = join()
                    except BaseException as error:
                        loop.call_soon_threadsafe(done.set_exception, error)
                    else:
                        loop.call_soon_threadsafe(done.set_result, result)

                threading.Thread(target=finish_join, name=f'{self.name}-shutdown',
                                 daemon=True).start()
                self._shutdown_task = done
                # Retrieve eventual failures even if every waiting caller is
                # canceled or times out. Awaiting the task still raises them.
                self._shutdown_task.add_done_callback(
                    lambda task: None if task.cancelled() else task.exception())
            shutdown = self._shutdown_task
        try:
            deadline = time.monotonic() + timeout
            while not shutdown.done():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise asyncio.TimeoutError()
                try:
                    await asyncio.wait_for(asyncio.shield(shutdown), min(.05, remaining))
                except asyncio.TimeoutError:
                    continue
            shutdown.result()
        except asyncio.TimeoutError as error:
            # A finalizer can itself raise TimeoutError. Preserve that error
            # when shutdown finished, rather than describing it as pending.
            if shutdown.done():
                return shutdown.result()
            raise WorkerShutdownError(f'{self.name} shutdown is still pending') from error
