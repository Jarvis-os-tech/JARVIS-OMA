"""Phase-one OS contracts: validation only, with no execution or activation path."""
import argparse
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys


MAX_INPUT_BYTES = 64 * 1024
OBSERVATIONS = {
    'load_state': frozenset({'loaded', 'not-found', 'error', 'unknown'}),
    'active_state': frozenset({'active', 'inactive', 'failed', 'unknown'}),
    'sub_state': frozenset({'running', 'dead', 'failed', 'unknown'}),
    'result': frozenset({'success', 'exit-code', 'signal', 'timeout', 'unknown'}),
}
ACTIONS = {
    'unit_unavailable': 'inspect_unit_configuration',
    'unit_failed': 'inspect_failure_context',
    'insufficient_evidence': 'gather_evidence',
}
LIMITATIONS = frozenset({'synthetic_only', 'no_root_cause_verified',
                         'evidence_missing', 'evidence_conflicting'})


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(',', ':'), allow_nan=False).encode('utf-8')


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def _fields(value, names):
    if type(value) is not dict or set(value) != set(names.split()):
        raise ValueError('Unexpected or missing contract fields')


def _matches(value, pattern):
    if type(value) is not str or re.fullmatch(pattern, value) is None:
        raise ValueError('Invalid contract identifier')


def _hash(value):
    _matches(value, '[0-9a-f]{64}')


def _choice(value, choices):
    if type(value) is not str or value not in choices:
        raise ValueError('Unsupported contract value')


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON key')
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError('Non-finite JSON value')


def _json(raw, limit=MAX_INPUT_BYTES):
    if type(raw) is not bytes or len(raw) > limit:
        raise ValueError('Input must be bounded UTF-8 bytes')
    try:
        value = json.loads(raw.decode('utf-8'), object_pairs_hook=_pairs,
                           parse_constant=_reject_constant)
        canonical(value)  # Reject invalid Unicode and non-finite numeric overflow.
        return value
    except (ValueError, UnicodeError, RecursionError, OverflowError):
        raise ValueError('Invalid or ambiguous JSON input') from None


def _read_file(path, limit):
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, 'rb') as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise ValueError('Contract input must be a regular file')
        raw = stream.read(limit + 1)
    if len(raw) > limit:
        raise ValueError('Contract input exceeds byte limit')
    return raw


