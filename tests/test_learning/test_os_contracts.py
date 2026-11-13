import copy
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from learning.os_contracts import (
    MAX_INPUT_BYTES, canonical, check_change_paths, parse_incident,
    parse_proposal, phase_one_policy,
)


NOW = datetime(2026, 11, 4, 12, tzinfo=timezone.utc)
BASELINE = 'a' * 64
ROOT = Path(__file__).resolve().parents[2]


def timestamp(delta=timedelta()):
    return (NOW + delta).isoformat().replace('+00:00', 'Z')


@pytest.fixture
def incident_data():
    return {'schema_version': 1, 'producer': 'fixture', 'source_incident_id': 'occurrence-1',
            'observed_at': timestamp(), 'component': 'fixture-user-service',
            'kind': 'failed_user_service', 'state': 'failed', 'baseline_sha256': BASELINE,
            'evidence': [{'id': 'active', 'name': 'active_state', 'value': 'failed',
                          'observed_at': timestamp()}]}


def parse(data):
    return parse_incident(canonical(data), baseline_sha256=BASELINE, now=NOW)


def proposal(incident, **changes):
    return {'schema_version': 1, 'incident_key': incident.key, 'incident_revision': incident.revision,
            'baseline_sha256': BASELINE, 'diagnosis_code': 'unit_failed',
            'supporting_observation_ids': ['active'], 'recommended_action_code': 'inspect_failure_context',
            'limitations': ['synthetic_only', 'no_root_cause_verified'], **changes}


def test_canonical_snapshot_and_identity_bind_every_revision(incident_data):
    first = parse(incident_data)
    reordered = parse_incident(json.dumps(incident_data, sort_keys=True, indent=2).encode(),
                               baseline_sha256=BASELINE, now=NOW)
    assert first == reordered
    assert first.evaluation_key('b' * 64, 'c' * 64) == reordered.evaluation_key('b' * 64, 'c' * 64)
    incident_data['observed_at'] = timestamp(timedelta(seconds=1))
    second = parse(incident_data)
    assert second.key == first.key
    assert second.revision != first.revision
    assert second.evaluation_key('b' * 64, 'c' * 64) != first.evaluation_key('b' * 64, 'c' * 64)
    assert first.evaluation_key('b' * 64, 'd' * 64) != first.evaluation_key('b' * 64, 'c' * 64)
    assert first.evaluation_key('d' * 64, 'c' * 64) != first.evaluation_key('b' * 64, 'c' * 64)
    with pytest.raises(ValueError):
        first.evaluation_key('not-a-hash', 'c' * 64)
    exported = first.document()
    exported['evidence'].clear()
    assert first.document()['evidence']
    changed = first.document()
    changed['baseline_sha256'] = 'b' * 64
    third = parse_incident(canonical(changed), baseline_sha256='b' * 64, now=NOW)
    assert third.key == first.key and third.revision != first.revision


@pytest.mark.parametrize('field,value', [
    ('schema_version', True), ('schema_version', 1.0), ('producer', 'omarchy-healer'),
    ('component', 'jarvis-voice.service'), ('component', ['fixture-user-service']),
    ('kind', 'run_command'), ('state', 'active'), ('source_incident_id', '../secret'),
    ('source_incident_id', 'x' * 129), ('source_incident_id', 'α'),
    ('baseline_sha256', 'b' * 64), ('baseline_sha256', 'A' * 64),
    ('observed_at', '2026-11-04T12:00:00+00:00'), ('observed_at', '2026-02-30T12:00:00Z'),
    ('observed_at', timestamp(-timedelta(hours=24, microseconds=1))),
    ('observed_at', timestamp(timedelta(minutes=5, microseconds=1))),
    ('evidence', {}), ('evidence', [{}] * 33),
])
def test_incident_rejects_untrusted_values(incident_data, field, value):
    incident_data[field] = value
    with pytest.raises(ValueError):
        parse(incident_data)


@pytest.mark.parametrize('delta', [-timedelta(hours=24), timedelta(minutes=5)])
def test_time_window_includes_exact_boundaries(incident_data, delta):
    incident_data['observed_at'] = timestamp(delta)
    incident_data['evidence'][0]['observed_at'] = timestamp(delta)
    assert parse(incident_data)


@pytest.mark.parametrize('field,value', [
    ('id', 'active/../../'), ('name', 'journal'), ('value', 'Bearer synthetic-secret'),
    ('value', True), ('observed_at', timestamp(-timedelta(days=2))),
])
def test_evidence_is_allowlisted_and_fresh(incident_data, field, value):
    incident_data['evidence'][0][field] = value
    with pytest.raises(ValueError):
        parse(incident_data)


