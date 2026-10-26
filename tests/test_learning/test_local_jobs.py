import asyncio
import json
import signal
import os
from pathlib import Path
import subprocess
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from google.genai import types

from core.agent import LiveVoice
from learning.bundles import BundleRegistry
from learning.evidence import EpisodeCapture, EpisodeStore
from learning.jobs import LocalHarnessJobs, local_status, read_limited
from learning.research import seed_bundle
from learning.service import LearningService
from skills.skills import DesktopSkills, SkillError


def initialize(tmp_path):
    registry = BundleRegistry(tmp_path)
    bundle = registry.register(seed_bundle())
    registry.activate(bundle.digest)
    return registry, bundle


@pytest.mark.asyncio
async def test_real_background_child_runs_offline_and_publishes_small_result(tmp_path):
    pytest.importorskip('harness2')
    registry, _ = initialize(tmp_path)
    before = registry.status()
    events = asyncio.Queue(maxsize=2)
    jobs = LocalHarnessJobs(tmp_path, events)
    try:
        item = jobs.start()
        assert item['status'] == 'queued'
        with pytest.raises(ValueError, match='already running'):
            jobs.start()
        await asyncio.wait_for(jobs.task, 20)
        event = events.get_nowait()
        assert event['id'] == item['id']
        assert event['status'] == 'completed', event
        assert event['ledger'] == {'rollouts': 4, 'stages': 3}
        assert event['comparison']['observed_difference'] == 0
        assert not event['verified_improvement'] and not event['activated']
        assert registry.status() == before
        assert len(json.dumps(event)) < 4096
        assert jobs.status()['artifacts']['report'].endswith('/report.json')
        restarted = LocalHarnessJobs(tmp_path)
        assert restarted.status()['id'] == item['id']
        assert restarted.status()['status'] == 'completed'
        assert restarted.status()['artifacts'] == event['artifacts']
        await restarted.close()
    finally:
        await jobs.close()


@pytest.mark.asyncio
async def test_cancel_before_launch_and_unknown_job(tmp_path):
    pytest.importorskip('harness2')
    initialize(tmp_path)
    jobs = LocalHarnessJobs(tmp_path)
    item = jobs.start()
    assert (await jobs.cancel(item['id']))['status'] == 'cancelled'
    assert jobs.process is None
    with pytest.raises(ValueError, match='Unknown'):
        jobs.status('another-job')
    await jobs.close()
    with pytest.raises(ValueError, match='closed'):
        jobs.start()


@pytest.mark.asyncio
async def test_cancel_stops_only_owned_group_and_strips_credentials(tmp_path, monkeypatch):
    pytest.importorskip('harness2')
    initialize(tmp_path)
    launched = asyncio.Event()
    stopped = asyncio.Event()
    stdout, stderr = asyncio.StreamReader(), asyncio.StreamReader()
    process = SimpleNamespace(pid=54321, returncode=None, stdout=stdout, stderr=stderr)

    async def wait():
        await stopped.wait()
        return process.returncode

    process.wait = wait

    async def spawn(*args, **kwargs):
        assert '--offline' in args and '--seconds' in args
        assert kwargs['start_new_session'] is True
        assert 'GEMINI_API_KEY' not in kwargs['env']
        launched.set()
        return process

    def killpg(group, sig):
        assert group == process.pid and sig == signal.SIGTERM
        process.returncode = -15
        stdout.feed_eof()
        stderr.feed_eof()
        stopped.set()

    monkeypatch.setenv('GEMINI_API_KEY', 'test-secret')
    monkeypatch.setattr(asyncio, 'create_subprocess_exec', spawn)
    monkeypatch.setattr('learning.jobs.os.killpg', killpg)
    jobs = LocalHarnessJobs(tmp_path)
    jobs.start()
    await launched.wait()
    assert (await jobs.cancel())['status'] == 'cancelled'
    assert stopped.is_set()
    await jobs.close()


@pytest.mark.asyncio
async def test_stream_caps_and_queue_pressure_are_visible(tmp_path):
    pytest.importorskip('harness2')
    stream = asyncio.StreamReader()
    stream.feed_data(b'x' * 20)
    stream.feed_eof()
    with pytest.raises(ValueError, match='output limit'):
        await read_limited(stream, 10)
    initialize(tmp_path)
    events = asyncio.Queue(maxsize=1)
    events.put_nowait({'other': 'event'})
    jobs = LocalHarnessJobs(tmp_path, events)
    jobs.start()
    await asyncio.wait_for(jobs.task, 20)
    assert jobs.status()['notification_dropped'] is True
    assert events.get_nowait() == {'other': 'event'}
    await jobs.close()


