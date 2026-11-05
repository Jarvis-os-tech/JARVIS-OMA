from datetime import datetime, timedelta, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest

from learning.os_contracts import canonical, parse_incident, parse_proposal
from learning.os_ingestion import ingest_healer_incident, read_healer_incident


NOW = datetime(2026, 11, 5, 1, tzinfo=timezone.utc)
BASELINE = 'a' * 64
INSTANCE = 'b' * 32
SECRET = 'synthetic-private-log-and-prompt'


def create_source(path, *, observed=NOW, domain='systemd_service', wal=False):
    connection = sqlite3.connect(path)
    if wal:
        connection.execute('PRAGMA journal_mode=WAL')
    connection.execute('CREATE TABLE incidents (id INTEGER PRIMARY KEY, incident_id TEXT, '
                       'domain TEXT, created_at TEXT, trace_json TEXT, title TEXT)')
    for row_id in (1, 2):
        connection.execute('INSERT INTO incidents VALUES (?,?,?,?,?,?)',
                           (row_id, 'inc-repeated-fingerprint', domain, observed.isoformat(), SECRET, SECRET))
    connection.commit()
    return connection


@pytest.fixture
def source(tmp_path):
    path = tmp_path / 'source.sqlite3'
    connection = create_source(path)
    connection.close()
    return path


def ingest(source, tmp_path, **changes):
    arguments = dict(state_dir=tmp_path / 'private-state', row_id=1, source_instance=INSTANCE,
                     baseline_sha256=BASELINE, now=NOW)
    arguments.update(changes)
    return ingest_healer_incident(source, **arguments)


def test_occurrences_are_distinct_duplicates_survive_restart_and_source_is_unchanged(source, tmp_path):
    before = source.read_bytes()
    first = ingest(source, tmp_path)
    duplicate = ingest(source, tmp_path)
    second = ingest(source, tmp_path, row_id=2)
    assert first['status'] == second['status'] == 'ingested'
    assert duplicate['status'] == 'duplicate'
    assert first['incident_revision'] == duplicate['incident_revision']
    assert first['incident_key'] != second['incident_key']
    assert source.read_bytes() == before
    assert not Path(str(source) + '-journal').exists()
    assert SECRET not in json.dumps(first)
    assert first['incident']['state'] == 'unknown'
    assert first['incident']['component'] == 'unidentified-user-service'
    assert first['incident']['evidence'] == []
    assert first['disposition'] == 'ingestion_only'
    assert not first['execution_allowed'] and not first['activation_allowed']
    state = tmp_path / 'private-state'
    assert state.stat().st_mode & 0o777 == 0o700
    assert (state / 'incidents.sqlite3').stat().st_mode & 0o777 == 0o600
    assert SECRET.encode() not in (state / 'incidents.sqlite3').read_bytes()
    with sqlite3.connect(state / 'incidents.sqlite3') as connection:
        assert connection.execute('SELECT count(*) FROM incidents').fetchone()[0] == 2


def test_new_baseline_creates_new_revision_without_overwriting(source, tmp_path):
    first = ingest(source, tmp_path)
    second = ingest(source, tmp_path, baseline_sha256='c' * 64)
    assert first['incident_key'] == second['incident_key']
    assert first['incident_revision'] != second['incident_revision']
    assert ingest(source, tmp_path)['status'] == 'duplicate'


@pytest.mark.parametrize('changes', [
    {'row_id': True}, {'row_id': 0}, {'row_id': 999}, {'row_id': 2**63},
    {'source_instance': 'private-name'}, {'source_instance': 'C' * 32},
    {'baseline_sha256': 'not-a-hash'}, {'now': NOW + timedelta(days=2)},
    {'now': NOW - timedelta(hours=1)}, {'now': NOW.replace(tzinfo=None)},
])
def test_invalid_admission_never_initializes_state(source, tmp_path, changes):
    with pytest.raises(ValueError):
        ingest(source, tmp_path, **changes)
    assert not (tmp_path / 'private-state').exists()


