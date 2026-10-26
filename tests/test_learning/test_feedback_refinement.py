import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from learning.bundles import BundleRegistry
from learning.experience import ExperienceLibrary, PROJECT
from learning.feedback import selected_feedback
from learning.jobs import LocalHarnessJobs
from learning.refinement import run_refinement
from learning.research import seed_bundle
from learning.research_runtime import ScriptedBackend
from learning.trials import candidate_check


def initialize(root, text='The answer omitted the source; improve citation checks.'):
    registry = BundleRegistry(root)
    bundle = registry.register(seed_bundle())
    registry.activate(bundle.digest)
    note = ExperienceLibrary(root).feedback(text, 'missing_source', project=PROJECT,
        model='test-voice-model', bundle=bundle.digest)
    return registry, bundle, note['id']


def cloud_report(root, identity, calls=None):
    class RecordingBackend(ScriptedBackend):
        model = 'test-cloud-model'

        def generate(self, **kwargs):
            if calls is not None:
                calls.append(kwargs)
            return super().generate(**kwargs)

    return run_refinement(root, model='test-cloud-model', feedback_ids=[identity],
                          backend_factory=RecordingBackend)


@pytest.fixture
def prepared_cloud_report(tmp_path):
    pytest.importorskip('harness2')
    _, _, identity = initialize(tmp_path)
    return identity, cloud_report(tmp_path, identity)


def test_selected_feedback_reaches_real_upstream_proposer_only_and_never_claims_fix(tmp_path, monkeypatch):
    pytest.importorskip('harness2')
    secret = 'private-feedback-secret-1234'
    monkeypatch.setenv('GEMINI_API_KEY', secret)
    marker = 'UNVERIFIED-CITATION-OBSERVATION'
    registry, bundle, identity = initialize(tmp_path, marker + ' bearer ' + secret)
    before = registry.status()
    calls = []
    report = cloud_report(tmp_path, identity, calls)
    assert report['ledger']['R'] == 4 and report['ledger']['P'] == 3
    assert report['model_calls'] == 23 and not report['offline']
    assert report['feedback_ids'] == [identity]
    assert report['feedback_addressed_verified'] is False
    assert report['activated'] is False and registry.status() == before
    proposer = [call for call in calls if call['role'] == 'proposer']
    executors = [call for call in calls if call['role'] == 'executor']
    assert len(proposer) == 3
    assert all(marker in call['contents'][0].parts[0].text for call in proposer)
    assert all('unverified task data' in call['system'] for call in proposer)
    assert all(marker not in str(call['contents']) for call in executors)
    assert all(secret not in str(call['contents']) for call in calls)
    artifact = Path(report['run_dir']) / 'feedback.json'
    assert secret not in artifact.read_text()
    assert '[redacted]' in artifact.read_text()
    assert report['artifact_sha256']['feedback.json']
    gate = candidate_check(tmp_path, Path(report['run_dir']).name)
    assert not any('manifest' in reason or 'feedback provenance' in reason for reason in gate['blockers'])
    assert any('no measured gain' in reason for reason in gate['blockers'])
    # Editing a selected note after execution cannot retain its provenance.
    document = json.loads(artifact.read_text())
    document['notes'][0]['text'] = 'Replaced observation'
    artifact.write_text(json.dumps(document))
    gate = candidate_check(tmp_path, Path(report['run_dir']).name)
    assert any('feedback provenance' in reason for reason in gate['blockers'])


def test_selection_rejects_duplicates_wrong_scope_and_stale_bundle(tmp_path):
    registry, bundle, identity = initialize(tmp_path)
    with pytest.raises(ValueError, match='distinct'):
        selected_feedback(tmp_path, [identity, identity], bundle.digest)
    with pytest.raises(ValueError, match='observation'):
        selected_feedback(tmp_path, ['unknown'], bundle.digest)
    library = ExperienceLibrary(tmp_path)
    other = library.feedback('Wrong project', 'other', project='/different/project',
                             model='test-voice-model', bundle=bundle.digest)
    with pytest.raises(ValueError, match='project'):
        selected_feedback(tmp_path, [other['id']], bundle.digest)
    different = registry.register({**seed_bundle(), 'instructions': 'A different research harness.'})
    registry.activate(different.digest)
    with pytest.raises(ValueError, match='bundle'):
        selected_feedback(tmp_path, [identity], different.digest)


@pytest.mark.asyncio
async def test_cloud_job_uses_one_explicit_credential_and_recovers_result(tmp_path, monkeypatch, prepared_cloud_report):
    identity, report = prepared_cloud_report
    secret = 'cloud-key-only-in-child-env'
    monkeypatch.setenv('OTHER_API_KEY', 'must-not-be-forwarded')
    monkeypatch.setenv('GEMINI_API_KEY', 'not-the-selected-key')
    spawned = []

    async def spawn(*arguments, **kwargs):
        spawned.append(arguments)
        assert '--offline' not in arguments
        assert arguments[arguments.index('--model') + 1] == 'test-cloud-model'
        assert arguments[arguments.index('--feedback-id') + 1] == identity
        assert kwargs['env']['GEMINI_API_KEY'] == secret
        assert 'OTHER_API_KEY' not in kwargs['env']
        assert secret not in str(arguments)
        assert kwargs['start_new_session'] is True
        stdout, stderr = asyncio.StreamReader(), asyncio.StreamReader()
        stdout.feed_data(json.dumps(report).encode())
        stdout.feed_eof()
        stderr.feed_eof()
        process = SimpleNamespace(pid=54321, returncode=0, stdout=stdout, stderr=stderr)

        async def wait():
            return 0

        process.wait = wait
        return process

    monkeypatch.setattr(asyncio, 'create_subprocess_exec', spawn)
    jobs = LocalHarnessJobs(tmp_path)
    item = jobs.start_refinement('test-cloud-model', [identity], api_key=secret)
    try:
        await asyncio.wait_for(jobs.task, 5)
        result = jobs.status(item['id'])
        assert result['status'] == 'completed', result
        assert result['offline'] is False and result['feedback_addressed_verified'] is False
        assert result['verified_improvement'] is False and result['activated'] is False
        assert len(spawned) == 1
        raw = (tmp_path / 'checks' / item['id'] / 'job.json').read_text()
        assert secret not in raw
        recovered = LocalHarnessJobs(tmp_path)
        assert recovered.status(item['id'])['status'] == 'completed'
        await recovered.close()
    finally:
        await asyncio.wait_for(jobs.close(), 5)


@pytest.mark.asyncio
async def test_cloud_start_requires_model_key_and_explicit_valid_feedback(tmp_path, monkeypatch):
    _, _, identity = initialize(tmp_path)
    monkeypatch.delenv('GEMINI_API_KEY', raising=False)
    jobs = LocalHarnessJobs(tmp_path)
    try:
        with pytest.raises(ValueError, match='model'):
            jobs.start_refinement('-bad', [identity], api_key='configured-key')
        with pytest.raises(ValueError, match='API key'):
            jobs.start_refinement('test-cloud-model', [identity])
        with pytest.raises(ValueError, match='observation'):
            jobs.start_refinement('test-cloud-model', ['unknown'], api_key='configured-key')
        assert jobs.jobs == {} and jobs.process is None
    finally:
        await jobs.close()
