"""Read one healer occurrence without repairs, incident mutations or raw-trace export."""
import argparse
from contextlib import closing
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import sys
import time

from .bundles import private_directory
from .os_contracts import canonical, check_change_paths, digest, parse_incident, _hash, _matches


MAX_RECORDS = 100
MAX_STATE_BYTES = 100 * 1024 * 1024
MAX_SOURCE_BYTES = 256 * 1024 * 1024


def _regular(path):
    path = Path(os.path.abspath(path))
    if any(part.is_symlink() for part in (path, *path.parents)):
        raise ValueError('Linked source or state rejected')
    info = path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise ValueError('Expected an unlinked regular file')
    return info


def read_healer_incident(db, *, row_id, source_instance, baseline_sha256, now):
    """Return only typed historical metadata from a consistent read-only transaction."""
    if type(row_id) is not int or not 1 <= row_id <= 2**63 - 1:
        raise ValueError('Invalid occurrence row identity')
    _matches(source_instance, '[0-9a-f]{32}')
    _hash(baseline_sha256)
    db = Path(os.path.abspath(db))
    before = _regular(db)
    if before.st_size > MAX_SOURCE_BYTES:
        raise ValueError('Source exceeds size limit')
    for suffix in ('-wal', '-shm'):
        sidecar = Path(str(db) + suffix)
        if sidecar.exists() or sidecar.is_symlink():
            if _regular(sidecar).st_size > MAX_SOURCE_BYTES:
                raise ValueError('Source sidecar exceeds size limit')
    deadline = time.monotonic() + 2
    with closing(sqlite3.connect(db.as_uri() + '?mode=ro', uri=True, timeout=2)) as connection:
        connection.execute('PRAGMA query_only=ON')
        connection.execute('PRAGMA trusted_schema=OFF')
        connection.set_progress_handler(lambda: int(time.monotonic() > deadline), 500)
        connection.execute('BEGIN')
        schema = connection.execute(
            "SELECT substr(sql,1,8193) FROM sqlite_schema WHERE name='incidents' AND type='table'"
        ).fetchone()
        if not schema or not schema[0] or len(schema[0]) > 8192 or not re.match(
                r'CREATE\s+TABLE\b', schema[0], re.IGNORECASE):
            raise ValueError('Unsupported incident table')
        columns = {row[1]: row for row in connection.execute('PRAGMA table_info(incidents)')}
        if (not {'id', 'domain', 'created_at'} <= columns.keys() or
                columns['id'][2].upper() != 'INTEGER' or columns['id'][5] != 1 or
                any(columns[name][2].upper() != 'TEXT' for name in ('domain', 'created_at'))):
            raise ValueError('Unsupported incident column schema')
        row = connection.execute(
            'SELECT id, substr(domain,1,65), substr(created_at,1,65) FROM incidents WHERE id=?',
            (row_id,)).fetchone()
        if row is None:
            raise ValueError('Occurrence not found')
        if type(row[0]) is not int or row[0] != row_id or row[1] != 'systemd_service':
            raise ValueError('Unsupported incident domain or identity')
        created = row[2]
        _matches(created, r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|\+00:00)')
        observed = datetime.fromisoformat(created.replace('Z', '+00:00')).isoformat().replace('+00:00', 'Z')
        incident = parse_incident(canonical({
            'schema_version': 1, 'producer': 'healer-metadata',
            'source_incident_id': digest({'source_instance': source_instance, 'row_id': row_id}),
            'observed_at': observed, 'component': 'unidentified-user-service',
            'kind': 'failed_user_service', 'state': 'unknown',
            'baseline_sha256': baseline_sha256, 'evidence': [],
        }), baseline_sha256=baseline_sha256, now=now, allow_healer_metadata=True)
        connection.rollback()
    after = _regular(db)
    if (before.st_dev, before.st_ino) != (after.st_dev, after.st_ino):
        raise ValueError('Source replaced during read')
    return {'incident': incident,
            'source_binding': digest({'path': str(db), 'device': before.st_dev, 'inode': before.st_ino}),
            'occurrence_sha256': digest({'row_id': row_id, 'domain': row[1], 'created_at': created})}


def _state_directory(state_dir, db):
    state_dir = Path(os.path.abspath(state_dir))
    if Path(os.path.abspath(db)).is_relative_to(state_dir):
        raise ValueError('Source database must be outside ingestion state')
    project = Path(__file__).resolve().parents[1]
    if state_dir.is_relative_to(project):
        relative = state_dir.relative_to(project)
        check_change_paths(project, [str(relative / 'incidents.sqlite3'), str(relative / 'ingestion.lock')])
    if state_dir.exists():
        allowed = {'ingestion.lock', 'incidents.sqlite3', 'incidents.sqlite3-journal'}
        entries = list(state_dir.iterdir())
        if any(entry.name not in allowed for entry in entries):
            raise ValueError('Use a dedicated ingestion state directory')
        if sum(_regular(entry).st_size for entry in entries) >= MAX_STATE_BYTES:
            raise ValueError('Ingestion state quota reached')
    return private_directory(state_dir)


