"""Regressions found in the system-persona review; no live audio or service changes."""
import asyncio
import json
from pathlib import Path
import shutil
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, Mock

import pytest

from jarvis_control.skills import UnifiedSkills
from jarvis_voice.background import deliver_once
from orchestration.model_routes import ModelJobs
from orchestration.release_manager import ReleaseManager
import scripts.prepare_persona_release as deploy


@pytest.mark.asyncio
async def test_completed_reasoning_is_retained_until_voice_accepts_delivery():
    queue = asyncio.Queue(maxsize=4)
    async def generate(model, prompt): return 'The supplied log shows a timeout; inspect the service.'
    jobs = ModelJobs(['fixture'], queue, generate=generate)
    receipt = jobs.start('Diagnose the supplied log', 'reasoning')
    await asyncio.gather(*tuple(jobs.workers.values()))
    skills = UnifiedSkills(desktop_skills=NS(_model_jobs=jobs))
    voice = NS(connected=True, muted=False, standby_active=False, standby=NS(engaged=False),
               announce_background=AsyncMock(side_effect=[False, True]))
    before = await skills.background_events()
    assert len(before) == 1
    assert before[0]['id'] == 'model:' + receipt['id']
    assert 'timeout' in before[0]['text'] and 'completed' in before[0]['text']
    await deliver_once(voice, skills)
    assert await skills.background_events() == before
    await deliver_once(voice, skills)
    assert await skills.background_events() == []
    assert jobs.jobs[receipt['id']]['notice_acknowledged'] is True
    await jobs.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('state', ['failed', 'cancelled'])
async def test_failed_or_cancelled_reasoning_is_not_announced_as_success(state):
    jobs = NS(jobs={'fixture': {'id': 'fixture', 'route': 'reasoning', 'status': state, 'error': 'TimeoutError'}})
    skills = UnifiedSkills(desktop_skills=NS(_model_jobs=jobs))
    events = await skills.background_events()
    assert len(events) == 1 and state in events[0]['text']
    assert 'completed' not in events[0]['text']
    await skills.acknowledge_event(events[0]['id'])
    assert await skills.background_events() == []


@pytest.mark.asyncio
async def test_model_delivery_preserves_existing_control_and_hermes_notices():
    control = NS(config=NS(), background_events=AsyncMock(return_value=[{'id': 'task:fixture', 'text': 'Existing task completed'}]),
                 acknowledge_event=AsyncMock())
    job = {'id': 'agent-fixture', 'state': 'completed', 'name': 'Existing agent task', 'summary': 'Result received'}
    models = NS(jobs={'fixture': {'id': 'fixture', 'route': 'reasoning', 'status': 'completed', 'result': 'Analysis result'}})
    agents = NS(jobs={'agent-fixture': job}, _get=lambda key: job, _save=Mock())
    skills = UnifiedSkills(control_skills=control, desktop_skills=NS(_model_jobs=models, _task_agents=agents))
    events = await skills.background_events()
    assert {event['id'] for event in events} == {'task:fixture', 'model:fixture', 'hermes:agent-fixture'}
    await skills.acknowledge_event('model:fixture')
    assert not control.acknowledge_event.called
    await skills.acknowledge_event('hermes:agent-fixture')
    assert job['notice_acknowledged'] is True
    await skills.acknowledge_event('task:fixture')
    control.acknowledge_event.assert_awaited_once_with('task:fixture')


def test_reprepare_replaces_an_existing_reasoning_prompt(tmp_path, monkeypatch):
    repo = Path(__file__).resolve().parents[1]
    home = tmp_path / 'home'
    runtime = home / '.local/share/jarvis-runtime'
    parent = runtime / 'releases/base'
    source = tmp_path / 'source'
    for relative in ('voice_layer/persona.py', 'voice_layer/daemon.py', 'core/harness_config.py',
                     'orchestration/model_routes.py', 'orchestration/tool_tiers.py',
                     'jarvis_control/skills.py', 'orchestration/model_notices.py',
                     'orchestration/release_manager.py', 'jarvis_control/nlu.py',
                     'skill_manifests/standby.json'):
        src = source / relative
        src.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(repo / relative, src)
        installed = parent / relative.replace('voice_layer/', 'jarvis_voice/')
        installed.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(repo / relative, installed)
    (parent / 'release.json').write_text('{}')
    (runtime / 'current').symlink_to(parent)
    prompt = source / 'orchestration/model_routes.py'
    prompt.write_text(prompt.read_text().replace('analysis worker for JARVIS OS', 'UPDATED analysis worker for JARVIS OS'))
    daemon = parent / 'jarvis_voice/daemon.py'
    body = daemon.read_text()
    original = deploy.function_text(body, 'send_wake_confirmation', 'LiveVoice')
    body = body.replace(original, "    async def send_wake_confirmation(self, session):\n        raise RuntimeError('legacy wake behavior')\n")
    daemon.write_text(body + '\nKEEP_INSTALLED_MARKER = True\n')
    harness = parent / 'core/harness_config.py'
    body = harness.read_text().replace("            'JARVIS is never permitted",
        "            'Interpret a bare “mute”, legacy standby override. '\n            'JARVIS is never permitted")
    body = body.replace("            'For switching between production mode",
        "            'When the user clearly asks for conversational silence legacy override. '\n            'For switching between production mode")
    harness.write_text(body)
    monkeypatch.setattr(deploy, 'SOURCE', source)
    monkeypatch.setattr(Path, 'home', lambda: home)
    monkeypatch.setattr(deploy.subprocess, 'run', Mock())
    candidate, _ = deploy.prepare(tmp_path)
    body = (candidate / 'orchestration/model_routes.py').read_text()
    assert 'UPDATED analysis worker for JARVIS OS' in body
    assert body.count('REASONING_INSTRUCTION =') == 1
    daemon_body = (candidate / 'jarvis_voice/daemon.py').read_text()
    assert deploy.function_text(daemon_body, 'send_wake_confirmation', 'LiveVoice') == deploy.function_text(
        (source / 'voice_layer/daemon.py').read_text(), 'send_wake_confirmation', 'LiveVoice')
    assert 'KEEP_INSTALLED_MARKER = True' in daemon_body
    harness_body = (candidate / 'core/harness_config.py').read_text()
    assert 'legacy standby override' not in harness_body
    assert 'conversational silence legacy override' not in harness_body
    assert 'JARVIS is never permitted' in harness_body