def test_missing_linked_and_non_database_sources_fail_without_creation(tmp_path):
    missing = tmp_path / 'missing.sqlite3'
    with pytest.raises(FileNotFoundError):
        ingest(missing, tmp_path)
    assert not missing.exists()
    missing.write_text(SECRET)
    with pytest.raises(sqlite3.DatabaseError):
        ingest(missing, tmp_path)
    link = tmp_path / 'linked.sqlite3'
    link.symlink_to(missing)
    with pytest.raises(ValueError, match='Linked'):
        ingest(link, tmp_path)
    assert not (tmp_path / 'private-state').exists()


@pytest.mark.parametrize('domain', ['ui_shell', 'systemd_service' + 'x' * 100, SECRET])
def test_unsupported_domains_are_not_guessed(tmp_path, domain):
    path = tmp_path / 'source.sqlite3'
    create_source(path, domain=domain).close()
    with pytest.raises(ValueError, match='domain'):
        ingest(path, tmp_path)


def test_views_and_malformed_timestamps_are_rejected(source, tmp_path):
    with sqlite3.connect(source) as connection:
        connection.execute('UPDATE incidents SET created_at=? WHERE id=1', (SECRET,))
    with pytest.raises(ValueError):
        ingest(source, tmp_path)
    view = tmp_path / 'view.sqlite3'
    with sqlite3.connect(view) as connection:
        connection.execute('CREATE VIEW incidents AS SELECT 1 AS id')
    with pytest.raises(ValueError, match='table'):
        ingest(view, tmp_path)


def test_nonunique_occurrence_columns_are_rejected(tmp_path):
    source = tmp_path / 'bad-schema.sqlite3'
    with sqlite3.connect(source) as connection:
        connection.execute('CREATE TABLE incidents (id INTEGER, domain TEXT, created_at TEXT)')
    with pytest.raises(ValueError, match='schema'):
        ingest(source, tmp_path)


def test_corrupt_local_record_is_not_reported_as_duplicate(source, tmp_path):
    ingest(source, tmp_path)
    with sqlite3.connect(tmp_path / 'private-state/incidents.sqlite3') as connection:
        connection.execute("UPDATE incidents SET incident_json='{}'")
    with pytest.raises(ValueError, match='Persisted'):
        ingest(source, tmp_path)


def test_state_size_quota_is_checked_before_more_records(source, tmp_path, monkeypatch):
    ingest(source, tmp_path)
    monkeypatch.setattr('learning.os_ingestion.MAX_STATE_BYTES', 1)
    with pytest.raises(ValueError, match='quota'):
        ingest(source, tmp_path, row_id=2)


def test_changed_occurrence_metadata_and_replaced_database_are_not_replayed(source, tmp_path):
    ingest(source, tmp_path)
    with sqlite3.connect(source) as connection:
        connection.execute('UPDATE incidents SET created_at=? WHERE id=1',
                           ((NOW + timedelta(seconds=1)).isoformat(),))
    with pytest.raises(ValueError, match='reused'):
        ingest(source, tmp_path)
    replacement = tmp_path / 'replacement.sqlite3'
    create_source(replacement).close()
    os.replace(replacement, source)
    with pytest.raises(ValueError, match='binding'):
        ingest(source, tmp_path)
    assert ingest(source, tmp_path, source_instance='d' * 32)['status'] == 'ingested'


def test_concurrent_wal_writer_does_not_change_the_read_snapshot(tmp_path, monkeypatch):
    source = tmp_path / 'source.sqlite3'
    writer = create_source(source, wal=True)
    original_connect = sqlite3.connect
    reads = []

    class SnapshotConnection(sqlite3.Connection):
        def execute(self, sql, parameters=()):
            reads.append(sql)
            if sql.startswith('SELECT id,'):
                writer.execute('UPDATE incidents SET created_at=? WHERE id=1',
                               ((NOW + timedelta(seconds=1)).isoformat(),))
                writer.commit()
            return super().execute(sql, parameters)

    def connect(path, **kwargs):
        assert 'mode=ro' in path and 'immutable' not in path
        connection = original_connect(path, factory=SnapshotConnection, **kwargs)
        connection.set_authorizer(lambda action, *args: sqlite3.SQLITE_DENY if action in {
            sqlite3.SQLITE_INSERT, sqlite3.SQLITE_UPDATE, sqlite3.SQLITE_DELETE,
            sqlite3.SQLITE_CREATE_TABLE, sqlite3.SQLITE_DROP_TABLE, sqlite3.SQLITE_ATTACH,
        } else sqlite3.SQLITE_OK)
        return connection

    monkeypatch.setattr(sqlite3, 'connect', connect)
    try:
        result = read_healer_incident(source, row_id=1, source_instance=INSTANCE,
                                      baseline_sha256=BASELINE, now=NOW)
        assert result['incident'].document()['observed_at'] == NOW.isoformat().replace('+00:00', 'Z')
        assert writer.execute('SELECT created_at FROM incidents WHERE id=1').fetchone()[0] != NOW.isoformat()
        assert not any(SECRET in sql or 'trace_json' in sql or 'title' in sql for sql in reads)
    finally:
        writer.close()


