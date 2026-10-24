"""Phone disconnects must not end the live conversation or strand listeners."""
import asyncio
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from connectors.phone import PhoneConnector
from core.agent import LiveVoice, supervise


class PhoneMonitorTests(unittest.IsolatedAsyncioTestCase):
    async def test_listener_exception_and_eof_recover_without_cancelling_audio(self):
        recovered = asyncio.Event()
        audio_started = asyncio.Event()
        audio_stopped = asyncio.Event()
        calls = 0
        retry_delays = []
        stop_events = []
        real_sleep = asyncio.sleep

        async def audio():
            audio_started.set()
            try:
                await asyncio.Event().wait()
            finally:
                audio_stopped.set()

        async def listen(callback, stop_event):
            nonlocal calls
            calls += 1
            stop_events.append(stop_event)
            if calls == 1:
                raise OSError('D-Bus unavailable')
            if calls == 2:
                return  # A monitor process exiting normally is also a disconnect.
            await callback({'call_path': '/test/call', 'name': 'Test caller'})
            recovered.set()
            await asyncio.Event().wait()

        async def retry(delay):
            retry_delays.append(delay)
            await real_sleep(0)

        voice = LiveVoice(None, skills=SimpleNamespace(
            phone=SimpleNamespace(listen_for_calls=listen)))
        with patch('core.agent.asyncio.sleep', side_effect=retry):
            supervisor = asyncio.create_task(supervise(audio(), voice.monitor_phone_calls()))
            try:
                await asyncio.wait_for(recovered.wait(), 1)
                self.assertTrue(audio_started.is_set())
                self.assertFalse(audio_stopped.is_set())
                self.assertFalse(supervisor.done())
                self.assertEqual(retry_delays, [1, 2])
                self.assertEqual(len(voice._notices), 1)
            finally:
                supervisor.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await supervisor
        self.assertTrue(audio_stopped.is_set())
        self.assertTrue(all(event.is_set() for event in stop_events))

    async def test_missing_phone_connector_keeps_optional_worker_alive(self):
        for skills in (None, SimpleNamespace()):
            with self.subTest(skills=skills):
                voice = LiveVoice(None, skills=skills)
                monitor = asyncio.create_task(voice.monitor_phone_calls())
                try:
                    await asyncio.sleep(0)
                    self.assertFalse(monitor.done())
                finally:
                    monitor.cancel()
                    with self.assertRaises(asyncio.CancelledError):
                        await monitor

    async def test_phone_connector_stays_dormant_until_requested(self):
        requested = asyncio.Event()
        listener = AsyncMock()
        skills = SimpleNamespace(
            phone_service_requested=requested,
            phone=SimpleNamespace(listen_for_calls=listener),
        )
        voice = LiveVoice(None, skills=skills)
        monitor = asyncio.create_task(voice.monitor_phone_calls())
        try:
            await asyncio.sleep(0)
            listener.assert_not_awaited()
            requested.set()
            await asyncio.sleep(0)
            listener.assert_awaited_once()
        finally:
            monitor.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await monitor

    async def test_connected_phone_automatically_starts_listener(self):
        requested = asyncio.Event()
        listening = asyncio.Event()

        async def listen(callback, stop_event):
            listening.set()
            await stop_event.wait()

        phone = SimpleNamespace(
            get_gateways=AsyncMock(return_value=['/org/pipewire/Telephony/ag0']),
            listen_for_calls=listen,
        )
        skills = SimpleNamespace(
            phone_service_requested=requested,
            get_phone_connector=MagicMock(return_value=phone),
        )
        voice = LiveVoice(None, skills=skills)
        monitor = asyncio.create_task(voice.monitor_phone_calls())
        try:
            await asyncio.wait_for(listening.wait(), 1)
            phone.get_gateways.assert_awaited_once()
            skills.get_phone_connector.assert_called_with(activate=False)
            self.assertFalse(requested.is_set())
        finally:
            monitor.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await monitor

    async def test_disconnected_phone_sleeps_without_starting_listener(self):
        requested = asyncio.Event()
        requested.set()
        phone = SimpleNamespace(
            get_gateways=AsyncMock(return_value=[]),
            listen_for_calls=AsyncMock(),
        )
        skills = SimpleNamespace(
            phone_service_requested=requested,
            get_phone_connector=MagicMock(return_value=phone),
        )
        voice = LiveVoice(None, skills=skills)
        monitor = asyncio.create_task(voice.monitor_phone_calls())
        try:
            await asyncio.sleep(0)
            await asyncio.sleep(0)
            phone.get_gateways.assert_awaited_once()
            phone.listen_for_calls.assert_not_awaited()
            self.assertFalse(requested.is_set())
            self.assertFalse(monitor.done())
        finally:
            monitor.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await monitor

    async def test_shutdown_during_retry_does_not_restart_listener(self):
        retry_started = asyncio.Event()
        listener = AsyncMock(side_effect=OSError('offline'))

        async def retry(delay):
            retry_started.set()
            await asyncio.Event().wait()

        voice = LiveVoice(None, skills=SimpleNamespace(
            phone=SimpleNamespace(listen_for_calls=listener)))
        with patch('core.agent.asyncio.sleep', side_effect=retry):
            monitor = asyncio.create_task(voice.monitor_phone_calls())
            try:
                await asyncio.wait_for(retry_started.wait(), 1)
            finally:
                monitor.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await monitor
        self.assertEqual(listener.await_count, 1)
        self.assertTrue(listener.await_args.kwargs['stop_event'].is_set())

    async def test_connector_cancellation_reaps_process_and_propagates(self):
        reading = asyncio.Event()

        async def readline():
            reading.set()
            await asyncio.Event().wait()

        process = MagicMock(returncode=None)
        process.stdout.readline = AsyncMock(side_effect=readline)
        process.wait = AsyncMock(return_value=-9)
        with patch('connectors.phone.asyncio.create_subprocess_exec', return_value=process):
            listener = asyncio.create_task(PhoneConnector().listen_for_calls(
                AsyncMock(), asyncio.Event()))
            try:
                await asyncio.wait_for(reading.wait(), 1)
            finally:
                listener.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await listener
        process.kill.assert_called_once()
        process.wait.assert_awaited_once()

    async def test_connector_eof_reaps_exited_process(self):
        process = MagicMock(returncode=1)
        process.stdout.readline = AsyncMock(return_value=b'')
        process.wait = AsyncMock(return_value=1)
        with patch('connectors.phone.asyncio.create_subprocess_exec', return_value=process):
            await PhoneConnector().listen_for_calls(AsyncMock(), asyncio.Event())
        process.kill.assert_not_called()
        process.wait.assert_awaited_once()