def _timestamp(value, now):
    _matches(value, r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z')
    try:
        observed = datetime.fromisoformat(value[:-1] + '+00:00')
    except ValueError:
        raise ValueError('Invalid observation time') from None
    if not now - timedelta(hours=24) <= observed <= now + timedelta(minutes=5):
        raise ValueError('Observation outside admission time window')


@dataclass(frozen=True)
class Incident:
    """Canonical snapshot; callers cannot mutate a validated incident in place."""
    _canonical: bytes

    def document(self):
        return json.loads(self._canonical)

    @property
    def key(self):
        value = self.document()
        return digest({name: value[name] for name in ('producer', 'source_incident_id')})

    @property
    def revision(self):
        return hashlib.sha256(self._canonical).hexdigest()

    @property
    def evidence_sha256(self):
        return digest(self.document()['evidence'])

    def evaluation_key(self, evaluator_sha256, fixtures_sha256):
        _hash(evaluator_sha256)
        _hash(fixtures_sha256)
        return digest({'incident_key': self.key, 'incident_revision': self.revision,
                       'evaluator_sha256': evaluator_sha256, 'fixtures_sha256': fixtures_sha256})


def parse_incident(raw, *, baseline_sha256, now, allow_healer_metadata=False):
    """Validate fixture evidence or evidence-free historical healer metadata."""
    _hash(baseline_sha256)
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError('Admission clock must be timezone-aware')
    now = now.astimezone(timezone.utc)
    value = _json(raw)
    _fields(value, 'schema_version producer source_incident_id observed_at component '
                   'kind state baseline_sha256 evidence')
    if type(value['schema_version']) is not int or value['schema_version'] != 1:
        raise ValueError('Unsupported incident version')
    if type(allow_healer_metadata) is not bool:
        raise ValueError('Invalid incident admission profile')
    _choice(value['producer'], {'fixture', 'healer-metadata'} if allow_healer_metadata else {'fixture'})
    component = ('fixture-user-service' if value['producer'] == 'fixture'
                 else 'unidentified-user-service')
    _choice(value['component'], {component})
    _choice(value['kind'], {'failed_user_service'})
    _choice(value['state'], {'failed', 'unknown'})
    _matches(value['source_incident_id'], '[A-Za-z0-9_-]{1,128}')
    _timestamp(value['observed_at'], now)
    _hash(value['baseline_sha256'])
    if value['baseline_sha256'] != baseline_sha256:
        raise ValueError('Incident baseline does not match trusted baseline')
    evidence = value['evidence']
    if type(evidence) is not list or len(evidence) > 32:
        raise ValueError('Evidence must contain at most 32 observations')
    if value['producer'] == 'healer-metadata' and (value['state'] != 'unknown' or evidence):
        raise ValueError('Historical healer metadata cannot assert service observations')
    ids, active = set(), set()
    for row in evidence:
        _fields(row, 'id name value observed_at')
        _matches(row['id'], '[a-z0-9_-]{1,64}')
        if row['id'] in ids:
            raise ValueError('Duplicate observation identity')
        ids.add(row['id'])
        _choice(row['name'], OBSERVATIONS)
        _choice(row['value'], OBSERVATIONS[row['name']])
        _timestamp(row['observed_at'], now)
        if row['name'] == 'active_state':
            active.add(row['value'])
    if len(active) == 1 and ((value['state'] == 'failed') != (active == {'failed'})):
        raise ValueError('Incident state contradicts active-state observation')
    return Incident(canonical(value))


def _diagnosis(evidence):
    values = {}
    for row in evidence:
        values.setdefault(row['name'], set()).add(row['value'])
    unavailable = bool(values.get('load_state', set()) & {'not-found', 'error'})
    active = values.get('active_state', set())
    conflict = (any(len(items) > 1 for items in values.values()) or
                unavailable and bool(active & {'active', 'failed'}) or
                'running' in values.get('sub_state', set()) and bool(active & {'inactive', 'failed'}))
    if conflict:
        return 'insufficient_evidence', 'evidence_conflicting'
    if unavailable:
        return 'unit_unavailable', None
    if active == {'failed'}:
        return 'unit_failed', None
    return 'insufficient_evidence', 'evidence_missing'


def parse_proposal(raw, *, incident):
    """Check advisory codes and supporting evidence, never execute their suggestions."""
    if incident.document()['producer'] != 'fixture':
        raise ValueError('Real-incident proposal evaluation is not implemented')
    value = _json(raw)
    _fields(value, 'schema_version incident_key incident_revision baseline_sha256 '
                   'diagnosis_code supporting_observation_ids recommended_action_code limitations')
    if type(value['schema_version']) is not int or value['schema_version'] != 1:
        raise ValueError('Unsupported proposal version')
    document = incident.document()
    if (value['incident_key'] != incident.key or value['incident_revision'] != incident.revision or
            value['baseline_sha256'] != document['baseline_sha256']):
        raise ValueError('Proposal is not bound to this incident revision and baseline')
    _choice(value['diagnosis_code'], ACTIONS)
    _choice(value['recommended_action_code'], {ACTIONS[value['diagnosis_code']]})
    support = value['supporting_observation_ids']
    if type(support) is not list or len(support) > 32:
        raise ValueError('Invalid supporting observation list')
    for item in support:
        _matches(item, '[a-z0-9_-]{1,64}')
    if len(set(support)) != len(support) or not set(support) <= {r['id'] for r in document['evidence']}:
        raise ValueError('Supporting observations are duplicate or absent')
    limitations = value['limitations']
    if type(limitations) is not list or len(limitations) > len(LIMITATIONS):
        raise ValueError('Invalid limitation list')
    for item in limitations:
        _choice(item, LIMITATIONS)
    if len(set(limitations)) != len(limitations):
        raise ValueError('Duplicate limitation')
    diagnosis, reason = _diagnosis(document['evidence'])
    required = {'synthetic_only', 'no_root_cause_verified'} | ({reason} if reason else set())
    if value['diagnosis_code'] != diagnosis or required != set(limitations):
        raise ValueError('Diagnosis or limitations do not reflect available evidence')
    if diagnosis != 'insufficient_evidence':
        supported, _ = _diagnosis([row for row in document['evidence'] if row['id'] in support])
        if supported != diagnosis:
            raise ValueError('Diagnosis lacks supporting observations')
    return value


def _relative(value):
    if (type(value) is not str or not value or '\\' in value or '\x00' in value or
            any(part in {'', '.', '..'} for part in value.split('/')) or Path(value).is_absolute()):
        raise ValueError('Expected a canonical repository-relative path')
    return Path(value)


def check_change_paths(root, paths):
    """Reject protected/linked paths; success is a path check, not permission to apply."""
    root = Path(root).resolve(strict=True)
    protected = {Path(name) for name in (
        'audio', 'jarvis_voice', 'voice_layer', 'universal-voice',
        'scripts/verify_voice_lock.py', 'learning/os_contracts.py',
        'tests/test_learning/test_os_contracts.py', 'learning/os_ingestion.py',
        'tests/test_learning/test_os_ingestion.py')}
    for filename in ('audio/.voice_lock.json', 'universal-voice/.voice_lock.json'):
        manifest_path = root / filename
        if any(part.is_symlink() for part in (manifest_path, *manifest_path.parents) if part != root):
            raise ValueError('Linked protection manifest')
        manifest = _json(_read_file(manifest_path, 1024 * 1024), limit=1024 * 1024)
        if (type(manifest) is not dict or type(manifest.get('schema_version')) is not int or
                manifest['schema_version'] != 1 or manifest.get('status') != 'locked' or
                type(manifest.get('locked_files')) is not dict or not manifest['locked_files'] or
                type(manifest.get('protected_roots')) is not list or not manifest['protected_roots']):
            raise ValueError('Missing or invalid protection manifest')
        if filename.startswith('audio/'):
            protected.update(_relative(name) for name in manifest['locked_files'])
            protected.update(_relative(name) for name in manifest['protected_roots'])
    if type(paths) is not list or not paths or len(paths) > 1024:
        raise ValueError('Supply 1–1024 changed paths')
    checked = []
    for name in paths:
        path = _relative(name)
        if any(path == locked or locked in path.parents or path in locked.parents for locked in protected):
            raise ValueError('Change intersects a protected path')
        if any((root / parent).is_symlink() for parent in (path, *path.parents)):
            raise ValueError('Linked candidate path')
        target = root / path
        if target.exists():
            info = target.stat()
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise ValueError('Candidate paths must be individual, unlinked regular files')
        checked.append(name)
    return {'checked_paths': checked, 'path_check_passed': True,
            'execution_allowed': False, 'activation_allowed': False}


def phase_one_policy():
    return {'phase': 1, 'mode': 'validation_only', 'incident_producers': ['fixture'],
            'voice_inspection': 'read_only', 'voice_repairs_allowed': False,
            'candidate_execution_allowed': False, 'activation_allowed': False,
            'cloud_calls_allowed': False, 'network_access_allowed': False,
            'max_input_bytes': MAX_INPUT_BYTES,
            'later_worker_limits': {'enforced': False, 'workers': 1, 'job_seconds': 30,
                                    'case_seconds': 5, 'report_bytes': 1024 * 1024,
                                    'completed_runs': 100, 'state_bytes': 100 * 1024 * 1024}}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('policy')
    for command in ('validate-incident', 'validate-proposal'):
        child = commands.add_parser(command)
        child.add_argument('--baseline', required=True, help='Independently trusted SHA-256')
        if command == 'validate-proposal':
            child.add_argument('--incident', required=True, type=Path)
    child = commands.add_parser('check-paths')
    child.add_argument('paths', nargs='+')
    args = parser.parse_args(argv)
    try:
        if args.command == 'policy':
            result = phase_one_policy()
        elif args.command == 'check-paths':
            result = check_change_paths(Path(__file__).resolve().parents[1], args.paths)
        else:
            now = datetime.now(timezone.utc)
            raw = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
            if args.command == 'validate-incident':
                incident = parse_incident(raw, baseline_sha256=args.baseline, now=now)
                result = {'valid': True, 'incident_key': incident.key, 'incident_revision': incident.revision,
                          'evidence_sha256': incident.evidence_sha256, 'admitted_at': now.isoformat(),
                          'disposition': 'validation_only'}
            else:
                incident = parse_incident(_read_file(args.incident, MAX_INPUT_BYTES),
                                          baseline_sha256=args.baseline, now=now)
                parse_proposal(raw, incident=incident)
                result = {'valid': True, 'disposition': 'advisory_only', 'activation_allowed': False}
        print(json.dumps(result, sort_keys=True))
        return 0
    except (ValueError, OSError):
        # Never echo rejected evidence, filenames, commands or secret-bearing parser errors.
        print(json.dumps({'valid': False, 'error': 'Contract or protection check failed'}), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