@pytest.mark.asyncio
async def test_native_voice_dispatch_starts_real_check_and_reads_result(tmp_path):
    pytest.importorskip('harness2')
    _, bundle = initialize(tmp_path)
    capture = EpisodeCapture(EpisodeStore(tmp_path), bundle, 'test-live-model')
    skills = DesktopSkills()
    skills.learning_service = LearningService(capture, events=skills.task_events)
    voice = LiveVoice(None, skills=skills, learning=capture)
    session = SimpleNamespace(send_tool_response=AsyncMock())
    try:
        capture.input('Run an offline Harness integration check')
        await voice._execute_tool(session, types.FunctionCall(id='launch', name='start_harness_check', args={}))
        queued = session.send_tool_response.call_args.kwargs['function_responses'].response['output']
        assert queued['status'] == 'queued'
        await asyncio.wait_for(skills.learning_service.jobs.task, 20)
        await voice._execute_tool(session, types.FunctionCall(id='result', name='harness_check_status', args={}))
        result = session.send_tool_response.call_args.kwargs['function_responses'].response['output']
        assert result['status'] == 'completed'
        assert result['id'] == queued['id']
        status = await skills.execute('get_harness_status', {})
        assert status['upstream_ready'] and status['learning_enabled']
        with pytest.raises(SkillError):
            await skills.execute('start_harness_check', {'cloud': True})
    finally:
        await capture.close()
        await skills.close_agent_jobs()


@pytest.mark.asyncio
async def test_disabled_capture_reports_status_without_starting_a_job():
    skills = DesktopSkills()
    try:
        result = await skills.execute('get_harness_status', {})
        assert result['learning_enabled'] is False
        with pytest.raises(SkillError, match='start-learning'):
            await skills.execute('start_harness_check', {})
    finally:
        await skills.close_agent_jobs()


@pytest.mark.asyncio
async def test_restart_marks_unfinished_job_unknown_without_replay_or_kill(tmp_path, monkeypatch):
    pytest.importorskip('harness2')
    initialize(tmp_path)
    spawned = AsyncMock(side_effect=AssertionError('Recovery must not launch a child'))
    monkeypatch.setattr(asyncio, 'create_subprocess_exec', spawned)
    killed = []
    monkeypatch.setattr('learning.jobs.os.killpg', lambda *args: killed.append(args))
    original = LocalHarnessJobs(tmp_path)
    item = original.start()
    # Simulate a voice-process crash before its queued worker gets its first tick.
    original.task.cancel()
    await asyncio.gather(original.task, return_exceptions=True)
    recovered = LocalHarnessJobs(tmp_path)
    assert recovered.status()['id'] == item['id']
    assert recovered.status()['status'] == 'interrupted'
    assert not recovered.status()['activated']
    spawned.assert_not_awaited()
    assert not killed
    await recovered.close()


@pytest.mark.asyncio
async def test_another_manager_observes_live_owner_without_reclassifying_or_cancelling(tmp_path):
    pytest.importorskip('harness2')
    initialize(tmp_path)
    owner = LocalHarnessJobs(tmp_path)
    observer = None
    try:
        item = owner.start()
        observer = LocalHarnessJobs(tmp_path)
        state = observer.status(item['id'])
        assert state['status'] in {'queued', 'running'}
        assert state['externally_owned'] is True
        with pytest.raises(ValueError, match='active|running'):
            observer.start()
        with pytest.raises(ValueError, match='owning session'):
            await observer.cancel(item['id'])
        await asyncio.wait_for(owner.task, 20)
        assert observer.status(item['id'])['status'] == 'completed'
    finally:
        await owner.close()
        if observer is not None:
            await observer.close()


@pytest.mark.asyncio
async def test_repeated_cancel_does_not_interrupt_owned_child_reaping(tmp_path, monkeypatch):
    pytest.importorskip('harness2')
    initialize(tmp_path)
    launched, stopping, stopped = asyncio.Event(), asyncio.Event(), asyncio.Event()
    stdout, stderr = asyncio.StreamReader(), asyncio.StreamReader()
    process = SimpleNamespace(pid=54321, returncode=None, stdout=stdout, stderr=stderr)
    signals = []

    async def wait():
        await stopped.wait()
        return process.returncode

    async def spawn(*args, **kwargs):
        launched.set()
        return process

    def killpg(group, sig):
        signals.append((group, sig))
        stopping.set()

    process.wait = wait
    monkeypatch.setattr(asyncio, 'create_subprocess_exec', spawn)
    monkeypatch.setattr('learning.jobs.os.killpg', killpg)
    jobs = LocalHarnessJobs(tmp_path)
    jobs.start()
    await launched.wait()
    first = asyncio.create_task(jobs.cancel())
    await stopping.wait()
    second = asyncio.create_task(jobs.cancel())
    await asyncio.sleep(0)
    process.returncode = -15
    stdout.feed_eof()
    stderr.feed_eof()
    stopped.set()
    results = await asyncio.wait_for(asyncio.gather(first, second), 2)
    assert all(row['status'] == 'cancelled' for row in results)
    assert signals == [(process.pid, signal.SIGTERM)]
    assert jobs.process is None
    await jobs.close()


