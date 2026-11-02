import json

import pytest

from jarvis_control.outcomes import classify_result


@pytest.mark.parametrize('value,status', [
    ({'status': 'blocked'}, 'blocked'),
    ({'status': 'success', 'verified': False}, 'unverified'),
    ({'status': 'dispatched', 'reobserve_required': True}, 'unverified'),
    ({'status': 'unverified_effect'}, 'unverified'),
    ({'status': 'queued', 'id': 'task'}, 'queued'),
    ({'task': {'status': 'running'}}, 'running'),
    ({'status': 'completed', 'total_steps': 3, 'completed_steps': 1}, 'partial'),
    ({'status': 'completed', 'steps': [{'status': 'completed'}, {'status': 'failed'}]}, 'partial'),
    ({'status': 'success', 'completed': False}, 'incomplete'),
    ({'status': 'completed', 'steps': [{'status': 'success', 'verified': False}]}, 'partial'),
    ({'status': 'completed', 'steps': [{'completed': False}]}, 'partial'),
    ({'status': 'completed', 'output': 'ERROR: no action executed'}, 'failed'),
    ({'success': False, 'error': 'No connection'}, 'failed'),
    ({'status': 'unknown', 'error': 'Dispatch timed out'}, 'unknown'),
    ('[dry-run] would open app', 'dry_run'),
    ('ERROR: This action needs spoken confirmation.', 'needs_confirmation'),
])
def test_incomplete_receipts_are_not_completed(value, status):
    assert classify_result(value).status == status
    assert not classify_result(value).completed
    if isinstance(value, dict):
        assert classify_result(json.dumps(value)).status == status


@pytest.mark.parametrize('value', [
    'Workspace 2 is active; verified',
    {'status': 'written', 'verified': True},
    {'status': 'success', 'verified': True},
    {'status': 'completed', 'completed_steps': 3, 'total_steps': 3},
])
def test_completed_results_remain_compatible(value):
    outcome = classify_result(value)
    assert outcome.ok and outcome.completed


@pytest.mark.parametrize('value', [None, '', '   '])
def test_empty_result_is_not_proof_of_success(value):
    assert not classify_result(value).completed
