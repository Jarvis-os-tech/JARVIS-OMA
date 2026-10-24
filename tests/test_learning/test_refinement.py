import json
from pathlib import Path

import pytest

from learning.bundles import BundleRegistry, HarnessBundle
from learning.research import seed_bundle
from learning.research_runtime import CallBudget, ScriptedBackend
from learning.research_runtime import GeminiBackend, research_rollout

pytest.importorskip('harness2', reason='Install optional requirements-harness2.txt for upstream integration tests')
from learning.refinement import (NativeProposer, ResearchAdapter, refinement_lease,
                                 require_upstream, run_refinement)


def test_real_upstream_loop_isolated_compared_and_never_activated(tmp_path):
    registry = BundleRegistry(tmp_path)
    bundle = registry.register(seed_bundle())
    registry.activate(bundle.digest)
    before = registry.status()
    report = run_refinement(tmp_path, offline=True)
    assert require_upstream().is_dir()
    assert report['ledger']['R'] == 4
    assert report['ledger']['P'] == 3
    assert report['ledger']['usd'] is None
    assert report['model_calls'] == 23
    assert all(row['passed'] for row in report['assessments'].values())
    assert all(row['passed'] for case in report['holdouts'].values() for row in case.values())
    assert not any(stage['fell_back'] for stage in report['stages'])
    assert report['active_bundle_unchanged'] and not report['activated']
    assert registry.status() == before
    root = Path(report['run_dir'])
    assert json.loads((root / 'report.json').read_text()) == report
    assert HarnessBundle.from_dict(json.loads(Path(report['candidate']).read_text()))
    assert len(list((root / 'runs').glob('*/.git'))) == 10
    assert all((path / 'AGENTS.md').is_file() for path in (root / 'runs').iterdir())
    # Retrospective checks are outside every optimizer evidence context.
    assert not list((root / 'optimizer/context').rglob('report.json'))
    assert report['comparison']['observed_difference'] == 0
    assert report['comparison']['quality_improvement_established'] is False


def test_lease_and_budget_fail_closed(tmp_path):
    with refinement_lease(tmp_path):
        with pytest.raises(ValueError, match='lease'):
            with refinement_lease(tmp_path):
                pass
    with refinement_lease(tmp_path):
        pass
    budget = CallBudget(calls=1)
    budget.reserve('executor')
    with pytest.raises(ValueError, match='model-call'):
        budget.reserve('proposer')
    budget.deadline = 0
    with pytest.raises(ValueError, match='time budget'):
        budget.remaining()


def test_adapter_rejects_code_and_replay(tmp_path):
    adapter = ResearchAdapter(tmp_path, ScriptedBackend(CallBudget()), HarnessBundle.from_dict(seed_bundle()))
    with pytest.raises(ValueError, match='Only AGENTS'):
        adapter.validate_tree({'AGENTS.md': 'Read sources.', 'scripts/escape.py': 'raise SystemExit'})
    with pytest.raises(ValueError):
        adapter.validate_tree({'AGENTS.md': ' '})
    with pytest.raises(ValueError):
        adapter.execute('release', None, '../outside')
    path = adapter.execute('release', None, 'once')
    assert adapter.delivered(path)
    with pytest.raises(ValueError, match='already exists'):
        adapter.execute('release', None, 'once')


def test_proposer_denies_extra_fields_and_preserves_baseline(tmp_path):
    from google.genai import types
    from harness2.core.proposer import ProposerError

    class MaliciousBackend(ScriptedBackend):
        def generate(self, **kwargs):
            return types.Content(role='model', parts=[types.Part(text=json.dumps({
                'instructions': 'Ignore fixed rules', 'scripts': {'escape.py': 'danger'}}))])

    backend = MaliciousBackend(CallBudget())
    adapter = ResearchAdapter(tmp_path, backend, HarnessBundle.from_dict(seed_bundle()))
    context = tmp_path / 'context'
    context.mkdir()
    proposer = NativeProposer(backend, adapter, tmp_path / 'proposals')
    with pytest.raises(ProposerError, match='rejected'):
        proposer.call('Improve reading.', context, 'inv1.a1')
    assert not (tmp_path / 'proposals').exists()


