"""Scoped experience checks using synthetic trial and human-review records."""
import asyncio
import json
import hashlib
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from google.genai import types

from core.agent import LiveVoice
from learning.bundles import BundleRegistry
from learning.evidence import EpisodeCapture, EpisodeStore, sanitize
from learning.experience import ExperienceLibrary, PROJECT
from learning.service import LearningService
from learning.trials import activate_trial, rollback_trial
from learning.voice_tests import CASES, record_result
from skills.skills import DesktopSkills, SkillError
from tests.test_learning.test_trials import prepared_trial


def reviewed_trial(tmp_path):
    registry, run_id, _, candidate = prepared_trial(tmp_path)
    activate_trial(tmp_path, run_id, 'Synthetic test fixture')
    library = ExperienceLibrary(tmp_path)
    proposal = library.propose(run_id, 'Research notices', 'unit-test-live')
    store = EpisodeStore(tmp_path)
    episode_ids = []
    for key, prompt, _ in CASES:
        episode = 'voice-' + key
        episode_ids.append(episode)
        store.append(episode, 'started', sanitize({'bundle': candidate.digest,
            'model': 'unit-test-live', 'role': 'research'}))
        store.append(episode, 'user_input', sanitize({'text': prompt}))
        store.append(episode, 'assistant_output', sanitize({'text': 'Synthetic reviewed output'}))
        store.append(episode, 'ended', sanitize({'state': 'delivered_unverified', 'pending_actions': 0,
                                               'dropped_events': 0, 'failed_events': 0}))
        record_result(store, episode, 'pass')
    return registry, run_id, library, proposal, episode_ids, candidate


def test_published_procedure_reuses_ledger_and_is_strictly_scoped(tmp_path):
    registry, _, library, proposal, ids, candidate = reviewed_trial(tmp_path)
    assert library.applicable(project=PROJECT, bundle=candidate.digest, voice_model='unit-test-live') == []
    published = library.publish(proposal['id'], ids)
    assert published['authority'] == 'verified'
    assert published['evidence']['voice_episodes']['research'] == 'voice-research'
    assert library.store.history(published['id'])
    assert [row['id'] for row in library.applicable(project=PROJECT, bundle=candidate.digest,
            voice_model='unit-test-live')] == [published['id']]
    assert library.applicable(project='another-project', bundle=candidate.digest, voice_model='unit-test-live') == []
    assert library.applicable(project=PROJECT, bundle=candidate.digest, voice_model='another-model') == []
    assert library.applicable(project=PROJECT, bundle='0' * 64, voice_model='unit-test-live') == []
    assert registry.active() == candidate


def test_feedback_is_unverified_redacted_and_never_exported(tmp_path, monkeypatch):
    registry, _, library, _, _, candidate = reviewed_trial(tmp_path)
    monkeypatch.setenv('SAMPLE_API_KEY', 'private-credential-value')
    result = library.feedback('Wrong source private-credential-value', 'missing_source',
        project=PROJECT, model='unit-test-live', bundle=candidate.digest, episode='voice-research')
    assert result['reusable_lesson'] is False
    row = library.store.get(result['id'])
    assert row['status'] == 'proposed' and row['kind'] == 'observation'
    assert 'private-credential-value' not in json.dumps(row)
    assert library.applicable(project=PROJECT, bundle=candidate.digest, voice_model='unit-test-live') == []
    assert library.export_for_optimizer(tmp_path / 'export', project=PROJECT,
                                        model='unit-test-text', bundle=candidate.digest) == []
    assert not (tmp_path / 'export').exists()