def test_ambiguous_keys_unknown_fields_and_duplicate_evidence_fail(incident_data):
    raw = canonical(incident_data)
    for invalid in [raw.replace(b'"schema_version":1', b'"schema_version":1,"schema_version":1'),
                    raw.replace(b'"value":"failed"', b'"value":"failed","value":"active"'),
                    raw[:-1] + b',"command":"sensitive-command"}',
                    raw.replace(b'"schema_version":1', b'"schema_version":NaN'),
                    raw.replace(b'"schema_version":1', b'"schema_version":1e999'),
                    b'{"x":"\xff"}', b'{"x":"\\ud800"}', b'[' * 2000,
                    b' ' * (MAX_INPUT_BYTES + 1)]:
        with pytest.raises(ValueError):
            parse_incident(invalid, baseline_sha256=BASELINE, now=NOW)
    incident_data['evidence'].append(copy.deepcopy(incident_data['evidence'][0]))
    with pytest.raises(ValueError):
        parse(incident_data)


def test_trusted_clock_and_state_are_checked(incident_data):
    with pytest.raises(ValueError, match='timezone-aware'):
        parse_incident(canonical(incident_data), baseline_sha256=BASELINE, now=NOW.replace(tzinfo=None))
    incident_data['state'] = 'unknown'
    with pytest.raises(ValueError, match='contradicts'):
        parse(incident_data)


def test_valid_proposal_and_unsupported_claims(incident_data):
    incident = parse(incident_data)
    assert parse_proposal(canonical(proposal(incident)), incident=incident)['diagnosis_code'] == 'unit_failed'
    invalid = [
        {'schema_version': True}, {'incident_revision': 'b' * 64}, {'incident_key': 'b' * 64},
        {'baseline_sha256': 'b' * 64}, {'command': 'restart voice'},
        {'recommended_action_code': 'restart_service'}, {'diagnosis_code': 'root_cause_verified'},
        {'supporting_observation_ids': []}, {'supporting_observation_ids': ['absent']},
        {'supporting_observation_ids': ['active', 'active']},
        {'limitations': ['no_root_cause_verified']}, {'limitations': ['synthetic_only', 'private text']},
        {'limitations': ['synthetic_only', 'no_root_cause_verified', 'evidence_conflicting']},
    ]
    for changes in invalid:
        with pytest.raises(ValueError):
            parse_proposal(canonical(proposal(incident, **changes)), incident=incident)


def test_absence_conflict_and_unavailable_are_distinct(incident_data):
    incident_data['evidence'] = []
    incident_data['state'] = 'unknown'
    missing = parse(incident_data)
    data = proposal(missing, diagnosis_code='insufficient_evidence', supporting_observation_ids=[],
                    recommended_action_code='gather_evidence',
                    limitations=['synthetic_only', 'no_root_cause_verified', 'evidence_missing'])
    assert parse_proposal(canonical(data), incident=missing)
    incident_data['evidence'] = [{'id': 'load', 'name': 'load_state', 'value': 'not-found',
                                  'observed_at': timestamp()}]
    unavailable = parse(incident_data)
    data = proposal(unavailable, diagnosis_code='unit_unavailable', supporting_observation_ids=['load'],
                    recommended_action_code='inspect_unit_configuration')
    assert parse_proposal(canonical(data), incident=unavailable)
    incident_data['evidence'].append({'id': 'loaded', 'name': 'load_state', 'value': 'loaded',
                                      'observed_at': timestamp()})
    conflict = parse(incident_data)
    with pytest.raises(ValueError):
        parse_proposal(canonical(proposal(conflict, diagnosis_code='unit_unavailable',
                       supporting_observation_ids=['load'],
                       recommended_action_code='inspect_unit_configuration')), incident=conflict)
    assert parse_proposal(canonical(proposal(conflict, diagnosis_code='insufficient_evidence',
                          supporting_observation_ids=['load', 'loaded'], recommended_action_code='gather_evidence',
                          limitations=['synthetic_only', 'no_root_cause_verified', 'evidence_conflicting'])),
                          incident=conflict)


@pytest.mark.parametrize('path', [
    'audio/new.py', 'voice_layer/daemon.py', 'voice_layer/new.py',
    'audio/.voice_lock.json',
    'bin/jarvis-voice', 'scripts/verify_voice_lock.py', 'scripts',
    'learning/os_contracts.py', 'tests/test_learning/test_os_contracts.py',
    '../outside', '/etc/passwd', './learning/new.py', 'learning/../audio/new.py',
    'learning//new.py', 'learning\\new.py', '', '.', 'audio/\x00',
])
def test_candidate_path_rejection(path):
    with pytest.raises(ValueError):
        check_change_paths(ROOT, [path])


def test_path_check_does_not_grant_execution_or_activation():
    result = check_change_paths(ROOT, ['learning/future_os_adapter.py'])
    assert result == {'checked_paths': ['learning/future_os_adapter.py'], 'path_check_passed': True,
                      'execution_allowed': False, 'activation_allowed': False}


