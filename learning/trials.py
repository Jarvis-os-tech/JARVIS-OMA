"""Trusted-local evidence gate for explicit, reversible research guidance trials."""
import hashlib
import json
import os
from pathlib import Path
import re

from .bundles import BundleRegistry, HarnessBundle
from .research import ResearchCorpus, assess
from .refinement import UPSTREAM_REVISION, refinement_lease, save_json, task_set
from .voice_tests import checklist


def read_artifact(root, relative):
    path = root / relative
    for component in (path, *path.parents):
        if component.is_symlink():
            raise ValueError('Trial artifacts must not contain symlinks')
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(descriptor, 'rb') as stream:
        data = stream.read(262145)
    if len(data) > 262144:
        raise ValueError('Trial artifact exceeds read limit')
    return data


def trial_root(registry, run_id):
    if not re.fullmatch('[0-9a-f]{32}', run_id):
        raise ValueError('Use the 32-character refinement run identity')
    return registry.root / 'refinements' / run_id


def candidate_check(state_dir, run_id):
    registry = BundleRegistry(state_dir)
    root = trial_root(registry, run_id)
    blockers = []
    try:
        report = json.loads(read_artifact(root, 'report.json'))
        started = json.loads(read_artifact(root, 'started.json'))
        candidate_bytes = read_artifact(root, 'candidate.json')
        candidate = HarnessBundle.from_dict(json.loads(candidate_bytes))
        if report.get('offline') is not False or started.get('offline') is not False:
            blockers.append('Offline scripted runs cannot qualify for a live trial')
        if (not report.get('provider') or report['provider'] == 'offline-scripted' or
                report['provider'] != started.get('model')):
            blockers.append('Cloud model provenance is missing or inconsistent')
        if report.get('upstream_revision') != UPSTREAM_REVISION or started.get('upstream_revision') != UPSTREAM_REVISION:
            blockers.append('Upstream revision differs from the reviewed integration')
        baseline = registry.active()
        if baseline is None or baseline.digest != started.get('baseline_bundle'):
            blockers.append('Active baseline differs from the trial baseline; initialize and rerun')
        if report.get('active_bundle_unchanged') is not True or report.get('activated') is not False:
            blockers.append('Refinement did not preserve the activation boundary')
        stages = report.get('stages', [])
        if (len(stages) != 3 or {stage['label'] for stage in stages} != {'inv1', 'dom1', 'c1'} or
                any(stage.get('fell_back') or stage.get('error') for stage in stages)):
            blockers.append('Refinement stages are missing or contain failed proposals')
        expected = ['candidate.json', 'started.json']
        run_tasks = {label: 'release' for label in ('base', 'inv1', 'dom1', 'c1')}
        for task in ('transfer', 'missing', 'conflict'):
            run_tasks.update({task + '-' + label: task for label in ('baseline', 'candidate')})
        for label in run_tasks:
            expected.extend('runs/' + label + '/' + name for name in ('AGENTS.md', 'started.json', 'result.json'))
        hashes = report.get('artifact_sha256', {})
        if set(hashes) != set(expected):
            blockers.append('Complete artifact manifest is missing')
        for relative in expected:
            data = read_artifact(root, relative)
            if hashlib.sha256(data).hexdigest() != hashes.get(relative):
                blockers.append('Artifact changed or is unbound: ' + relative)
        checks = {}
        cases = task_set()
        for label, task_id in run_tasks.items():
            prefix = 'runs/' + label + '/'
            identity = json.loads(read_artifact(root, prefix + 'started.json'))
            instructions = read_artifact(root, prefix + 'AGENTS.md').decode()
            bundle = HarnessBundle.from_dict({**(baseline or candidate).document(), 'instructions': instructions})
            # Source attribution changes bundle identity; compare instruction content explicitly.
            expected_instructions = (baseline.instructions if baseline and
                (label == 'base' or label.endswith('-baseline')) else candidate.instructions
                if label == 'c1' or label.endswith('-candidate') else instructions)
            if instructions != expected_instructions or identity.get('task') != task_id or identity.get('model') != report.get('provider'):
                blockers.append('Run identity or harness mismatch: ' + label)
            if baseline and identity.get('bundle') != bundle.digest:
                blockers.append('Run bundle provenance mismatch: ' + label)
            if not bundle.instructions.strip():
                blockers.append('Empty run harness: ' + label)
            result = json.loads(read_artifact(root, prefix + 'result.json'))
            if result.get('model') != report.get('provider'):
                blockers.append('Result model provenance mismatch: ' + label)
            answer = result['answer']
            task = cases[task_id]
            checks[label] = assess(answer['claims'], ResearchCorpus(task['sources']),
                required_claims=list(task['sources'].values()) if task_id != 'missing' else (),
                unavailable=task_id == 'missing', gap=answer['gap'])['passed']
        candidate_labels = ['c1', 'transfer-candidate', 'missing-candidate', 'conflict-candidate']
        baseline_labels = ['base', 'transfer-baseline', 'missing-baseline', 'conflict-baseline']
        gain = sum(checks[label] for label in candidate_labels) - sum(checks[label] for label in baseline_labels)
        if not all(checks[label] for label in candidate_labels):
            blockers.append('Candidate failed an independently recomputed check')
        if gain <= 0:
            blockers.append('Candidate has no measured gain over the baseline')
        if baseline and candidate.instructions == baseline.instructions:
            blockers.append('Candidate instructions are unchanged')
        return {'run_id': run_id, 'eligible_for_controlled_trial': not blockers,
                'blockers': blockers, 'checks': checks, 'observed_gain': gain,
                'candidate_digest': candidate.digest, 'baseline_digest': baseline.digest if baseline else None,
                'scope': 'Trusted-local, narrow text research evidence; broader quality and Live voice remain unverified.'}
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        return {'run_id': run_id, 'eligible_for_controlled_trial': False,
                'blockers': blockers + ['Incomplete or invalid evidence: ' + type(error).__name__]}


