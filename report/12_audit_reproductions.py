import asyncio
import runpy
import sys
from unittest.mock import AsyncMock, patch
sys.path.insert(0, '/home/g0pi/Projects/JARVIS-OMA')
from skills import system_control


def test_mute_twice_unmutes_reproduction():
    cli = runpy.run_path('/home/g0pi/Projects/JARVIS-OMA/scripts/jarvisctl')
    run = cli['run_async']
    state = {'muted': False}
    async def send(path, request):
        if request['command'] == 'toggle_mute':
            state['muted'] = not state['muted']
        return {'muted': state['muted']}
    async def exercise():
        with patch.dict(run.__globals__, {'send_command': send}):
            await run(['mute'])
            assert state['muted'] is True
            await run(['mute'])
            assert state['muted'] is False
    asyncio.run(exercise())


def test_empty_env_is_preserved_after_fix():
    process = AsyncMock()
    process.communicate.return_value = (b'', b'')
    process.returncode = 0
    async def exercise():
        with patch.object(system_control.asyncio, 'create_subprocess_exec', return_value=process) as spawn:
            with patch.dict(system_control.os.environ, {'JARVIS_AUDIT_SENTINEL': 'synthetic'}):
                await system_control._run_command('dummy-command', env={})
            assert spawn.call_args.kwargs['env'] == {}
    asyncio.run(exercise())

import errno
import pytest
from filesystem import filesystem as fs
from connectors.internet_search import _public_url


def test_failed_copy_discards_existing_destination(tmp_path):
    src, dst = tmp_path / 'source', tmp_path / 'destination'
    src.write_text('new')
    dst.write_text('original')
    with patch.object(fs.shutil, 'copy2', side_effect=OSError(errno.ENOSPC, 'disk full')):
        with pytest.raises(fs.FileOperationError):
            fs.copy_path(str(src), str(dst), overwrite=True)
    assert not dst.exists()


def test_copy_to_ancestor_removes_source_tree(tmp_path):
    destination = tmp_path / 'parent'
    destination.mkdir()
    source = destination / 'source'
    source.write_text('only copy')
    with pytest.raises(fs.FileOperationError):
        fs.copy_path(str(source), str(destination), overwrite=True)
    assert not source.exists()
    assert not destination.exists()


def test_dotdot_bypasses_critical_directory_guard(tmp_path):
    protected = tmp_path / 'protected'
    protected.mkdir()
    alias = str(protected / '..' / 'protected')
    with patch.object(fs, 'CRITICAL_PATHS', {protected}):
        with pytest.raises(fs.FileOperationError):
            fs.delete_path(str(protected), recursive=True)
        # Only a disposable fixture is deleted, never a real protected path.
        fs.delete_path(alias, recursive=True)
    assert not protected.exists()


def test_malformed_result_url_is_rejected_after_fix():
    assert _public_url('https://[invalid') is False

from filesystem.task_runner import TaskRunner
from proactive.monitor import ProactiveMonitor, MonitorError
from proactive.policy import ProactivePolicy, PolicyLimits, Action, ActionEffect, DecisionStatus
import json


async def _finish_runner(runner, plan):
    job = runner.start('Audit fixture', json.dumps(plan))
    await asyncio.gather(*list(runner._workers.values()))
    return runner.status(job['id'])


def test_task_runner_accepts_successfully_created_empty_file_after_fix(tmp_path):
    path = tmp_path / 'empty.txt'
    async def execute(tool, args):
        return fs.write_text(args['path'], args['content'])
    runner = TaskRunner(execute, lambda tool, args: True)
    result = asyncio.run(_finish_runner(runner, [{'tool': 'write_file', 'args': {'path': str(path), 'content': ''}}]))
    assert path.exists() and path.read_text() == ''
    assert result['status'] == 'completed'
    assert result['completed_steps'] == 1


def test_task_runner_reports_success_when_requested_content_not_written(tmp_path):
    path = tmp_path / 'existing.txt'
    path.write_text('old contents')
    async def execute(tool, args):
        return {'status': 'error', 'message': 'write rejected'}
    runner = TaskRunner(execute, lambda tool, args: True)
    result = asyncio.run(_finish_runner(runner, [{'tool': 'write_file', 'args': {'path': str(path), 'content': 'new contents', 'overwrite': True}}]))
    assert path.read_text() == 'old contents'
    assert result['status'] == 'completed'
    assert result['steps'][0]['result']['status'] == 'error'


def test_read_character_offset_handles_unicode_after_fix(tmp_path):
    path = tmp_path / 'unicode.txt'
    path.write_text('éB', encoding='utf-8')
    assert fs.read_text(str(path), offset=1)['content'] == 'B'


def test_monitor_whitespace_alias_preserves_running_job_after_fix():
    monitor = ProactiveMonitor()
    monitor.track('job', timeout_seconds=10, metadata={'original': True})
    with pytest.raises(MonitorError, match='already tracked'):
        monitor.track(' job ', timeout_seconds=20, metadata={'replacement': True})
    assert len(monitor.list_jobs()) == 1
    assert monitor.get(' job ')['metadata'] == {'original': True}


def test_nan_policy_timestamp_is_rejected_after_fix():
    policy = ProactivePolicy(PolicyLimits(rate_limit_count=1, rate_limit_window=1))
    action = Action('inspect', ActionEffect.READ_ONLY)
    with pytest.raises(ValueError, match='finite'):
        policy.evaluate('first', action, float('nan'))
    assert policy.evaluate('first', action, 0).allowed
    assert policy.evaluate('later', action, 2).allowed
