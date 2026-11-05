from pathlib import Path

import pytest

import filesystem.filesystem as files


@pytest.mark.parametrize('operation', ['delete', 'trash'])
def test_critical_path_aliases_are_rejected(tmp_path, monkeypatch, operation):
    protected = tmp_path / 'protected'
    protected.mkdir()
    (protected / 'child').mkdir()
    (protected / 'keep.txt').write_text('keep')
    monkeypatch.setattr(files, 'CRITICAL_PATHS', files.CRITICAL_PATHS | {protected})
    alias = tmp_path / 'parent-alias'
    alias.symlink_to(tmp_path, target_is_directory=True)
    escaped = str(alias / 'protected' / 'child' / '..')

    with pytest.raises(files.FileOperationError):
        getattr(files, f'{operation}_path')(escaped)
    assert (protected / 'keep.txt').read_text() == 'keep'


@pytest.mark.parametrize('operation', ['copy', 'move'])
def test_critical_destination_alias_is_rejected(tmp_path, monkeypatch, operation):
    protected = tmp_path / 'protected'
    protected.mkdir()
    (protected / 'child').mkdir()
    source = tmp_path / 'source.txt'
    source.write_text('keep')
    monkeypatch.setattr(files, 'CRITICAL_PATHS', files.CRITICAL_PATHS | {protected})
    destination = str(protected / 'child' / '..')

    with pytest.raises(files.FileOperationError, match='cannot overwrite'):
        getattr(files, f'{operation}_path')(str(source), destination, overwrite=True)
    assert source.read_text() == 'keep'


@pytest.mark.parametrize('operation', ['copy', 'move'])
def test_ancestor_destination_cannot_remove_source(tmp_path, operation):
    parent = tmp_path / 'parent'
    parent.mkdir()
    source = parent / 'source.txt'
    source.write_text('keep')

    with pytest.raises(files.FileOperationError, match='inside itself'):
        getattr(files, f'{operation}_path')(str(source), str(parent), overwrite=True)
    assert source.read_text() == 'keep'


@pytest.mark.parametrize('operation', ['copy', 'move'])
def test_ancestor_alias_destination_cannot_remove_source(tmp_path, operation):
    real = tmp_path / 'real'
    parent = real / 'parent'
    parent.mkdir(parents=True)
    source = parent / 'child.txt'
    source.write_text('keep')
    alias = tmp_path / 'alias'
    alias.symlink_to(real, target_is_directory=True)

    with pytest.raises(files.FileOperationError, match='inside itself'):
        getattr(files, f'{operation}_path')(str(source), str(alias / 'parent'), overwrite=True)
    assert source.read_text() == 'keep'


def test_move_rejects_protected_source_alias(tmp_path, monkeypatch):
    protected = tmp_path / 'protected'
    (protected / 'child').mkdir(parents=True)
    alias = tmp_path / 'alias'
    alias.symlink_to(tmp_path, target_is_directory=True)
    monkeypatch.setattr(files, 'CRITICAL_PATHS', files.CRITICAL_PATHS | {protected})

    with pytest.raises(files.FileOperationError, match='cannot move system root or home'):
        files.move_path(str(alias / 'protected' / 'child' / '..'), str(tmp_path / 'destination'))
    assert protected.is_dir()


def test_delete_symlink_keeps_its_target(tmp_path):
    target = tmp_path / 'target.txt'
    target.write_text('keep')
    link = tmp_path / 'link.txt'
    link.symlink_to(target)

    assert files.delete_path(str(link))['status'] == 'deleted'
    assert not link.is_symlink()
    assert target.read_text() == 'keep'


def test_copy_overwrite_failure_keeps_destination(tmp_path, monkeypatch):
    source = tmp_path / 'source.txt'
    destination = tmp_path / 'destination.txt'
    source.write_text('new')
    destination.write_text('old')

    def fail_copy(src, dst, *args, **kwargs):
        Path(dst).write_text('partial')
        raise OSError('simulated copy failure')

    monkeypatch.setattr(files.shutil, 'copy2', fail_copy)
    with pytest.raises(files.FileOperationError, match='cannot copy path'):
        files.copy_path(str(source), str(destination), overwrite=True)
    assert destination.read_text() == 'old'
    assert not list(tmp_path.glob('*.stage'))


def test_move_overwrite_failure_restores_destination_and_source(tmp_path, monkeypatch):
    source = tmp_path / 'source.txt'
    destination = tmp_path / 'destination.txt'
    source.write_text('new')
    destination.write_text('old')

    def fail_replace(stage, target):
        raise OSError('simulated install failure')

    monkeypatch.setattr(files, '_replace_path', fail_replace)
    with pytest.raises(files.FileOperationError, match='cannot move path'):
        files.move_path(str(source), str(destination), overwrite=True)
    assert source.read_text() == 'new'
    assert destination.read_text() == 'old'


def test_failed_install_restores_destination(tmp_path, monkeypatch):
    staged = tmp_path / '.destination.stage'
    destination = tmp_path / 'destination'
    staged.write_text('new')
    destination.write_text('old')
    original_rename = Path.rename

    def fail_staged_rename(path, target):
        if path == staged:
            raise OSError('simulated install failure')
        return original_rename(path, target)

    monkeypatch.setattr(Path, 'rename', fail_staged_rename)
    with pytest.raises(OSError, match='simulated install failure'):
        files._replace_path(staged, destination)
    assert destination.read_text() == 'old'
    assert staged.read_text() == 'new'


def test_failed_install_does_not_delete_concurrent_destination(tmp_path, monkeypatch):
    staged = tmp_path / '.destination.stage'
    destination = tmp_path / 'destination'
    staged.write_text('new')
    destination.write_text('old')
    original_rename = Path.rename

    def race_staged_rename(path, target):
        if path == staged:
            destination.write_text('concurrent')
            raise OSError('simulated install failure')
        return original_rename(path, target)

    monkeypatch.setattr(Path, 'rename', race_staged_rename)
    with pytest.raises(OSError, match='previous destination remains at'):
        files._replace_path(staged, destination)
    backups = list(tmp_path.glob('.*.bak'))
    assert destination.read_text() == 'concurrent'
    assert len(backups) == 1 and backups[0].read_text() == 'old'


def test_copy_reports_backup_when_cleanup_fails(tmp_path, monkeypatch):
    source = tmp_path / 'source.txt'
    destination = tmp_path / 'destination.txt'
    source.write_text('new')
    destination.write_text('old')
    original_remove = files._remove_path

    def fail_backup_cleanup(path):
        if path.name.endswith('.bak'):
            raise OSError('simulated cleanup failure')
        original_remove(path)

    monkeypatch.setattr(files, '_remove_path', fail_backup_cleanup)
    result = files.copy_path(str(source), str(destination), overwrite=True)
    assert result['status'] == 'copied'
    backup = Path(result['replacement_backup']['backup_path'])
    assert result['replacement_backup']['cleanup_error'] == 'simulated cleanup failure'
    assert destination.read_text() == 'new'
    assert backup.read_text() == 'old'