def ingest_healer_incident(db, *, state_dir, row_id, source_instance, baseline_sha256, now):
    """Deduplicate one occurrence/revision atomically in separate private local state."""
    # Validate source first, so a missing/invalid input never initializes a store.
    record = read_healer_incident(db, row_id=row_id, source_instance=source_instance,
                                 baseline_sha256=baseline_sha256, now=now)
    root = _state_directory(state_dir, db)
    descriptor = os.open(root / 'ingestion.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, 'w') as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError('Another ingestion owns this state directory') from None
        database = root / 'incidents.sqlite3'
        descriptor = os.open(database, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        os.close(descriptor)
        for path in (database, root / 'ingestion.lock'):
            info = _regular(path)
            if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600:
                raise ValueError('Ingestion state must be privately owned')
        with closing(sqlite3.connect(database, timeout=2)) as connection:
            connection.execute('PRAGMA trusted_schema=OFF')
            page_size = connection.execute('PRAGMA page_size').fetchone()[0]
            connection.execute('PRAGMA max_page_count=' + str(MAX_STATE_BYTES // page_size))
            connection.execute('BEGIN IMMEDIATE')
            connection.execute('CREATE TABLE IF NOT EXISTS sources ('
                               'instance TEXT PRIMARY KEY, binding TEXT NOT NULL)')
            connection.execute('CREATE TABLE IF NOT EXISTS incidents ('
                               'instance TEXT NOT NULL, row_id INTEGER NOT NULL, '
                               'occurrence_sha256 TEXT NOT NULL, baseline TEXT NOT NULL, '
                               'revision TEXT NOT NULL, incident_json TEXT NOT NULL, '
                               'PRIMARY KEY(instance,row_id,baseline))')
            source = connection.execute('SELECT binding FROM sources WHERE instance=?',
                                        (source_instance,)).fetchone()
            if source and source[0] != record['source_binding']:
                raise ValueError('Source instance binding changed; inspect before reusing identity')
            prior = connection.execute(
                'SELECT occurrence_sha256,baseline,revision,incident_json FROM incidents '
                'WHERE instance=? AND row_id=?', (source_instance, row_id)).fetchall()
            if any(row[0] != record['occurrence_sha256'] for row in prior):
                raise ValueError('Occurrence identity reused with changed metadata')
            incident = record['incident']
            encoded = incident._canonical.decode('utf-8')
            existing = next((row for row in prior if row[1] == baseline_sha256), None)
            if existing and (existing[2] != incident.revision or existing[3] != encoded):
                raise ValueError('Persisted incident differs from source snapshot')
            if not existing:
                if connection.execute('SELECT count(*) FROM incidents').fetchone()[0] >= MAX_RECORDS:
                    raise ValueError('Incident record quota reached')
                connection.execute('INSERT OR IGNORE INTO sources VALUES (?,?)',
                                   (source_instance, record['source_binding']))
                connection.execute('INSERT INTO incidents VALUES (?,?,?,?,?,?)',
                                   (source_instance, row_id, record['occurrence_sha256'],
                                    baseline_sha256, incident.revision, encoded))
            connection.commit()
    return {'status': 'duplicate' if existing else 'ingested', 'source_instance': source_instance,
            'source_row_id': row_id, 'incident_key': incident.key, 'incident_revision': incident.revision,
            'incident': incident.document(), 'disposition': 'ingestion_only',
            'limitations': ['historical_metadata_only', 'service_identity_unverified', 'evidence_missing'],
            'execution_allowed': False, 'activation_allowed': False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', required=True, type=Path)
    parser.add_argument('--state-dir', required=True, type=Path)
    parser.add_argument('--row-id', required=True, type=int)
    parser.add_argument('--source-instance', required=True, help='Stable operator-assigned 32-character hex ID')
    parser.add_argument('--baseline', required=True, help='Independently trusted SHA-256')
    args = parser.parse_args(argv)
    try:
        result = ingest_healer_incident(args.db, state_dir=args.state_dir, row_id=args.row_id,
                                       source_instance=args.source_instance, baseline_sha256=args.baseline,
                                       now=datetime.now(timezone.utc))
        print(json.dumps(result, sort_keys=True))
        return 0
    except (ValueError, OSError, sqlite3.Error):
        print(json.dumps({'status': 'rejected', 'error': 'Incident ingestion failed; inspect source and state'}),
              file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
