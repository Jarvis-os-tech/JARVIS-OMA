import json
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