def test_corrupt_or_symlinked_journal_is_not_treated_as_success(tmp_path):
    initialize(tmp_path)
    checks = tmp_path / 'checks'
    corrupt = checks / 'harness-000000000001'
    corrupt.mkdir(parents=True)
    (corrupt / 'job.json').write_text('{not-json')
    linked = checks / 'harness-000000000002'
    linked.mkdir()
    outside = tmp_path / 'untrusted.json'
    outside.write_text('{"status":"completed"}')
    (linked / 'job.json').symlink_to(outside)
    jobs = LocalHarnessJobs(tmp_path)
    status = jobs.status()
    assert status['status'] == 'idle'
    assert status.get('recovery_warnings')
    assert not jobs.jobs


def test_completed_journal_cannot_reference_artifacts_outside_state(tmp_path):
    initialize(tmp_path)
    key = 'harness-000000000003'
    directory = tmp_path / 'checks' / key
    directory.mkdir(parents=True)
    record = {'version': 1, 'owner_session': 'previous-session', 'updated_at': 1,
        'job': {'id': key, 'kind': 'harness_refinement', 'status': 'completed',
            'offline': True, 'activated': False, 'verified_improvement': False,
            'artifacts': {'run_dir': '/tmp/unrelated', 'report': '/tmp/unrelated/report.json'}}}
    (directory / 'job.json').write_text(json.dumps(record))
    jobs = LocalHarnessJobs(tmp_path)
    assert jobs.status()['status'] == 'idle'
    assert jobs.status()['recovery_warnings']


def test_setup_only_launcher_works_outside_checkout_and_preserves_selection(tmp_path):
    registry, bundle = initialize(tmp_path / 'private-state')
    selected = registry.register({**bundle.document(), 'instructions': 'A deliberately selected local research procedure.'})
    registry.activate(selected.digest)
    before = registry.status()
    root = Path(__file__).resolve().parents[2]
    environment = dict(os.environ, JARVIS_LEARNING_DIR=str(registry.root))
    result = subprocess.run(['bash', str(root / 'scripts/start-learning.sh'), '--setup-only'],
        cwd=tmp_path, env=environment, capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr
    assert selected.digest in result.stdout
    assert registry.status() == before
    assert registry.root.stat().st_mode & 0o777 == 0o700
    assert (registry.root / 'active.json').stat().st_mode & 0o777 == 0o600


def test_unavailable_core_status_does_not_claim_readiness_or_leak_error(monkeypatch):
    def missing():
        raise ValueError('Private provider configuration detail')
    monkeypatch.setattr('learning.jobs.require_upstream', missing)
    result = local_status()
    assert result['status'] == 'warning'
    assert result['upstream_ready'] is False
    assert result['error_type'] == 'ValueError'
    assert 'Private provider' not in json.dumps(result)


@pytest.mark.asyncio
@pytest.mark.parametrize('payload', [b'not json', b'{"offline":false,"activated":false}',
    b'{"offline":true,"activated":true,"provider":"offline-scripted"}'])
async def test_malformed_or_wrong_mode_child_cannot_be_reported_as_completed(tmp_path, monkeypatch, payload):
    pytest.importorskip('harness2')
    initialize(tmp_path)
    stdout, stderr = asyncio.StreamReader(), asyncio.StreamReader()
    stdout.feed_data(payload)
    stdout.feed_eof()
    stderr.feed_eof()
    process = SimpleNamespace(pid=54321, returncode=0, stdout=stdout, stderr=stderr,
                              wait=AsyncMock(return_value=0))
    monkeypatch.setattr(asyncio, 'create_subprocess_exec', AsyncMock(return_value=process))
    jobs = LocalHarnessJobs(tmp_path)
    jobs.start()
    await asyncio.wait_for(jobs.task, 2)
    assert jobs.status()['status'] == 'failed'
    assert jobs.status()['activated'] is False
    assert jobs.status()['verified_improvement'] is False
    await jobs.close()
