"""Bounded delivery and shutdown behavior for IPC state subscribers."""
import asyncio
import json
import tempfile
import unittest
from pathlib import Path

from core.ipc import JarvisIPCServer, _Subscriber


class _SlowWriter:
    def __init__(self):
        self.writes = []
        self.closed = False
        self.drain_started = asyncio.Event()
        self.release_drain = asyncio.Event()
        self.wait_closed_calls = 0

    def write(self, data):
        self.writes.append(data)

    async def drain(self):
        self.drain_started.set()
        await self.release_drain.wait()

    def close(self):
        self.closed = True

    async def wait_closed(self):
        self.wait_closed_calls += 1


class TestIPCBackpressure(unittest.IsolatedAsyncioTestCase):
    async def test_shutdown_closes_client_waiting_for_first_command(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            server = JarvisIPCServer(socket_path=Path(temp_dir) / 'idle.sock')
            await server.start()
            reader, writer = await asyncio.open_unix_connection(str(server.socket_path))
            try:
                # Let the handler register this accepted connection.
                await asyncio.sleep(0)
                await asyncio.wait_for(server.close(), 2)
                self.assertEqual(await asyncio.wait_for(reader.read(), 1), b'')
            finally:
                writer.close()
                await writer.wait_closed()
                await server.close()

    async def test_real_socket_subscriber_receives_state_and_shutdown_closes_it(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            socket_path = Path(temp_dir) / "ipc.sock"
            server = JarvisIPCServer(socket_path=socket_path)
            await server.start()
            reader, writer = await asyncio.open_unix_connection(str(socket_path))
            try:
                writer.write(b'{"command":"subscribe"}\n')
                await writer.drain()
                initial = json.loads((await asyncio.wait_for(reader.readline(), 1)).decode())
                self.assertEqual(initial["event"], "state_change")

                server.broadcast_state({"state": "speaking"})
                event = json.loads((await asyncio.wait_for(reader.readline(), 1)).decode())
                self.assertEqual(event, {"event": "state_change", "state": "speaking"})

                await asyncio.wait_for(server.close(), 2)
                self.assertEqual(server._subscribers, {})
                self.assertEqual(await asyncio.wait_for(reader.readline(), 1), b"")
            finally:
                writer.close()
                await writer.wait_closed()
                await server.close()

    async def test_slow_writer_is_evicted_when_bounded_queue_fills(self):
        server = JarvisIPCServer(subscriber_queue_size=2, subscriber_drain_timeout=5)
        slow_writer = _SlowWriter()
        subscriber = _Subscriber(slow_writer, asyncio.Queue(maxsize=2))
        server._subscribers[slow_writer] = subscriber
        subscriber.sender_task = asyncio.create_task(server._send_subscriber_events(subscriber))
        server._sender_tasks.add(subscriber.sender_task)
        subscriber.sender_task.add_done_callback(server._sender_tasks.discard)

        server.broadcast_state({"sequence": 0})
        await asyncio.wait_for(slow_writer.drain_started.wait(), 1)
        # The sender is blocked in drain. Two queued events fit; the next one
        # immediately evicts the slow writer without waiting in broadcast_state.
        server.broadcast_state({"sequence": 1})
        server.broadcast_state({"sequence": 2})
        server.broadcast_state({"sequence": 3})

        self.assertEqual(server._subscribers, {})
        self.assertTrue(slow_writer.closed)
        await server.close()
        self.assertTrue(subscriber.sender_task.done())
        self.assertGreaterEqual(slow_writer.wait_closed_calls, 1)

    async def test_oversized_event_is_skipped_without_evicting_subscribers(self):
        server = JarvisIPCServer(max_event_bytes=80)
        slow_writer = _SlowWriter()
        subscriber = _Subscriber(slow_writer, asyncio.Queue(maxsize=2))
        server._subscribers[slow_writer] = subscriber

        server.broadcast_state({"state": "x" * 200})

        self.assertIn(slow_writer, server._subscribers)
        self.assertEqual(subscriber.queue.qsize(), 0)
        self.assertFalse(slow_writer.closed)

    async def test_stalled_drain_times_out_without_blocking_healthy_subscriber(self):
        server = JarvisIPCServer(subscriber_drain_timeout=0.02)
        slow, healthy = _SlowWriter(), _SlowWriter()
        healthy.release_drain.set()
        subscribers = []
        for writer in (slow, healthy):
            subscriber = _Subscriber(writer, asyncio.Queue(maxsize=2))
            server._subscribers[writer] = subscriber
            subscriber.sender_task = asyncio.create_task(server._send_subscriber_events(subscriber))
            server._sender_tasks.add(subscriber.sender_task)
            subscriber.sender_task.add_done_callback(server._sender_tasks.discard)
            subscribers.append(subscriber)
        try:
            server.broadcast_state({'sequence': 1})
            await asyncio.wait_for(slow.drain_started.wait(), 1)
            await asyncio.wait_for(healthy.drain_started.wait(), 1)
            await asyncio.wait_for(subscribers[0].sender_task, 1)
            self.assertNotIn(slow, server._subscribers)
            self.assertIn(healthy, server._subscribers)
            self.assertEqual(json.loads(healthy.writes[0])['sequence'], 1)
            self.assertTrue(slow.closed)
        finally:
            await asyncio.wait_for(server.close(), 1)
        self.assertFalse(server._sender_tasks)

    async def test_invalid_backpressure_limits_are_rejected(self):
        for kwargs in (
            {"subscriber_queue_size": 0},
            {"max_subscribers": 1.5},
            {"max_event_bytes": -1},
            {"subscriber_drain_timeout": float("inf")},
            {"subscriber_drain_timeout": float("nan")},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                JarvisIPCServer(**kwargs)

    async def test_subscriber_limit_bounds_sender_tasks(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            socket_path = Path(temp_dir) / "ipc.sock"
            server = JarvisIPCServer(socket_path=socket_path, max_subscribers=1)
            await server.start()
            first_reader, first_writer = await asyncio.open_unix_connection(str(socket_path))
            second_reader, second_writer = await asyncio.open_unix_connection(str(socket_path))
            try:
                first_writer.write(b'{"command":"subscribe"}\n')
                await first_writer.drain()
                await asyncio.wait_for(first_reader.readline(), 1)
                second_writer.write(b'{"command":"subscribe"}\n')
                await second_writer.drain()
                rejected = json.loads((await asyncio.wait_for(second_reader.readline(), 1)).decode())
                self.assertEqual(rejected["status"], "error")
                self.assertEqual(len(server._subscribers), 1)
            finally:
                first_writer.close()
                second_writer.close()
                await asyncio.gather(first_writer.wait_closed(), second_writer.wait_closed())
                await server.close()


if __name__ == "__main__":
    unittest.main()
