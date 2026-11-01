import json
import subprocess
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from orchestration.release_manager import ReleaseManager

def test_atomic_activation_and_previous_link(tmp_path):
    rm = ReleaseManager(root_dir=tmp_path)
    releases = tmp_path / "releases"
    releases.mkdir(parents=True)
    r1 = releases / "rel_1"
    r1.mkdir()
    (r1 / "release.json").write_text(json.dumps({"commit": "sha1"}))
    r2 = releases / "rel_2"
    r2.mkdir()
    (r2 / "release.json").write_text(json.dumps({"commit": "sha2"}))

    # Activate r1
    with patch.object(rm, "verify_health", return_value=True), patch.object(rm, "_restart_services"):
        meta = rm.activate_release(r1)
        assert meta["commit"] == "sha1"
        assert (tmp_path / "current").resolve() == r1.resolve()
        assert not (tmp_path / "previous").exists()

    # Activate r2
    with patch.object(rm, "verify_health", return_value=True), patch.object(rm, "_restart_services"):
        meta = rm.activate_release(r2)
        assert meta["commit"] == "sha2"
        assert (tmp_path / "current").resolve() == r2.resolve()
        assert (tmp_path / "previous").resolve() == r1.resolve()

def test_auto_rollback_on_health_failure(tmp_path):
    rm = ReleaseManager(root_dir=tmp_path)
    releases = tmp_path / "releases"
    releases.mkdir(parents=True)
    r1 = releases / "rel_1"
    r1.mkdir()
    (r1 / "release.json").write_text(json.dumps({"commit": "sha1"}))
    r2 = releases / "rel_2"
    r2.mkdir()
    (r2 / "release.json").write_text(json.dumps({"commit": "sha2"}))

    # Activate initial release r1
    with patch.object(rm, "verify_health", return_value=True), patch.object(rm, "_restart_services"):
        rm.activate_release(r1)
        assert (tmp_path / "current").resolve() == r1.resolve()

    # Attempt to activate r2, but health check fails!
    with patch.object(rm, "verify_health", side_effect=[False, True]), patch.object(rm, "_restart_services"):
        with pytest.raises(RuntimeError, match="Health probe failed.*rolled back"):
            rm.activate_release(r2)
        # Verify it automatically restored r1
        assert (tmp_path / "current").resolve() == r1.resolve()

def test_manual_rollback(tmp_path):
    rm = ReleaseManager(root_dir=tmp_path)
    releases = tmp_path / "releases"
    releases.mkdir(parents=True)
    r1 = releases / "rel_1"
    r1.mkdir()
    (r1 / "release.json").write_text(json.dumps({"commit": "sha1"}))
    r2 = releases / "rel_2"
    r2.mkdir()
    (r2 / "release.json").write_text(json.dumps({"commit": "sha2"}))

    with patch.object(rm, "verify_health", return_value=True), patch.object(rm, "_restart_services"):
        rm.activate_release(r1)
        rm.activate_release(r2)
        assert (tmp_path / "current").resolve() == r2.resolve()
        assert (tmp_path / "previous").resolve() == r1.resolve()

        # Rollback
        meta = rm.rollback()
        assert meta["commit"] == "sha1"
        assert (tmp_path / "current").resolve() == r1.resolve()
        assert (tmp_path / "previous").resolve() == r2.resolve()

def test_state_snapshot(tmp_path):
    rm = ReleaseManager(root_dir=tmp_path)
    data = tmp_path / "data"
    data.mkdir(parents=True)
    db1 = data / "sessions.db"
    db1.write_text("dummy database content")

    snapshots = rm.snapshot_state()
    assert len(snapshots) == 1
    assert snapshots[0].exists()
    assert "sessions.db.bak." in snapshots[0].name
    assert snapshots[0].read_text() == "dummy database content"

