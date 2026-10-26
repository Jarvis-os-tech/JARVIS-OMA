"""Synthetic trusted-local report fixtures; these are not cloud quality evidence."""
import hashlib
import json

import pytest

from learning.bundles import BundleRegistry, HarnessBundle
from learning.refinement import UPSTREAM_REVISION, save_json, task_set
from learning.trials import candidate_check, activate_trial, rollback_trial, trial_voice_tests


def prepared_trial(tmp_path, *, offline=False, baseline_failure=True):
    registry = BundleRegistry(tmp_path)
    base = registry.register({'version': 1, 'role': 'research', 'source': 'test fixture',
                              'instructions': 'Read the supplied notice.'})
    registry.activate(base.digest)
    run_id = 'a' * 32
    root = tmp_path / 'refinements' / run_id
    root.mkdir(parents=True)
    candidate = HarnessBundle.from_dict({**base.document(), 'instructions': 'Read all notices and quote exact sentences.',
                                         'source': 'test candidate'})
    save_json(root / 'candidate.json', candidate.document())
    save_json(root / 'started.json', {'offline': offline, 'model': 'unit-test-text',
        'baseline_bundle': base.digest, 'upstream_revision': UPSTREAM_REVISION})
    cases = task_set()
    labels = {label: 'release' for label in ('base', 'inv1', 'dom1', 'c1')}
    for task in ('transfer', 'missing', 'conflict'):
        labels.update({task + '-' + label: task for label in ('baseline', 'candidate')})
    for label, task_id in labels.items():
        directory = root / 'runs' / label
        directory.mkdir(parents=True)
        instructions = base.instructions if label == 'base' or label.endswith('-baseline') else candidate.instructions
        (directory / 'AGENTS.md').write_text(instructions)
        bundle = HarnessBundle.from_dict({**base.document(), 'instructions': instructions})
        save_json(directory / 'started.json', {'task': task_id, 'bundle': bundle.digest, 'model': 'unit-test-text'})
        claims = [{'claim': text, 'source': source, 'quote': text} for source, text in cases[task_id]['sources'].items()]
        if task_id == 'missing' or (label == 'base' and baseline_failure):
            claims = []
        save_json(directory / 'result.json', {'model': 'unit-test-text', 'answer': {
            'claims': claims, 'gap': 'No notice available.' if not claims else None}})
    report = {'provider': 'unit-test-text', 'offline': offline, 'upstream_revision': UPSTREAM_REVISION,
        'active_bundle_unchanged': True, 'activated': False,
        'stages': [{'label': label, 'fell_back': False, 'error': ''} for label in ('inv1', 'dom1', 'c1')]}
    report['artifact_sha256'] = {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
                                for path in root.rglob('*') if path.is_file()}
    save_json(root / 'report.json', report)
    return registry, run_id, root, candidate


def test_reviewed_trial_activation_voice_plan_and_rollback(tmp_path):
    registry, run_id, root, candidate = prepared_trial(tmp_path)
    before = registry.status()
    gate = candidate_check(tmp_path, run_id)
    assert gate['eligible_for_controlled_trial'], gate
    assert gate['observed_gain'] == 1
    assert registry.status() == before
    result = activate_trial(tmp_path, run_id, 'Reviewed synthetic fixture for gate testing')
    assert result['restart_required'] and result['trial']
    assert registry.active() == candidate
    assert trial_voice_tests(tmp_path)['bundle_for_next_startup'] == candidate.digest
    assert len(trial_voice_tests(tmp_path)['tests']) == 6
    assert rollback_trial(tmp_path, run_id)['active'] == before['active']


@pytest.mark.parametrize('offline,tied', [(True, False), (False, True)])
def test_offline_and_tied_trials_are_blocked(tmp_path, offline, tied):
    registry, run_id, _, _ = prepared_trial(tmp_path, offline=offline, baseline_failure=not tied)
    before = registry.status()
    gate = candidate_check(tmp_path, run_id)
    assert not gate['eligible_for_controlled_trial']
    with pytest.raises(ValueError, match='Trial blocked'):
        activate_trial(tmp_path, run_id, 'review')
    assert registry.status() == before


@pytest.mark.parametrize('relative', ['candidate.json', 'runs/c1/result.json', 'runs/transfer-candidate/AGENTS.md'])
def test_changed_artifacts_are_blocked(tmp_path, relative):
    _, run_id, root, _ = prepared_trial(tmp_path)
    with (root / relative).open('a') as stream:
        stream.write(' ')
    gate = candidate_check(tmp_path, run_id)
    assert not gate['eligible_for_controlled_trial']
    assert any('Artifact changed' in reason for reason in gate['blockers'])


def test_stale_baseline_symlinks_and_unrelated_rollback_are_denied(tmp_path):
    registry, run_id, root, _ = prepared_trial(tmp_path)
    activate_trial(tmp_path, run_id, 'review')
    other = registry.register({**registry.active().document(), 'instructions': 'Another selected harness.'})
    registry.activate(other.digest)
    with pytest.raises(ValueError, match='unrelated'):
        rollback_trial(tmp_path, run_id)
    assert not candidate_check(tmp_path, run_id)['eligible_for_controlled_trial']
    path = root / 'runs/c1/result.json'
    path.unlink()
    path.symlink_to(root / 'candidate.json')
    assert not candidate_check(tmp_path, run_id)['eligible_for_controlled_trial']
    with pytest.raises(ValueError):
        candidate_check(tmp_path, '../escape')


def test_recomputed_checks_reject_failed_candidate_even_if_report_claims_success(tmp_path):
    _, run_id, root, _ = prepared_trial(tmp_path)
    path = root / 'runs/missing-candidate/result.json'
    value = json.loads(path.read_text())
    value['answer'] = {'claims': [], 'gap': None}
    path.write_text(json.dumps(value))
    report_path = root / 'report.json'
    report = json.loads(report_path.read_text())
    report['artifact_sha256'][str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
    report['comparison'] = {'quality_improvement_established': True}
    report_path.write_text(json.dumps(report))
    gate = candidate_check(tmp_path, run_id)
    assert not gate['eligible_for_controlled_trial']
    assert any('independently recomputed' in reason for reason in gate['blockers'])


def test_actual_offline_refinement_manifest_is_complete_but_trial_is_blocked(tmp_path):
    pytest.importorskip('harness2')
    from learning.refinement import run_refinement
    from learning.research import seed_bundle
    registry = BundleRegistry(tmp_path)
    base = registry.register(seed_bundle())
    registry.activate(base.digest)
    report = run_refinement(tmp_path, offline=True)
    gate = candidate_check(tmp_path, report['run_dir'].split('/')[-1])
    assert not gate['eligible_for_controlled_trial']
    assert all(gate['checks'].values())
    assert any('Offline' in reason for reason in gate['blockers'])
    assert any('no measured gain' in reason for reason in gate['blockers'])
    assert not any('Artifact' in reason or 'manifest' in reason for reason in gate['blockers'])