@pytest.mark.parametrize('problem', ['missing_review', 'wrong_model', 'incomplete', 'duplicate', 'offline'])
def test_publication_rejects_unverified_or_mismatched_evidence(tmp_path, problem):
    _, _, library, proposal, ids, _ = reviewed_trial(tmp_path)
    store = EpisodeStore(tmp_path)
    if problem == 'missing_review':
        record_result(store, ids[0], 'fail')
    elif problem == 'wrong_model':
        row = library.store.get(proposal['id'])
        # A second pending proposal can name a different model; it still cannot publish.
        proposal = library.propose(row['evidence']['run_id'], 'Research notices', 'another-model')
    elif problem == 'incomplete':
        store.append(ids[0], 'capture_health', sanitize({'incomplete': True}))
    elif problem == 'duplicate':
        ids[-1] = ids[0]
    else:
        root = tmp_path / 'refinements' / ('a' * 32)
        report = json.loads((root / 'report.json').read_text())
        report['offline'] = True
        (root / 'report.json').write_text(json.dumps(report))
    with pytest.raises(ValueError):
        library.publish(proposal['id'], ids)
    assert library.store.list() == []


@pytest.mark.parametrize('changed', ['candidate_digest', 'baseline_digest', 'provider'])
def test_publication_rejects_stale_proposal_provenance_even_if_gate_is_eligible(tmp_path, monkeypatch, changed):
    _, run_id, library, proposal, ids, _ = reviewed_trial(tmp_path)
    evidence = proposal['evidence']
    gate = {'eligible_for_controlled_trial': True, 'candidate_digest': evidence['bundle'],
            'baseline_digest': evidence['baseline']}
    if changed == 'provider':
        path = tmp_path / 'refinements' / run_id / 'report.json'
        report = json.loads(path.read_text())
        report['provider'] = 'different-text-model'
        path.write_text(json.dumps(report))
    else:
        gate[changed] = '0' * 64
    monkeypatch.setattr('learning.experience.candidate_check', lambda *args, **kwargs: gate)
    with pytest.raises(ValueError, match='proposal provenance differs'):
        library.publish(proposal['id'], ids)
    assert library.store.list() == []


def test_consistently_rewritten_trial_model_does_not_validate_an_older_lesson_proposal(tmp_path):
    from learning.trials import candidate_check
    _, run_id, library, proposal, ids, _ = reviewed_trial(tmp_path)
    root = tmp_path / 'refinements' / run_id
    report_path = root / 'report.json'
    report = json.loads(report_path.read_text())
    for relative in report['artifact_sha256']:
        path = root / relative
        if path.name in {'started.json', 'result.json'}:
            document = json.loads(path.read_text())
            document['model'] = 'another-text-model'
            path.write_text(json.dumps(document))
    report['provider'] = 'another-text-model'
    report['artifact_sha256'] = {relative: hashlib.sha256((root / relative).read_bytes()).hexdigest()
                                for relative in report['artifact_sha256']}
    report_path.write_text(json.dumps(report))
    assert candidate_check(tmp_path, run_id,
        baseline_digest=proposal['evidence']['baseline'])['eligible_for_controlled_trial']
    with pytest.raises(ValueError, match='proposal provenance differs'):
        library.publish(proposal['id'], ids)
    assert library.store.list() == []


def test_approved_guidance_export_and_revocation_keep_history(tmp_path):
    _, _, library, proposal, ids, candidate = reviewed_trial(tmp_path)
    entry = library.publish(proposal['id'], ids)
    exported = library.export_for_optimizer(tmp_path / 'export', project=PROJECT,
        model='unit-test-text', bundle=candidate.digest)
    assert exported == [entry['id']]
    assert (tmp_path / 'export' / (entry['id'] + '.md')).read_text() == candidate.instructions
    assert 'voice-research' not in (tmp_path / 'export' / 'INDEX.md').read_text()
    library.revoke(entry['id'], 'Regression observed')
    assert library.applicable(project=PROJECT, bundle=candidate.digest, voice_model='unit-test-live') == []
    assert library.store.get(entry['id'])['text'] == candidate.instructions
    assert library.store.history(entry['id'])


