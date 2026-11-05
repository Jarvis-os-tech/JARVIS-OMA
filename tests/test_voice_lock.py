import hashlib
import json
from pathlib import Path

import pytest

from scripts.verify_voice_lock import verify


def fixture(root):
    (root / 'audio').mkdir()
    (root / 'voice_layer').mkdir()
    target = root / 'voice_layer/speech.py'
    target.write_text('baseline\n')
    manifest = {'schema_version': 1, 'protected_roots': ['voice_layer'], 'locked_files': {
        'voice_layer/speech.py': {'sha256': hashlib.sha256(target.read_bytes()).hexdigest()}}}
    (root / 'audio/.voice_lock.json').write_text(json.dumps(manifest))
    return target


def test_current_voice_baseline_is_intact():
    assert verify(Path(__file__).resolve().parents[1]) == []


def test_voice_lock_detects_changed_missing_and_added_code(tmp_path):
    target = fixture(tmp_path)
    assert verify(tmp_path) == []
    target.write_text('changed\n')
    assert 'Changed: voice_layer/speech.py' in verify(tmp_path)
    target.unlink()
    assert 'Missing: voice_layer/speech.py' in verify(tmp_path)
    (target.parent / 'replacement.py').write_text('replacement\n')
    assert 'Added: voice_layer/replacement.py' in verify(tmp_path)


def test_voice_lock_rejects_symlink_replacement(tmp_path):
    target = fixture(tmp_path)
    elsewhere = tmp_path / 'elsewhere.py'
    elsewhere.write_text('baseline\n')
    target.unlink()
    target.symlink_to(elsewhere)
    assert 'Linked: voice_layer/speech.py' in verify(tmp_path)


def test_voice_lock_rejects_paths_outside_workspace(tmp_path):
    fixture(tmp_path)
    manifest = tmp_path / 'audio/.voice_lock.json'
    data = json.loads(manifest.read_text())
    data['locked_files']['../outside.py'] = {'sha256': 'unused'}
    manifest.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='Invalid locked path'):
        verify(tmp_path)


def test_voice_lock_preserves_only_the_pinned_internal_link(tmp_path):
    fixture(tmp_path)
    link = tmp_path / 'voice_layer/assets'
    link.symlink_to('../audio', target_is_directory=True)
    manifest = tmp_path / 'audio/.voice_lock.json'
    data = json.loads(manifest.read_text())
    data['locked_files']['voice_layer/assets'] = {'link_target': '../audio'}
    manifest.write_text(json.dumps(data))
    assert verify(tmp_path) == []
    link.unlink()
    link.symlink_to('../elsewhere', target_is_directory=True)
    assert 'Changed link: voice_layer/assets' in verify(tmp_path)