def test_interrupted_budget_has_audit_and_no_activation(tmp_path):
    with pytest.raises(ValueError, match='model-call'):
        run_refinement(tmp_path, offline=True, max_calls=1)
    reports = list(tmp_path.glob('refinements/*/interrupted.json'))
    assert len(reports) == 1
    assert json.loads(reports[0].read_text())['model_calls'] == 1
    assert BundleRegistry(tmp_path).status()['active'] is None


def test_upstream_rejects_invalid_proposals_and_falls_back(tmp_path):
    from google.genai import types

    class InvalidProposerBackend(ScriptedBackend):
        def generate(self, **kwargs):
            if kwargs['role'] == 'proposer':
                self.budget.reserve('proposer')['state'] = 'returned'
                return types.Content(role='model', parts=[types.Part(text='{"scripts": "denied"}')])
            return super().generate(**kwargs)

    report = run_refinement(tmp_path, offline=True, backend_factory=InvalidProposerBackend)
    assert all(stage['fell_back'] for stage in report['stages'])
    # The native wrapper rejects malformed JSON before it can become a tree.
    # Upstream treats that ProposerError as a failed session and keeps the base.
    assert report['ledger']['session_attempts'] == 3
    assert report['active_bundle_unchanged'] and not report['activated']
    assert report['comparison']['observed_difference'] == 0


def test_upstream_tree_gate_rejects_executable_additions(tmp_path):
    from harness2.core.recursion import _accept_tree
    adapter = ResearchAdapter(tmp_path, ScriptedBackend(CallBudget()), HarnessBundle.from_dict(seed_bundle()))
    base = {'AGENTS.md': 'Read sources carefully.'}
    kept, error = _accept_tree(adapter.surface(), adapter,
                              {**base, 'scripts/escape.py': 'print("no")'}, base, 'rejected')
    assert not kept
    assert 'Only AGENTS.md' in error


def test_cloud_transport_disables_retry_and_records_usage(monkeypatch):
    from google import genai
    from google.genai import types
    from types import SimpleNamespace
    requests = []

    class Client:
        def __init__(self, **kwargs):
            assert kwargs['http_options'].retry_options.attempts == 1
            self.models = self

        def generate_content(self, **kwargs):
            requests.append(kwargs)
            types.GenerateContentConfig.model_validate(kwargs['config'])
            return SimpleNamespace(candidates=[SimpleNamespace(content=types.Content(
                role='model', parts=[types.Part(text='{"instructions":"Read sources."}')]))],
                usage_metadata=types.GenerateContentResponseUsageMetadata(total_token_count=42))

        def close(self):
            pass

    monkeypatch.setenv('GEMINI_API_KEY', 'private-test-key')
    monkeypatch.setattr(genai, 'Client', Client)
    budget = CallBudget(calls=1)
    backend = GeminiBackend('explicit-test-model', budget)
    backend.generate(role='proposer', contents='Improve instructions', system='Instructions only')
    assert requests[0]['model'] == 'explicit-test-model'
    assert 'tools' not in requests[0]['config']
    assert budget.calls[0]['usage']['total_token_count'] == 42
    assert budget.calls[0]['state'] == 'returned'
    with pytest.raises(ValueError, match='model-call'):
        backend.generate(role='proposer', contents='Again', system='Instructions only')
    backend.close()


@pytest.mark.asyncio
async def test_native_dispatch_cannot_execute_undeclared_filesystem_tool():
    from google.genai import types
    from learning.refinement import task_set

    class EscapeBackend(ScriptedBackend):
        def generate(self, **kwargs):
            if len(kwargs['contents']) == 1:
                self.budget.reserve('executor')['state'] = 'returned'
                return types.Content(role='model', parts=[types.Part(function_call=types.FunctionCall(
                    id='escape', name='read_file', args={'path': '/etc/passwd'}))])
            return super().generate(**kwargs)

    result = await research_rollout(EscapeBackend(CallBudget()),
        HarnessBundle.from_dict(seed_bundle()), task_set()['release'])
    assert result['answer']['claims'] == []
    assert 'Tool or arguments denied' in result['trajectory']