def test_rollback_immediately_suppresses_candidate_lessons(tmp_path):
    _, run_id, library, proposal, ids, candidate = reviewed_trial(tmp_path)
    library.publish(proposal['id'], ids)
    rollback_trial(tmp_path, run_id)
    assert library.applicable(project=PROJECT, bundle=candidate.digest, voice_model='unit-test-live') == []


def test_ledger_cap_never_prevents_revocation(tmp_path, monkeypatch):
    _, _, library, proposal, ids, candidate = reviewed_trial(tmp_path)
    entry = library.publish(proposal['id'], ids)
    monkeypatch.setattr(library.store, 'stats', lambda: {'total': 1000})
    with pytest.raises(ValueError, match='limit'):
        library.feedback('New note', 'other', project=PROJECT, model='unit-test-live', bundle=candidate.digest)
    assert library.revoke(entry['id'], 'Revoke even at capacity')['revoked']
    assert library.applicable(project=PROJECT, bundle=candidate.digest, voice_model='unit-test-live') == []


@pytest.mark.asyncio
async def test_native_voice_tools_return_real_status_and_persist_feedback(tmp_path):
    registry, _, _, _, _, candidate = reviewed_trial(tmp_path)
    capture = EpisodeCapture(EpisodeStore(tmp_path), candidate, 'unit-test-live')
    capture.previous = 'voice-research'
    skills = DesktopSkills()
    skills.learning_service = LearningService(capture)
    voice = LiveVoice(None, skills=skills, learning=capture)
    session = SimpleNamespace(send_tool_response=AsyncMock())
    try:
        capture.input('Jarvis, is research learning enabled?')
        await voice._execute_tool(session, types.FunctionCall(id='status', name='get_learning_status', args={}))
        output = session.send_tool_response.call_args.kwargs['function_responses'].response['output']
        assert output['enabled'] and output['applicable_lessons'] == 0
        await voice._execute_tool(session, types.FunctionCall(id='feedback', name='record_research_feedback',
            args={'text': 'There was a pause before the answer', 'category': 'lag_before_answer'}))
        output = session.send_tool_response.call_args.kwargs['function_responses'].response['output']
        assert output['validation'] == 'unverified'
        assert output['episode'] == 'voice-research'
        assert not output['reusable_lesson']
        assert (await skills.execute('get_learning_status', {}))['unverified_feedback'] == 1
        assert (await skills.execute('list_research_lessons', {}))['lessons'] == []
        with pytest.raises(SkillError):
            await skills.execute('record_research_feedback', {'text': 'x', 'publish': True})
        assert registry.active() == candidate
    finally:
        await capture.close()
        await skills.close_agent_jobs()


@pytest.mark.asyncio
async def test_learning_tools_honestly_report_disabled():
    skills = DesktopSkills()
    try:
        assert (await skills.execute('get_learning_status', {}))['enabled'] is False
        with pytest.raises(SkillError, match='disabled'):
            await skills.execute('list_research_lessons', {})
    finally:
        await skills.close_agent_jobs()