@pytest.fixture
def release_history(tmp_path):
    rm = ReleaseManager(tmp_path)
    rm.init_directories()
    releases = []
    for name in ('older', 'working', 'candidate'):
        release = rm.releases_dir / name
        release.mkdir()
        (release / 'release.json').write_text(json.dumps({'commit': name}))
        releases.append(release)
    rm.current_link.symlink_to(releases[1])
    rm.previous_link.symlink_to(releases[0])
    return rm, releases


@pytest.mark.parametrize('failure', [
    subprocess.TimeoutExpired('systemctl', 30),
    subprocess.CalledProcessError(1, 'systemctl'),
])
def test_restart_failure_restores_both_pointers(release_history, failure):
    rm, (older, working, candidate) = release_history
    with patch.object(rm, '_restart_services', side_effect=[failure, None]), \
         patch.object(rm, 'verify_health', return_value=True):
        with pytest.raises(RuntimeError, match='automatically rolled back'):
            rm.activate_release(candidate)
    assert rm.current_link.resolve() == working
    assert rm.previous_link.resolve() == older


def test_health_failure_preserves_older_rollback_target(release_history):
    rm, (older, working, candidate) = release_history
    with patch.object(rm, '_restart_services'), \
         patch.object(rm, 'verify_health', side_effect=[False, True]):
        with pytest.raises(RuntimeError, match='automatically rolled back'):
            rm.activate_release(candidate)
    assert rm.current_link.resolve() == working
    assert rm.previous_link.resolve() == older


def test_failed_manual_rollback_restores_working_release(release_history):
    rm, (older, working, _) = release_history
    with patch.object(rm, '_restart_services'), \
         patch.object(rm, 'verify_health', side_effect=[False, True]):
        with pytest.raises(RuntimeError, match='automatically rolled back'):
            rm.rollback()
    assert rm.current_link.resolve() == working
    assert rm.previous_link.resolve() == older


def test_recovery_failure_is_reported(release_history):
    rm, (_, working, candidate) = release_history
    with patch.object(rm, '_restart_services'), \
         patch.object(rm, 'verify_health', side_effect=[False, False]):
        with pytest.raises(RuntimeError, match='recovery failed'):
            rm.activate_release(candidate)
    assert rm.current_link.resolve() == working


def test_first_activation_failure_removes_current(tmp_path):
    rm = ReleaseManager(tmp_path)
    candidate = tmp_path / 'candidate'
    candidate.mkdir()
    (candidate / 'release.json').write_text('{}')
    with patch.object(rm, '_restart_services'), patch.object(rm, 'verify_health', return_value=False):
        with pytest.raises(RuntimeError, match='no previous active release'):
            rm.activate_release(candidate)
    assert not rm.current_link.is_symlink()


@pytest.mark.parametrize('states', ['active\nfailed\n', 'activating\nactive\n', 'active\n'])
def test_health_rejects_unhealthy_services(tmp_path, states):
    import subprocess
    rm = ReleaseManager(tmp_path)
    with patch('orchestration.release_manager.subprocess.run',
               return_value=subprocess.CompletedProcess([], 0, states)), \
         patch('orchestration.release_manager.time.sleep'), \
         patch('orchestration.release_manager.time.monotonic', side_effect=[0, 0, 0, 0.1, 2]):
        assert not rm.verify_health(timeout=1)


def test_health_requires_sustained_activity(tmp_path):
    import subprocess
    rm = ReleaseManager(tmp_path)
    with patch('orchestration.release_manager.subprocess.run',
               return_value=subprocess.CompletedProcess([], 0, 'active\nactive\n')) as run, \
         patch('orchestration.release_manager.time.sleep'), \
         patch('orchestration.release_manager.time.monotonic', side_effect=[0, 0, 0, 0, 0.5, 0.5, 1.1]):
        assert rm.verify_health(timeout=2)
    assert run.call_count == 2
    assert 'jarvis-device-bridge.service' in run.call_args.args[0]
