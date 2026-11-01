import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from orchestration.release_manager import ReleaseManager, DEFAULT_REPO_URL

def test_check_remote_update_no_update(tmp_path):
    rm = ReleaseManager(root_dir=tmp_path)
    current = tmp_path / "current"
    current.mkdir(parents=True)
    (current / "release.json").write_text(json.dumps({
        "commit": "abc1234",
        "branch": "JARVIS-OS"
    }))
    with patch.object(rm, "_query_remote_sha", return_value="abc1234"):
        res = rm.check_remote_update()
        assert res["has_update"] is False
        assert res["current_sha"] == "abc1234"
        assert res["remote_sha"] == "abc1234"

def test_check_remote_update_update_available(tmp_path):
    rm = ReleaseManager(root_dir=tmp_path)
    current = tmp_path / "current"
    current.mkdir(parents=True)
    (current / "release.json").write_text(json.dumps({
        "commit": "abc1234",
        "branch": "JARVIS-OS"
    }))
    with patch.object(rm, "_query_remote_sha", return_value="def5678"):
        with patch.object(rm, "_query_remote_commit_message", return_value="feat: new update"):
            res = rm.check_remote_update()
            assert res["has_update"] is True
            assert res["current_sha"] == "abc1234"
            assert res["remote_sha"] == "def5678"
            assert "feat: new update" in res["message"]

def test_prune_releases(tmp_path):
    rm = ReleaseManager(root_dir=tmp_path)
    releases_dir = tmp_path / "releases"
    releases_dir.mkdir(parents=True)
    # create 5 mock release dirs with timestamps
    for i in range(5):
        d = releases_dir / f"rel_0{i}"
        d.mkdir()
        (d / "release.json").write_text(json.dumps({
            "commit": f"sha_{i}",
            "created_at": 1000 + i
        }))
    pruned = rm.prune_releases(keep=3)
    assert len(pruned) == 2
    remaining = sorted([p.name for p in releases_dir.iterdir() if p.is_dir()])
    assert remaining == ["rel_02", "rel_03", "rel_04"]

def test_list_releases_tagging(tmp_path):
    rm = ReleaseManager(root_dir=tmp_path)
    releases_dir = tmp_path / "releases"
    releases_dir.mkdir(parents=True)
    r1 = releases_dir / "rel_1"
    r1.mkdir()
    (r1 / "release.json").write_text(json.dumps({"commit": "sha1", "created_at": 100}))
    r2 = releases_dir / "rel_2"
    r2.mkdir()
    (r2 / "release.json").write_text(json.dumps({"commit": "sha2", "created_at": 200}))

    # Symlinks
    (tmp_path / "current").symlink_to(r2)
    (tmp_path / "previous").symlink_to(r1)

    items = rm.list_releases()
    assert len(items) == 2
    assert items[0]["name"] == "rel_2"
    assert items[0]["is_current"] is True
    assert items[1]["name"] == "rel_1"
    assert items[1]["is_previous"] is True