def activate_trial(state_dir, run_id, note):
    if not isinstance(note, str) or not 1 <= len(note.strip()) <= 1000:
        raise ValueError('Supply a review note of 1–1000 characters')
    registry = BundleRegistry(state_dir)
    with refinement_lease(registry.root):
        gate = candidate_check(state_dir, run_id)
        if not gate['eligible_for_controlled_trial']:
            raise ValueError('Trial blocked: ' + '; '.join(gate['blockers']))
        root = trial_root(registry, run_id)
        candidate = registry.register(json.loads(read_artifact(root, 'candidate.json')))
        if candidate.digest != gate['candidate_digest']:
            raise ValueError('Candidate changed during review')
        if registry.status()['active'] != gate['baseline_digest']:
            raise ValueError('Baseline changed during review')
        # Intent first: a crash between this record and activation requires inspection.
        from .evidence import sanitize
        save_json(root / 'trial-intent.json', {'candidate': candidate.digest,
            'baseline': gate['baseline_digest'], 'review': sanitize({'note': note}), 'authority': 'local_administrator'})
        registry.activate(candidate.digest)
        return {'active': candidate.digest, 'previous': gate['baseline_digest'],
                'run_id': run_id, 'restart_required': True, 'trial': True}


def rollback_trial(state_dir, run_id):
    registry = BundleRegistry(state_dir)
    with refinement_lease(registry.root):
        intent = json.loads(read_artifact(trial_root(registry, run_id), 'trial-intent.json'))
        state = registry.status()
        if state != {'active': intent['candidate'], 'previous': intent['baseline']}:
            raise ValueError('Active selection changed; refusing to roll back an unrelated bundle')
        return {**registry.restore(), 'restart_required': True}


def trial_voice_tests(state_dir):
    registry = BundleRegistry(state_dir)
    state = registry.status()
    return {'bundle_for_next_startup': state['active'], 'restart_required_if_changed': True,
            'tests': checklist(), 'instruction': 'Run correction then recall in the same conversation. '
            'Record lag before the answer or during speech. Captured episodes identify the actual running bundle.'}
