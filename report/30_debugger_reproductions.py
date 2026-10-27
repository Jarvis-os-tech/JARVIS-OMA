"""Audit probes: passing tests CONFIRM current defects, not repaired behavior.

No real microphone, GUI mutation, provider request, credential, or agent job.
All process calls are mocked except private temporary UNIX sockets and bounded
verification subprocesses. Run explicitly with .venv/bin/pytest -q this_file.
"""
import asyncio
import json
import os
from pathlib import Path
from types import SimpleNamespace
import threading
from unittest.mock import AsyncMock, Mock, patch

import pytest

from core.connection import ToolCallCache, ToolCallConflict
from core.desktop_session import recover_desktop_environment
from core.ipc import JarvisIPCServer
from core.tool_dispatch import run_skill_call
from core.workers import BoundedWorker
from skills.errors import SkillError


@pytest.mark.asyncio
async def test_native_helper_inherits_environment_without_filter():
    from audio.plugins.native_backend import NativeCompanionEngine
    engine = NativeCompanionEngine()
    with patch.dict(os.environ, {'AUDIT_API_KEY': 'synthetic-not-a-secret'}), \
         patch.object(Path, 'is_file', return_value=True), \
         patch('audio.plugins.native_backend.subprocess.Popen', side_effect=OSError('probe')) as spawn:
        with pytest.raises(OSError):
            engine.start('test-source', 'test-sink')
    assert spawn.call_args.kwargs.get('env') is None


@pytest.mark.asyncio
async def test_gui_daemon_autostart_copies_secret_variables():
    from skills.gui_control import GuiControl, GuiControlError
    gui = GuiControl('/unused/cua-driver')
    with patch.dict(os.environ, {'AUDIT_API_KEY': 'synthetic-not-a-secret'}), \
         patch.object(gui, '_invoke', new=AsyncMock(side_effect=[
             GuiControlError('daemon is not running'), GuiControlError('daemon is not running'), {}])), \
         patch('skills.gui_control.asyncio.create_subprocess_exec', new=AsyncMock()) as spawn, \
         patch('skills.gui_control.asyncio.sleep', new=AsyncMock()):
        await gui._call('list_windows', {})
    assert spawn.call_args.kwargs['env']['AUDIT_API_KEY'] == 'synthetic-not-a-secret'


@pytest.mark.asyncio
async def test_running_file_work_survives_tool_timeout(tmp_path):
    worker = BoundedWorker('audit-owned-worker', capacity=1)
    started, release, finished = threading.Event(), threading.Event(), threading.Event()
    marker = tmp_path / 'late-effect.txt'
    def effect():
        started.set()
        release.wait(2)
        marker.write_text('effect after timeout')
        finished.set()
    owner = SimpleNamespace(execute=lambda *_: worker.run(effect))
    try:
        with pytest.raises(SkillError, match='outcome is unknown'):
            await run_skill_call(owner, 'write_file', {}, timeout=.05)
        assert started.is_set() and not finished.is_set()
        assert len(worker._jobs) == 1
        release.set()
        async with asyncio.timeout(1):
            while not finished.is_set():
                await asyncio.sleep(.005)
        assert marker.read_text() == 'effect after timeout'
    finally:
        release.set()
        await worker.close()


@pytest.mark.asyncio
async def test_registry_command_cancellation_does_not_kill_child():
    from skills import DesktopSkills
    begun = asyncio.Event()
    async def communicate():
        begun.set()
        await asyncio.Event().wait()
    child = SimpleNamespace(communicate=communicate, kill=Mock(), wait=AsyncMock(), returncode=None)
    with patch('skills.skills.asyncio.create_subprocess_exec', new=AsyncMock(return_value=child)):
        task = asyncio.create_task(DesktopSkills._run(SimpleNamespace(_command_timeout=10), '/unused'))
        await begun.wait()
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
    child.kill.assert_not_called()
    child.wait.assert_not_awaited()


@pytest.mark.asyncio
async def test_stop_all_omits_personal_helpers_tasks_and_model_jobs():
    from skills import DesktopSkills
    runtime = SimpleNamespace(stop_all=AsyncMock(return_value={'status': 'stopped'}))
    managers = [SimpleNamespace(close=AsyncMock(), cancel=AsyncMock()) for _ in range(3)]
    owner = SimpleNamespace(get_proactive=AsyncMock(return_value=runtime),
        proactive_service_requested=asyncio.Event(), _cancel_active_development=AsyncMock(),
        _task_agents=managers[0], _task_runner=managers[1], _model_jobs=managers[2])
    result = await DesktopSkills._adapter_proactive_stop(owner)
    assert result['status'] == 'stopped'
    for manager in managers:
        manager.close.assert_not_awaited()
        manager.cancel.assert_not_awaited()


