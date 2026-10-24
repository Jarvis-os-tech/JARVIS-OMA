import asyncio
import json
import signal
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
