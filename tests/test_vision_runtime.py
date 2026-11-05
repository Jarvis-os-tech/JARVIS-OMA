"""Vision regression checks using fake frames; no desktop/camera capture."""
import asyncio
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock

import pytest

from skills.errors import SkillError
from skills.skills import DesktopSkills
from voice_layer import daemon


@pytest.mark.asyncio
async def test_cold_screen_capture_returns_frame_without_a_preview_cache(tmp_path, monkeypatch):
    monkeypatch.setenv('XDG_RUNTIME_DIR', str(tmp_path))
    monkeypatch.setattr(daemon.shutil, 'which', lambda _: '/usr/bin/grim')
    frame = b'\xff\xd8synthetic-test-frame\xff\xd9'
    process = NS(returncode=0, communicate=AsyncMock(return_value=(frame, b'')))
    spawn = AsyncMock(return_value=process)
    monkeypatch.setattr(daemon.asyncio, 'create_subprocess_exec', spawn)
    voice = daemon.LiveVoice.__new__(daemon.LiveVoice)
    assert await voice._capture_screen_frame() == frame
    assert (tmp_path / 'jarvis_screen/live_stream.jpg').read_bytes() == frame
    assert spawn.call_args.args[0] == '/usr/bin/grim'


@pytest.mark.asyncio
async def test_vision_stream_delivers_frames_to_the_attached_session():
    voice = daemon.LiveVoice.__new__(daemon.LiveVoice)
    voice.vision_mode = 'screen'
    voice.vision_mode_event = asyncio.Event()
    voice.send_lock = asyncio.Lock()
    voice.connected = True
    frame = b'\xff\xd8synthetic-test-frame\xff\xd9'
    voice._capture_screen_frame = AsyncMock(return_value=frame)
    delivered = asyncio.Event()

    async def receive_frame(**kwargs):
        assert kwargs['video'].data == frame
        assert kwargs['video'].mime_type == 'image/jpeg'
        voice.vision_mode = 'off'
        delivered.set()

    session = NS(send_realtime_input=AsyncMock(side_effect=receive_frame))
    voice._session = session
    worker = asyncio.create_task(voice.stream_vision(session))
    try:
        await asyncio.wait_for(delivered.wait(), 1)
    finally:
        worker.cancel()
        await asyncio.gather(worker, return_exceptions=True)
    session.send_realtime_input.assert_awaited_once()


@pytest.mark.asyncio
async def test_missing_camera_is_reported_without_claiming_active_vision(monkeypatch):
    skills = DesktopSkills.__new__(DesktopSkills)
    skills.vision_mode = 'off'
    monkeypatch.setattr('skills.skills.Path.exists', lambda _: False)
    with pytest.raises(SkillError, match='Connect a webcam'):
        await skills._adapter_control_vision_mode('camera')
    assert skills.vision_mode == 'off'


def test_missing_camera_via_local_control_does_not_change_voice_state(monkeypatch):
    voice = daemon.LiveVoice.__new__(daemon.LiveVoice)
    voice.vision_mode = 'off'
    voice._camera_device = '/dev/video0'
    monkeypatch.setattr(daemon.os.path, 'exists', lambda _: False)
    with pytest.raises(RuntimeError, match='Connect a webcam'):
        voice.set_vision_mode('camera')
    assert voice.vision_mode == 'off'


@pytest.mark.asyncio
async def test_local_vision_failure_returns_an_error_instead_of_an_empty_reply():
    import json
    from voice_layer.ipc import ControlServer

    def unavailable(mode):
        raise RuntimeError('Connect a webcam first.')

    server = ControlServer(
        status_provider=lambda: {'vision_mode': 'off'},
        toggle_mute_cb=lambda: False,
        get_vision_mode_cb=lambda: 'off',
        set_vision_mode_cb=unavailable,
    )
    result = json.loads(await server._handle_json_command(
        {'command': 'set_vision_mode', 'mode': 'camera'}))
    assert result == {'status': 'error', 'message': 'Connect a webcam first.',
                      'vision_mode': 'off'}