@pytest.mark.asyncio
async def test_gui_verification_boundary_allows_overlapping_mutations():
    from skills.action_verification import verify_adapter_action
    window = {'address': '0x123', 'pid': 42}
    both = asyncio.Event()
    count = 0
    async def dispatch():
        nonlocal count
        count += 1
        if count == 2:
            both.set()
        await asyncio.wait_for(both.wait(), .5)
        return {'status': 'dispatched'}
    with patch('skills.ground_truth.prepare_action_target', new=AsyncMock(
            return_value={'verified': True, 'window': window})), \
         patch('skills.system_control._query_active_window', new=AsyncMock(return_value=window)):
        await asyncio.gather(*(verify_adapter_action(SimpleNamespace(), 'input.type', {}, dispatch)
                               for _ in range(2)))
    assert count == 2


@pytest.mark.asyncio
async def test_standby_does_not_observe_failed_audio_health():
    from audio.plugins.standby import StandbyController
    engine = SimpleNamespace(async_input_queue=asyncio.Queue(),
        monitor_health=AsyncMock(side_effect=RuntimeError('audio failed')))
    detector = SimpleNamespace(reset=Mock(), process=Mock(return_value=False))
    standby = StandbyController(detector=detector, arming_delay=0)
    task = asyncio.create_task(standby.listen_for_wake_word(engine))
    done, _ = await asyncio.wait({task}, timeout=.03)
    assert not done
    engine.monitor_health.assert_not_awaited()
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)


@pytest.mark.asyncio
async def test_manual_interrupt_accepts_late_old_turn_pcm_again():
    from audio.plugins.native_backend import NativeCompanionEngine
    from core.agent import LiveVoice
    from google.genai import types
    engine = NativeCompanionEngine()
    voice = LiveVoice(engine)
    voice.interrupt_audio()
    assert not engine.speaking
    # The provider has not sent an interrupted/turn_complete event yet.
    await voice.handle(types.LiveServerMessage(server_content=types.LiveServerContent(
        model_turn=types.Content(role='model', parts=[types.Part(
            inline_data=types.Blob(data=bytes(960), mime_type='audio/pcm;rate=24000'))]))))
    assert engine.speaking
    assert engine._generation_samples == 480


def test_completed_calls_exhaust_cache_after_256_actions():
    cache = ToolCallCache()
    for number in range(256):
        key = str(number)
        cache.claim(key, 'read_file', {'path': 'example'})
        cache.store(key, {'status': 'done'})
        cache.delivered(key)
    with pytest.raises(ToolCallConflict, match='cache is full'):
        cache.claim('257', 'read_file', {'path': 'example'})


def test_desktop_recovery_retains_invalid_existing_identifiers(tmp_path):
    env = {'XDG_RUNTIME_DIR': str(tmp_path), 'WAYLAND_DISPLAY': 'old-display',
           'HYPRLAND_INSTANCE_SIGNATURE': 'dead-instance'}
    assert recover_desktop_environment(env) == {}


@pytest.mark.asyncio
async def test_idle_ipc_clients_bypass_subscriber_limit(tmp_path):
    server = JarvisIPCServer(tmp_path / 'ipc.sock', max_subscribers=1)
    clients = []
    await server.start()
    try:
        for _ in range(4):
            clients.append(await asyncio.open_unix_connection(str(server.socket_path)))
        await asyncio.sleep(.02)
        assert len(server._clients) == 4
        assert not server._subscribers
    finally:
        for _, writer in clients:
            writer.close()
            await writer.wait_closed()
        await server.close()


@pytest.mark.asyncio
async def test_second_ipc_server_replaces_first_live_endpoint(tmp_path):
    path = tmp_path / 'ipc.sock'
    first = JarvisIPCServer(path, status_provider=lambda: {'owner': 'first'})
    second = JarvisIPCServer(path, status_provider=lambda: {'owner': 'second'})
    await first.start()
    try:
        await second.start()
        reader, writer = await asyncio.open_unix_connection(str(path))
        writer.write(b'{"command":"status"}\n')
        await writer.drain()
        result = json.loads(await reader.readline())
        writer.close()
        await writer.wait_closed()
        assert result['owner'] == 'second' and first._server.is_serving()
    finally:
        await second.close()
        await first.close()


@pytest.mark.asyncio
async def test_structural_completion_can_pass_a_functional_regression(tmp_path):
    from proactive.verification import capture_workspace, verify_workspace_changes, completion_evidence
    (tmp_path / 'maths.py').write_text('def add(a, b): return a + b\n')
    baseline = await capture_workspace(tmp_path)
    (tmp_path / 'maths.py').write_text('def add(a, b): return 0\n')
    result = await verify_workspace_changes(tmp_path, baseline)
    assert result['status'] == 'passed'
    assert result['functional_verified'] is False
    assert completion_evidence(result)['announcement_state'] == 'completed'