def test_update_during_copy_cannot_replace_a_newer_release(tmp_path, monkeypatch):
    home = tmp_path / 'home'
    runtime = home / '.local/share/jarvis-runtime'
    old, newer = runtime / 'releases/old', runtime / 'releases/newer'
    old.mkdir(parents=True); newer.mkdir()
    for release in (old, newer): (release / 'release.json').write_text('{}')
    (runtime / 'current').symlink_to(old)
    staged = tmp_path / 'candidate'; staged.mkdir()
    (staged / 'release.json').write_text(json.dumps({'persona_extension': {'parent': str(old), 'sha256': {}}}))
    original_copy = shutil.copytree
    def concurrent_update(src, dest, **kwargs):
        result = original_copy(src, dest, **kwargs)
        (runtime / 'current').unlink(); (runtime / 'current').symlink_to(newer)
        return result
    monkeypatch.setattr(Path, 'home', lambda: home)
    monkeypatch.setattr(deploy.shutil, 'copytree', concurrent_update)
    restart = Mock()
    monkeypatch.setattr(ReleaseManager, '_restart_services', restart)
    monkeypatch.setattr(ReleaseManager, 'verify_health', lambda *a, **kw: True)
    with pytest.raises((ValueError, RuntimeError), match='[Aa]ctive release changed'):
        deploy.activate(staged)
    assert (runtime / 'current').resolve() == newer
    restart.assert_not_called()


@pytest.mark.parametrize('operation', ['switch', 'activate', 'rollback', 'prune'])
def test_release_operations_share_an_exclusive_lock(tmp_path, monkeypatch, operation):
    first, second = ReleaseManager(tmp_path), ReleaseManager(tmp_path)
    first.init_directories()
    older, current, candidate = [first.releases_dir / name for name in ('older', 'current', 'candidate')]
    for release in (older, current, candidate):
        release.mkdir(); (release / 'release.json').write_text('{}')
    first.current_link.symlink_to(current)
    first.previous_link.symlink_to(older)
    restart = Mock(); monkeypatch.setattr(second, '_restart_services', restart)
    actions = {
        'switch': lambda: second._switch_release(candidate, 1),
        'activate': lambda: second.activate_release(candidate),
        'rollback': second.rollback,
        'prune': lambda: second.prune_releases(keep=0),
    }
    with first.release_lock(), pytest.raises(RuntimeError, match='Another release operation'):
        actions[operation]()
    assert first.current_link.resolve() == current
    assert older.exists() and candidate.exists()
    restart.assert_not_called()
    # Exceptions release the lock for later legitimate work.
    with second.release_lock(): pass


def test_prepared_install_verifies_copied_hashes_and_keeps_rollback(tmp_path, monkeypatch):
    import hashlib
    manager = ReleaseManager(tmp_path / 'runtime'); manager.init_directories()
    old = manager.releases_dir / 'old'; old.mkdir(); (old / 'release.json').write_text('{}')
    manager.current_link.symlink_to(old)
    staged = tmp_path / 'staged'; staged.mkdir()
    (staged / 'release.json').write_text('{}'); (staged / 'code.py').write_text('answer = 42\n')
    restart = Mock(); monkeypatch.setattr(manager, '_restart_services', restart)
    monkeypatch.setattr(manager, 'verify_health', lambda **kwargs: True)
    with pytest.raises(ValueError, match='Copied source changed'):
        manager.install_prepared_release(staged, 'bad', expected_current=old, expected_hashes={'code.py': 'invalid'})
    assert manager.current_link.resolve() == old
    assert not (manager.releases_dir / 'bad').exists()
    restart.assert_not_called()
    digest = hashlib.sha256((staged / 'code.py').read_bytes()).hexdigest()
    target = manager.install_prepared_release(staged, 'good', expected_current=old, expected_hashes={'code.py': digest})
    assert manager.current_link.resolve() == target
    assert manager.previous_link.resolve() == old
    assert not list(manager.root_dir.glob('.prepared-*'))
    restart.assert_called_once()


def test_reasoning_prompt_migration_and_repeated_refresh_preserve_other_code():
    old = "class ModelJobs:\n    value = 'Provide analysis only. You have no execution tools. Never claim computer actions were performed.'\n"
    # Match the older module's import/class boundary as well as its string use.
    old = 'import os\n\n' + old
    source = "REASONING_INSTRUCTION = 'new contract'\n"
    refreshed = deploy.refresh_worker_instruction(old, source)
    assert "REASONING_INSTRUCTION = 'new contract'" in refreshed
    assert '    value = REASONING_INSTRUCTION' in refreshed
    assert deploy.refresh_worker_instruction(refreshed, source) == refreshed
    assert refreshed.startswith('import os\n')