def test_manifests_fail_closed_and_links_cannot_hide_targets(tmp_path):
    for folder, filename in [('audio', '.voice_lock.json')]:
        (tmp_path / folder).mkdir()
        (tmp_path / folder / filename).write_text(json.dumps({
            'schema_version': 1, 'status': 'locked', 'protected_roots': ['audio'],
            'locked_files': {'legacy.py': {}}}))
    outside = tmp_path / 'elsewhere'
    outside.mkdir()
    (tmp_path / 'linked').symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match='Linked'):
        check_change_paths(tmp_path, ['linked/new.py'])
    (tmp_path / 'dangling').symlink_to(tmp_path / 'missing')
    with pytest.raises(ValueError, match='Linked'):
        check_change_paths(tmp_path, ['dangling'])
    with pytest.raises(ValueError, match='protected'):
        check_change_paths(tmp_path, ['legacy.py'])
    target = outside / 'original'
    target.write_text('unchanged')
    os.link(target, tmp_path / 'hardlink')
    with pytest.raises(ValueError, match='unlinked'):
        check_change_paths(tmp_path, ['hardlink'])
    with pytest.raises(ValueError, match='individual'):
        check_change_paths(tmp_path, ['elsewhere'])
    assert target.read_text() == 'unchanged'
    (tmp_path / 'audio/.voice_lock.json').write_text('{}')
    with pytest.raises(ValueError, match='manifest'):
        check_change_paths(tmp_path, ['ordinary.py'])


def test_cli_validates_without_side_effects_and_does_not_echo_secrets(incident_data, tmp_path):
    # A standalone CLI must work without importing any voice/provider runtime.
    command = [sys.executable, '-m', 'learning.os_contracts']
    policy = subprocess.run(command + ['policy'], capture_output=True, text=True, check=True, cwd=ROOT)
    assert json.loads(policy.stdout) == phase_one_policy()
    incident_data['observed_at'] = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    incident_data['evidence'][0]['observed_at'] = incident_data['observed_at']
    valid = subprocess.run(command + ['validate-incident', '--baseline', BASELINE],
                           input=canonical(incident_data), capture_output=True, cwd=ROOT)
    assert valid.returncode == 0 and json.loads(valid.stdout)['disposition'] == 'validation_only'
    invalid = subprocess.run(command + ['validate-incident', '--baseline', BASELINE],
                             input=b'{"secret":"synthetic-secret-value"}', capture_output=True, cwd=ROOT)
    assert invalid.returncode == 1 and b'synthetic-secret-value' not in invalid.stdout + invalid.stderr
    incident = parse_incident(canonical(incident_data), baseline_sha256=BASELINE, now=datetime.now(timezone.utc))
    incident_file = tmp_path / 'incident.json'
    incident_file.write_bytes(canonical(incident_data))
    valid_proposal = subprocess.run(command + ['validate-proposal', '--baseline', BASELINE,
                                              '--incident', str(incident_file)],
                                   input=canonical(proposal(incident)), capture_output=True, cwd=ROOT)
    assert valid_proposal.returncode == 0, valid_proposal.stderr
    assert json.loads(valid_proposal.stdout)['activation_allowed'] is False
    assert list(tmp_path.iterdir()) == [incident_file]


def test_policy_is_fresh_data_and_future_limits_are_not_claimed_enforced():
    policy = phase_one_policy()
    assert not any(policy[name] for name in ('voice_repairs_allowed', 'candidate_execution_allowed',
                                            'activation_allowed', 'cloud_calls_allowed', 'network_access_allowed'))
    assert policy['later_worker_limits']['enforced'] is False
    policy['later_worker_limits']['workers'] = 999
    assert phase_one_policy()['later_worker_limits']['workers'] == 1


@pytest.mark.parametrize('kind', ['fifo', 'symlink', 'oversized'])
def test_cli_rejects_nonregular_linked_and_oversized_incident_files(tmp_path, kind):
    path = tmp_path / 'incident'
    if kind == 'fifo':
        os.mkfifo(path)
    elif kind == 'symlink':
        path.symlink_to(tmp_path / 'absent')
    else:
        path.write_bytes(b' ' * (MAX_INPUT_BYTES + 1))
    result = subprocess.run([sys.executable, '-m', 'learning.os_contracts', 'validate-proposal',
                             '--baseline', BASELINE, '--incident', str(path)],
                            input=b'{}', capture_output=True, cwd=ROOT, timeout=5)
    assert result.returncode == 1
    assert result.stderr == b'{"valid": false, "error": "Contract or protection check failed"}\n'


def test_cli_path_checks_are_checks_not_deployment():
    command = [sys.executable, '-m', 'learning.os_contracts', 'check-paths']
    allowed = subprocess.run(command + ['learning/future_os_adapter.py'], capture_output=True, cwd=ROOT)
    assert allowed.returncode == 0
    assert json.loads(allowed.stdout)['activation_allowed'] is False
    denied = subprocess.run(command + ['bin/jarvis-voice'], capture_output=True, cwd=ROOT)
    assert denied.returncode == 1
