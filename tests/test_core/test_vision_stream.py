"""Offline unit tests for JARVIS Real-Time Vision Streaming in core/agent."""
import asyncio
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from core.agent import LiveVoice
from core.ipc import JarvisIPCServer
from skills import DesktopSkills


class MockBlob:
    def __init__(self, data=b'', mime_type=''):
        self.data = data
        self.mime_type = mime_type


class VisionStreamTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.engine = MagicMock()
        self.engine.async_input_queue = asyncio.Queue()
        self.skills = DesktopSkills()
        for cmd in ('vision_ctrl', 'grim', 'hyprctl'):
            if not self.skills._commands.get(cmd):
                self.skills._commands[cmd] = f'/usr/bin/{cmd}'
        self.voice = LiveVoice(self.engine, skills=self.skills)

    def test_set_vision_mode_lifecycle(self):
        # Initial state is off
        self.assertEqual(self.voice.vision_mode, 'off')
        self.assertFalse(self.voice.vision_mode_event.is_set())

        # Turn on screen sharing
        mode = self.voice.set_vision_mode('screen')
        self.assertEqual(mode, 'screen')
        self.assertEqual(self.voice.vision_mode, 'screen')
        self.assertEqual(self.skills.vision_mode, 'screen')
        self.assertTrue(self.voice.vision_mode_event.is_set())
        self.assertIn("REALTIME DESKTOP SCREEN SHARING", self.voice._notices[-1])

        # Switch to camera sharing
        mode = self.voice.set_vision_mode('camera')
        self.assertEqual(mode, 'camera')
        self.assertEqual(self.voice.vision_mode, 'camera')
        self.assertTrue(self.voice.vision_mode_event.is_set())
        self.assertIn("REALTIME HARDWARE CAMERA FEED", self.voice._notices[-1])

        # Turn off
        mode = self.voice.set_vision_mode('off')
        self.assertEqual(mode, 'off')
        self.assertEqual(self.voice.vision_mode, 'off')
        self.assertFalse(self.voice.vision_mode_event.is_set())
        self.assertIn("Realtime vision feed is now STOPPED", self.voice._notices[-1])

        # Invalid mode falls back to off
        mode = self.voice.set_vision_mode('invalid_xyz')
        self.assertEqual(mode, 'off')

    async def test_stream_vision_worker(self):
        fake_frame = b'\xff\xd8\xff\xe0fake_jpeg_content'
        self.voice._capture_screen_frame = AsyncMock(return_value=fake_frame)

        session = MagicMock()
        session.send_realtime_input = AsyncMock()

        # Start streaming screen
        self.voice.set_vision_mode('screen')

        # Run stream_vision briefly
        task = asyncio.create_task(self.voice.stream_vision(session))
        await asyncio.sleep(0.05)

        # Stop streaming and cancel task
        self.voice.set_vision_mode('off')
        task.cancel()
        with contextlib_suppress(asyncio.CancelledError):
            await task

        # Verify that send_realtime_input was called with a video Blob
        session.send_realtime_input.assert_awaited()
        kwargs = session.send_realtime_input.await_args.kwargs
        self.assertIn('video', kwargs)
        blob = kwargs['video']
        self.assertEqual(blob.mime_type, 'image/jpeg')
        self.assertEqual(blob.data, fake_frame)

    async def test_ipc_vision_mode_commands(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            sock_path = Path(tmpdir) / 'test_ipc_vision.sock'
            ipc = JarvisIPCServer(
                socket_path=sock_path,
                status_provider=lambda: {'vision_mode': self.voice.vision_mode},
                set_vision_mode_cb=lambda m: {'vision_mode': self.voice.set_vision_mode(m)},
            )
            self.voice.on_vision_mode_broadcast = lambda m: ipc.broadcast_state({'vision_mode': m})
            await ipc.start()

            reader, writer = await asyncio.open_unix_connection(str(sock_path))

            # Query initial vision mode
            writer.write(b'{"command": "get_vision_mode"}\n')
            await writer.drain()
            line = await reader.readline()
            resp = json.loads(line.decode('utf-8').strip())
            self.assertEqual(resp['status'], 'ok')
            self.assertEqual(resp['vision_mode'], 'off')
            writer.close()
            await writer.wait_closed()

            # Change vision mode to screen via IPC
            reader2, writer2 = await asyncio.open_unix_connection(str(sock_path))
            writer2.write(b'{"command": "set_vision_mode", "mode": "screen"}\n')
            await writer2.drain()
            line = await reader2.readline()
            resp = json.loads(line.decode('utf-8').strip())
            self.assertEqual(resp['status'], 'ok')
            self.assertEqual(resp['vision_mode'], 'screen')
            self.assertEqual(self.voice.vision_mode, 'screen')

            writer2.close()
            await writer2.wait_closed()
            await ipc.close()

    async def test_capture_screen_frame_atomic(self):
        fake_jpeg = b'\xff\xd8\xff\xe0\x00\x10JFIFfake_screen_frame_content'
        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(fake_jpeg, b''))

        with patch('asyncio.create_subprocess_exec', return_value=mock_proc) as mock_exec, \
             tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict('os.environ', {'XDG_RUNTIME_DIR': tmpdir}):
                frame = await self.voice._capture_screen_frame()
                self.assertEqual(frame, fake_jpeg)

                # Verify grim arguments include pipe stdout '-'
                args = mock_exec.call_args[0]
                self.assertIn('-', args)
                self.assertIn('-t', args)
                self.assertIn('jpeg', args)

                # Verify atomic file write produced valid live_stream.jpg
                saved_path = Path(tmpdir) / 'jarvis_screen' / 'live_stream.jpg'
                self.assertTrue(saved_path.exists())
                self.assertEqual(saved_path.read_bytes(), fake_jpeg)

    async def test_capture_screen_frame_timeout_cleanup(self):
        mock_proc = AsyncMock()
        mock_proc.returncode = None
        mock_proc.kill = MagicMock()
        mock_proc.wait = AsyncMock()
        mock_proc.communicate = AsyncMock(side_effect=asyncio.TimeoutError)

        with patch('asyncio.create_subprocess_exec', return_value=mock_proc):
            frame = await self.voice._capture_screen_frame()
            self.assertIsNone(frame)
            mock_proc.kill.assert_called_once()
            mock_proc.wait.assert_awaited_once()

    async def test_stream_vision_timeout_resilience(self):
        fake_frame = b'\xff\xd8\xff\xe0fake_jpeg_content'
        self.voice._capture_screen_frame = AsyncMock(return_value=fake_frame)

        session = MagicMock()
        # Simulate send_realtime_input timing out
        session.send_realtime_input = AsyncMock(side_effect=asyncio.TimeoutError)

        self.voice.set_vision_mode('screen')
        task = asyncio.create_task(self.voice.stream_vision(session))
        await asyncio.sleep(0.05)

        # Worker should remain alive and not crash the task
        self.assertFalse(task.done())

        self.voice.set_vision_mode('off')
        task.cancel()
        with contextlib_suppress(asyncio.CancelledError):
            await task


    async def test_capture_camera_frame_live_stream_cache(self):
        fake_camera_frame = b'\xff\xd8\xff\xe0\x00\x10JFIFfake_camera_live_feed\xff\xd9'
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict('os.environ', {'XDG_RUNTIME_DIR': tmpdir}):
                webcam_dir = Path(tmpdir) / 'jarvis_webcam'
                webcam_dir.mkdir(parents=True, exist_ok=True)
                frame_file = webcam_dir / 'live_stream.jpg'
                frame_file.write_bytes(fake_camera_frame)

                with patch('asyncio.create_subprocess_exec') as mock_exec:
                    frame = await self.voice._capture_camera_frame()
                    self.assertEqual(frame, fake_camera_frame)
                    mock_exec.assert_not_called()

    async def test_capture_camera_frame_actuator_fallback_when_stale(self):
        stale_frame = b'\xff\xd8\xff\xe0\x00\x10JFIFold_content\xff\xd9'
        fresh_frame = b'\xff\xd8\xff\xe0\x00\x10JFIFnew_grab\xff\xd9'
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict('os.environ', {'XDG_RUNTIME_DIR': tmpdir}):
                webcam_dir = Path(tmpdir) / 'jarvis_webcam'
                webcam_dir.mkdir(parents=True, exist_ok=True)
                frame_file = webcam_dir / 'live_stream.jpg'
                frame_file.write_bytes(stale_frame)

                # Set mtime to 10 seconds ago
                old_time = time.time() - 10.0
                os.utime(str(frame_file), (old_time, old_time))

                mock_proc = AsyncMock()
                mock_proc.returncode = 0
                async def mock_communicate():
                    frame_file.write_bytes(fresh_frame)
                    return (b'{"status":"ok"}', b'')
                mock_proc.communicate = AsyncMock(side_effect=mock_communicate)

                with patch('asyncio.create_subprocess_exec', return_value=mock_proc) as mock_exec:
                    frame = await self.voice._capture_camera_frame()
                    self.assertEqual(frame, fresh_frame)
                    mock_exec.assert_called_once()


def contextlib_suppress(*exceptions):
    import contextlib
    return contextlib.suppress(*exceptions)

