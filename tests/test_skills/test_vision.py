"""Offline unit tests for JARVIS Vision & Video Streaming skills."""
import json
from pathlib import Path
import unittest
from unittest.mock import AsyncMock, patch

from skills import DesktopSkills, SkillError


class VisionSkillsTests(unittest.IsolatedAsyncioTestCase):
    def make_desktop_skills(self):
        skills = DesktopSkills()
        for cmd in ('vision_ctrl', 'grim', 'hyprctl'):
            if not skills._commands.get(cmd):
                skills._commands[cmd] = f'/usr/bin/{cmd}'
        return skills

    async def test_control_vision_mode(self):
        skills = self.make_desktop_skills()
        callback_called = []

        def on_change(mode):
            callback_called.append(mode)

        skills.on_vision_mode_change = on_change

        # 1. Turn on screen sharing
        res = await skills.execute('control_vision_mode', {'mode': 'screen'})
        self.assertEqual(res['status'], 'ok')
        self.assertEqual(res['mode'], 'screen')
        self.assertTrue(res['active'])
        self.assertEqual(skills.vision_mode, 'screen')
        self.assertEqual(callback_called, ['screen'])

        # 2. Switch to camera sharing
        res = await skills.execute('control_vision_mode', {'mode': 'camera'})
        self.assertEqual(res['status'], 'ok')
        self.assertEqual(res['mode'], 'camera')
        self.assertTrue(res['active'])
        self.assertEqual(skills.vision_mode, 'camera')
        self.assertEqual(callback_called, ['screen', 'camera'])

        # 3. Query status
        res = await skills.execute('control_vision_mode', {'mode': 'camera', 'action': 'status'})
        self.assertEqual(res['status'], 'ok')
        self.assertEqual(res['mode'], 'camera')
        self.assertEqual(res['action'], 'status')
        self.assertTrue(res['active'])

        # 4. Stop streaming
        res = await skills.execute('control_vision_mode', {'mode': 'camera', 'action': 'stop'})
        self.assertEqual(res['status'], 'ok')
        self.assertEqual(res['mode'], 'off')
        self.assertFalse(res['active'])
        self.assertEqual(skills.vision_mode, 'off')
        self.assertEqual(callback_called, ['screen', 'camera', 'off'])

    async def test_control_vision_mode_validation(self):
        skills = self.make_desktop_skills()
        with self.assertRaises(SkillError):
            await skills.execute('control_vision_mode', {'mode': 'invalid_mode'})

    async def test_capture_camera_frame(self):
        skills = self.make_desktop_skills()
        sample_path = '/tmp/test_webcam_frame.jpg'
        Path(sample_path).write_bytes(b'\xff\xd8\xff\xe0test_jpg_data')
        try:
            mock_out = json.dumps({
                'status': 'ok',
                'action': 'capture_frame',
                'path': sample_path,
                'file_size': 20,
                'method': 'ffmpeg-mjpeg',
            })
            skills._run = AsyncMock(return_value=mock_out)

            res = await skills.execute('capture_camera_frame', {'device': '/dev/video0'})
            self.assertEqual(res['status'], 'captured')
            self.assertEqual(res['screenshot_path'], sample_path)
            self.assertEqual(res['method'], 'ffmpeg-mjpeg')
        finally:
            if Path(sample_path).exists():
                Path(sample_path).unlink()

    async def test_check_vision_hardware(self):
        skills = self.make_desktop_skills()
        status_json = json.dumps({
            'status': 'ok',
            'camera_ready': True,
            'camera_count': 1,
            'display_ready': True,
            'session_type': 'wayland',
        })
        camera_json = json.dumps({
            'status': 'ok',
            'camera_count': 1,
            'cameras': [{'device': '/dev/video0', 'name': 'USB Camera', 'available': True}],
        })
        skills._run = AsyncMock(side_effect=[status_json, camera_json])

        res = await skills.execute('check_vision_hardware', {})
        self.assertEqual(res['status'], 'ok')
        self.assertTrue(res['hardware_status']['camera_ready'])
        self.assertEqual(len(res['cameras']), 1)
        self.assertEqual(res['cameras'][0]['device'], '/dev/video0')
