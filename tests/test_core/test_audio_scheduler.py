"""Voice transport scheduling under backlog, cancellation and failed writes."""
import asyncio
import time
from types import SimpleNamespace as NS
import unittest
from unittest.mock import AsyncMock, patch

from core.audio_scheduler import AudioSendScheduler, SendStalled, VideoFrameDropped


class AudioSchedulerTests(unittest.IsolatedAsyncioTestCase):
    async def test_short_inflight_audio_backpressure_does_not_force_reconnect(self):
        scheduler = AudioSendScheduler()
        async with scheduler.audio():
            await asyncio.sleep(.18)
        self.assertFalse(scheduler.locked())
        self.assertEqual(scheduler.timeouts, 0)
        async with scheduler:
            pass

    async def test_sustained_inflight_audio_stall_still_has_a_hard_deadline(self):
        scheduler = AudioSendScheduler(audio_budget=.01)
        with self.assertRaises(SendStalled):
            async with scheduler.audio():
                await asyncio.Event().wait()
        self.assertEqual(scheduler.timeouts, 1)
        with self.assertRaises(SendStalled):
            await scheduler.acquire()

    async def test_audio_passes_queued_controls_but_controls_remain_fifo(self):
        scheduler = AudioSendScheduler()
        await scheduler.acquire()
        order = []

        async def send(label, priority):
            async with scheduler.hold(priority):
                order.append(label)

        tasks = [asyncio.create_task(send(f'control-{i}', scheduler.CONTROL)) for i in range(3)]
        await asyncio.sleep(0)
        tasks.append(asyncio.create_task(send('audio', scheduler.AUDIO)))
        tasks.append(asyncio.create_task(send('video', scheduler.VIDEO)))
        await asyncio.sleep(0)
        scheduler.release()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        self.assertIsInstance(results[-1], VideoFrameDropped)
        self.assertEqual(order, ['audio', 'control-0', 'control-1', 'control-2'])
        self.assertEqual(scheduler.metrics()['network_send_waiters'], 0)

    async def test_video_drop_is_nonblocking_and_does_not_poison_audio(self):
        scheduler = AudioSendScheduler()
        await scheduler.acquire(scheduler.AUDIO)
        with self.assertRaises(VideoFrameDropped):
            await scheduler.acquire(scheduler.VIDEO)
        self.assertEqual(scheduler.metrics()['network_send_waiters'], 0)
        scheduler.release()
        async with scheduler.audio():
            pass
        self.assertEqual(scheduler.dropped_video_frames, 1)

    async def test_video_choke_recovers_after_audio_latency_and_backlog_clear(self):
        scheduler = AudioSendScheduler()
        scheduler._audio_waits.extend([25] * 20)
        with self.assertRaises(VideoFrameDropped):
            async with scheduler.video():
                self.fail('choked video must not write')
        scheduler._audio_waits.extend([0] * 256)
        scheduler.set_audio_backpressure(3)
        with self.assertRaises(VideoFrameDropped):
            await scheduler.acquire(scheduler.VIDEO)
        scheduler.set_audio_backpressure(0)
        async with scheduler.video():
            pass

    async def test_old_generation_video_is_dropped_but_control_and_audio_continue(self):
        scheduler = AudioSendScheduler()
        scheduler.update_generation(2)
        with self.assertRaises(VideoFrameDropped):
            async with scheduler.video(generation=1):
                self.fail('old video must not write')
        with self.assertRaises(ValueError):
            scheduler.update_generation(1)
        async with scheduler.audio(generation=2):
            pass
        async with scheduler:
            pass

    async def test_generation_interrupts_inflight_video_and_requires_clean_transport(self):
        scheduler = AudioSendScheduler()
        entered = asyncio.Event()

        async def video():
            async with scheduler.video(generation=0):
                entered.set()
                await asyncio.Event().wait()

        task = asyncio.create_task(video())
        await entered.wait()
        scheduler.update_generation(1)
        with self.assertRaises(SendStalled):
            await task
        self.assertFalse(scheduler.locked())
        scheduler.reset()
        async with scheduler.audio(generation=1):
            pass

    async def test_cancellation_before_and_after_grant_never_strands_writer(self):
        for cancel_before_release in (True, False):
            scheduler = AudioSendScheduler()
            await scheduler.acquire()
            waiter = asyncio.create_task(scheduler.acquire())
            await asyncio.sleep(0)
            if cancel_before_release:
                waiter.cancel()
                scheduler.release()  # Removes the cancelled future before its task resumes.
            else:
                scheduler.release()
                waiter.cancel()  # Cancellation races with the handoff.
            await asyncio.gather(waiter, return_exceptions=True)
            async with scheduler:
                self.assertTrue(scheduler.locked())
            self.assertFalse(scheduler.locked())

    async def test_timed_out_writer_poison_blocks_waiters_and_notifies_supervisor(self):
        scheduler = AudioSendScheduler(control_budget=.01)
        entered = asyncio.Event()
        sent = []

        async def blocked():
            async with scheduler:
                entered.set()
                await asyncio.Event().wait()

        async def audio():
            async with scheduler.audio():
                sent.append(True)

        writer = asyncio.create_task(blocked())
        await entered.wait()
        pending = asyncio.create_task(audio())
        monitor = asyncio.create_task(scheduler.monitor())
        results = await asyncio.gather(writer, pending, monitor, return_exceptions=True)
        self.assertTrue(all(isinstance(result, SendStalled) for result in results))
        self.assertEqual(sent, [])
        self.assertFalse(scheduler.locked())
        self.assertEqual(scheduler.timeouts, 1)
        scheduler.reset()
        async with scheduler.audio():
            sent.append(True)
        self.assertEqual(sent, [True])

    async def test_detached_tool_failure_is_visible_to_live_supervision(self):
        from core.agent import LiveVoice
        voice = LiveVoice(None)
        session = NS(send_tool_response=AsyncMock(side_effect=ConnectionError('disconnected')))
        task = asyncio.create_task(voice._send_tool_response(session, object()))
        voice.tool_tasks['call'] = task
        task.add_done_callback(lambda finished: voice._tool_done('call', finished))
        with self.assertLogs('gemini_voice', level='WARNING'):
            await asyncio.gather(task, return_exceptions=True)
            with self.assertRaises(SendStalled):
                await asyncio.wait_for(voice.send_lock.monitor(), 1)
        session.send_tool_response.assert_awaited_once()

    async def test_real_microphone_sender_gets_priority_over_waiting_tool_results(self):
        from core.agent import LiveVoice
        from audio.plugins.native_backend import CaptureQueue
        engine = NS(async_input_queue=CaptureQueue(), output_frame_bytes=960,
                    speaking=False, continuous_capture=True, muted=True)
        voice = LiveVoice(engine)
        order = []
        sent = asyncio.Event()

        async def send_audio(**kwargs):
            order.append('audio')
            sent.set()

        async def send_tool(**kwargs):
            order.append(kwargs['function_responses'])

        session = NS(send_realtime_input=send_audio, send_tool_response=send_tool)
        await voice.send_lock.acquire()
        controls = [asyncio.create_task(voice._send_tool_response(session, f'tool-{i}')) for i in range(3)]
        await asyncio.sleep(0)
        for _ in range(8):
            asyncio.Queue.put_nowait(engine.async_input_queue, (time.monotonic_ns(), bytes(640)))
        audio = asyncio.create_task(voice.send_audio(session))
        await asyncio.sleep(0)
        voice.send_lock.release()
        await asyncio.wait_for(sent.wait(), 1)
        await asyncio.gather(*controls)
        audio.cancel()
        await asyncio.gather(audio, return_exceptions=True)
        self.assertEqual(order[0], 'audio')
        self.assertLess(order.index('tool-0'), 3)
        self.assertEqual([item for item in order if item.startswith('tool')], ['tool-0', 'tool-1', 'tool-2'])
        self.assertEqual(order.count('audio'), 8)
        self.assertEqual(voice.stale_microphone_frames_discarded, 0)

    async def test_blocked_requested_screenshot_cannot_hold_audio_indefinitely(self):
        from core.agent import LiveVoice
        voice = LiveVoice(None)
        started = asyncio.Event()

        async def blocked_video(**kwargs):
            started.set()
            await asyncio.Event().wait()

        session = NS(send_realtime_input=blocked_video, send_tool_response=AsyncMock())
        body = {'output': {'status': 'inspected', 'screenshot_path': '/tmp/frame.jpg'}}
        call = NS(id='screen', name='inspect_screen')
        with patch('core.agent._read_visual_frame', return_value=b'image'), \
             patch('core.agent.VISION_SEND_BUDGET_SECONDS', .01):
            writer = asyncio.create_task(voice._send_screen_tool_response(session, call, body))
            await asyncio.wait_for(started.wait(), 1)
            with self.assertRaises(SendStalled):
                await asyncio.wait_for(writer, 1)
        self.assertFalse(voice.send_lock.locked())
        self.assertEqual(body['output']['visual_input'], 'ocr_only')
        session.send_tool_response.assert_not_awaited()

    async def test_slow_screenshot_read_does_not_block_audio_loop(self):
        import threading
        from core.agent import LiveVoice
        voice = LiveVoice(None)
        read_started = threading.Event()
        release = threading.Event()

        def slow_read(path):
            read_started.set()
            release.wait(1)
            return None

        session = NS(send_tool_response=AsyncMock())
        body = {'output': {'status': 'inspected', 'screenshot_path': '/tmp/frame.jpg'}}
        with patch('core.agent._read_visual_frame', side_effect=slow_read):
            task = asyncio.create_task(voice._send_screen_tool_response(session,
                NS(id='screen', name='inspect_screen'), body))
            try:
                async with asyncio.timeout(1):
                    while not read_started.is_set():
                        await asyncio.sleep(.001)
                # The conversation loop runs while the filesystem worker is blocked.
                async with voice.send_lock.audio():
                    self.assertFalse(task.done())
            finally:
                release.set()
                await task
        session.send_tool_response.assert_awaited_once()