def test_single_owner_rollback_and_capacity(source, tmp_path, monkeypatch):
    first = ingest(source, tmp_path)
    state = tmp_path / 'private-state'
    with (state / 'ingestion.lock').open('r+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(ValueError, match='owns'):
            ingest(source, tmp_path, row_id=2)
    with sqlite3.connect(state / 'incidents.sqlite3') as connection:
        connection.execute("CREATE TRIGGER reject_insert BEFORE INSERT ON incidents BEGIN "
                           "SELECT RAISE(ABORT,'synthetic interruption'); END")
    with pytest.raises(sqlite3.DatabaseError):
        ingest(source, tmp_path, row_id=2, source_instance='e' * 32)
    with sqlite3.connect(state / 'incidents.sqlite3') as connection:
        assert connection.execute('SELECT count(*) FROM incidents').fetchone()[0] == 1
        assert connection.execute('SELECT count(*) FROM sources').fetchone()[0] == 1
        connection.execute('DROP TRIGGER reject_insert')
    monkeypatch.setattr('learning.os_ingestion.MAX_RECORDS', 1)
    assert ingest(source, tmp_path)['incident_revision'] == first['incident_revision']
    with pytest.raises(ValueError, match='quota'):
        ingest(source, tmp_path, row_id=2)


def test_state_cannot_target_source_directory_or_link(source, tmp_path):
    with pytest.raises(ValueError, match='outside'):
        ingest(source, tmp_path, state_dir=tmp_path)
    outside = tmp_path / 'outside'
    outside.mkdir()
    linked = tmp_path / 'state-link'
    linked.symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match='symlink'):
        ingest(source, tmp_path, state_dir=linked)
    assert list(outside.iterdir()) == []


def test_real_metadata_profile_cannot_supply_observations_or_be_evaluated(source, tmp_path):
    data = ingest(source, tmp_path)['incident']
    with pytest.raises(ValueError):
        parse_incident(canonical(data), baseline_sha256=BASELINE, now=NOW)
    incident = parse_incident(canonical(data), baseline_sha256=BASELINE, now=NOW, allow_healer_metadata=True)
    with pytest.raises(ValueError, match='not implemented'):
        parse_proposal(b'{}', incident=incident)
    for changes in [{'state': 'failed'}, {'component': 'fixture-user-service'},
                    {'evidence': [{'id': 'active', 'name': 'active_state', 'value': 'failed',
                                   'observed_at': data['observed_at']}]}]:
        with pytest.raises(ValueError):
            parse_incident(canonical({**data, **changes}), baseline_sha256=BASELINE, now=NOW,
                           allow_healer_metadata=True)


def test_cli_is_read_only_and_rejections_do_not_echo_private_content(tmp_path):
    source = tmp_path / 'source.sqlite3'
    create_source(source, observed=datetime.now(timezone.utc)).close()
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    command = [sys.executable, '-m', 'learning.os_ingestion', '--db', str(source),
               '--state-dir', str(tmp_path / 'state'), '--source-instance', INSTANCE,
               '--baseline', BASELINE, '--row-id']
    first = subprocess.run(command + ['1'], capture_output=True, text=True, timeout=5)
    assert first.returncode == 0, first.stderr
    assert json.loads(first.stdout)['status'] == 'ingested'
    second = subprocess.run(command + ['1'], capture_output=True, text=True, timeout=5)
    assert json.loads(second.stdout)['status'] == 'duplicate'
    failed = subprocess.run(command + ['999'], capture_output=True, text=True, timeout=5)
    assert failed.returncode == 1
    assert SECRET not in first.stdout + second.stdout + failed.stdout + failed.stderr
    assert hashlib.sha256(source.read_bytes()).hexdigest() == before