@pytest.mark.asyncio
@pytest.mark.parametrize('ipc_enabled', [False, True])
@pytest.mark.parametrize('learning_enabled', [False, True])
async def test_startup_wires_service_and_declares_voice_tools(tmp_path, ipc_enabled, learning_enabled):
    import contextlib
    from unittest.mock import MagicMock, patch
    from core import agent
    from core.config import Config
    from learning.research import seed_bundle
    registry = BundleRegistry(tmp_path)
    bundle = registry.register(seed_bundle())
    registry.activate(bundle.digest)
    config = Config()
    config.audio.backend = 'legacy'  # The test supplies a legacy engine double.
    config.skills.enabled = True
    config.memory.enabled = False
    config.agent.greet_on_activation = False
    config.agent.model = 'unit-test-live'
    skills = DesktopSkills(config=config)
    engine = MagicMock()
    engine.async_input_queue = asyncio.Queue()
    engine.monitor_health = AsyncMock()
    echo = SimpleNamespace(start=AsyncMock(), close=AsyncMock(), source='source', sink='sink')
    ipc = SimpleNamespace(start=AsyncMock(), close=AsyncMock(), broadcast_state=MagicMock())
    connected = []

    @contextlib.asynccontextmanager
    async def connect(**kwargs):
        connected.append(kwargs)
        yield SimpleNamespace()

    @contextlib.asynccontextmanager
    async def client_context():
        yield SimpleNamespace(live=SimpleNamespace(connect=connect))

    async def stop(*workers):
        for worker in workers:
            worker.close()
        raise asyncio.CancelledError()

    args = SimpleNamespace(microphone=None, transcripts=False, no_ipc=not ipc_enabled, retries=0,
                           learning_dir=str(tmp_path) if learning_enabled else None)
    with patch.dict('os.environ', {'JARVIS_LEARNING_DIR': ''}), \
         patch.object(agent, 'EchoCancellation', return_value=echo), \
         patch.object(agent, 'NativeAudioEngine', return_value=engine), \
         patch.object(agent, 'DesktopSkills', return_value=skills), \
         patch.object(agent, 'JarvisIPCServer', return_value=ipc) as ipc_factory, \
         patch('google.genai.Client', return_value=SimpleNamespace(aio=client_context())), \
         patch.object(agent, 'supervise', side_effect=stop):
        with pytest.raises(asyncio.CancelledError):
            await agent.run(args, 'fake', config=config)
    if learning_enabled:
        assert skills.learning_service.capture.model == 'unit-test-live'
        assert skills.learning_service.capture.bundle == bundle
    else:
        assert skills.learning_service is None
    names = {item['name'] for item in connected[0]['config']['tools'][0]['function_declarations']}
    assert {'discover_domain_tools', 'execute_domain_tool'} <= names
    domain = await skills.execute('discover_domain_tools', {'domain': 'learning'})
    assert {'get_learning_status', 'list_research_lessons', 'record_research_feedback'} <= {
        item['name'] for item in domain['tools']}
    types.LiveConnectConfig.model_validate(connected[0]['config'])
    if ipc_enabled:
        status = ipc_factory.call_args.kwargs['status_provider']()
        assert status['learning_enabled'] is learning_enabled
        assert status['learning_bundle'] == (bundle.digest if learning_enabled else None)
        assert status['learning_model'] == ('unit-test-live' if learning_enabled else None)
        assert status['learning_capture_dropped'] == 0
        assert status['learning_capture_failed'] == 0
        ipc.start.assert_awaited_once()
        ipc.close.assert_awaited_once()
    engine.terminate.assert_called_once()
    echo.close.assert_awaited_once()


def test_symlink_experience_database_is_rejected(tmp_path):
    library = ExperienceLibrary(tmp_path)
    library.path.symlink_to(tmp_path / 'outside')
    with pytest.raises(ValueError, match='symlink'):
        library.entries()


def test_published_lesson_is_available_to_real_upstream_context_only_in_scope(tmp_path):
    pytest.importorskip('harness2')
    from pathlib import Path
    from learning.refinement import run_refinement
    from learning.research_runtime import ScriptedBackend
    _, _, library, proposal, ids, candidate = reviewed_trial(tmp_path)
    entry = library.publish(proposal['id'], ids)

    class MatchingBackend(ScriptedBackend):
        model = 'unit-test-text'

    report = run_refinement(tmp_path, offline=True, backend_factory=MatchingBackend)
    assert report['experience_ids'] == [entry['id']]
    context = Path(report['run_dir']) / 'optimizer/context'
    files = list(context.rglob(entry['id'] + '.md'))
    assert files and all(path.read_text() == candidate.instructions for path in files)
    assert not list(context.rglob('research-experience.sqlite3'))
    with pytest.raises(ValueError, match='already published'):
        library.publish(proposal['id'], ids)
