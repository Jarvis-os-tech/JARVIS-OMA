import json
import subprocess
import sys

from learning.bundles import BundleRegistry
from learning.doctor import doctor
from learning.research import seed_bundle


def initialize(root):
    registry = BundleRegistry(root)
    bundle = registry.register(seed_bundle())
    registry.activate(bundle.digest)


def test_doctor_ready_without_opening_audio_or_models(tmp_path):
    initialize(tmp_path)
    report = doctor(tmp_path)
    assert report['ready'], report
    assert {row['name'] for row in report['checks']} == {
        'python', 'upstream', 'state', 'databases', 'voice_tools', 'voice_lock'}
    assert not (tmp_path / 'episodes.sqlite3').exists()


def test_doctor_missing_state_is_not_created(tmp_path):
    missing = tmp_path / 'missing'
    report = doctor(missing)
    assert not report['ready']
    assert not missing.exists()


def test_doctor_catches_corrupt_database_and_bad_pin(tmp_path, monkeypatch):
    initialize(tmp_path)
    (tmp_path / 'episodes.sqlite3').write_bytes(b'not a sqlite database')
    (tmp_path / 'episodes.sqlite3').chmod(0o600)
    monkeypatch.setattr('learning.doctor.require_upstream', lambda: (_ for _ in ()).throw(ValueError('mismatch')))
    report = doctor(tmp_path)
    assert not report['ready']
    failures = {row['name'] for row in report['checks'] if row['status'] == 'fail'}
    assert {'upstream', 'databases'} <= failures


def test_doctor_cli_exits_nonzero_when_not_ready(tmp_path):
    process = subprocess.run([sys.executable, '-m', 'learning', '--state-dir', str(tmp_path / 'missing'),
                              'doctor'], capture_output=True, text=True, timeout=15)
    assert process.returncode == 1
    assert json.loads(process.stdout)['ready'] is False
