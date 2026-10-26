"""Fault-injected recovery tests for copy and move replacement."""
import errno
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

import filesystem.filesystem as fs


class ReplacementRecoveryTests(unittest.TestCase):
    def test_copy_enospc_keeps_old_file_destination(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, destination = root / 'source', root / 'destination'
            source.write_text('new', encoding='utf-8')
            destination.write_text('old', encoding='utf-8')
            with patch.object(fs, 'CRITICAL_PATHS', set()), patch.object(
                    fs.shutil, 'copy2', side_effect=OSError(errno.ENOSPC, 'disk full')):
                with self.assertRaisesRegex(fs.FileOperationError, 'cannot copy'):
                    fs.copy_path(str(source), str(destination), overwrite=True)
            self.assertEqual(source.read_text(encoding='utf-8'), 'new')
            self.assertEqual(destination.read_text(encoding='utf-8'), 'old')

    def test_copy_publish_failure_restores_old_directory_without_nesting(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, destination = root / 'source', root / 'destination'
            source.mkdir()
            (source / 'new.txt').write_text('new', encoding='utf-8')
            destination.mkdir()
            (destination / 'old.txt').write_text('old', encoding='utf-8')
            original_replace = Path.replace

            def fail_publish(path, target):
                if Path(target) == destination and '.stage.' in path.name:
                    raise OSError(errno.EIO, 'publish failed')
                return original_replace(path, target)

            with patch.object(fs, 'CRITICAL_PATHS', set()), patch.object(Path, 'replace', fail_publish):
                with self.assertRaisesRegex(fs.FileOperationError, 'cannot copy'):
                    fs.copy_path(str(source), str(destination), overwrite=True)
            self.assertEqual((destination / 'old.txt').read_text(encoding='utf-8'), 'old')
            self.assertFalse((destination / 'source').exists())

    def test_copy_backup_cleanup_failure_keeps_published_destination_and_backup(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, destination = root / 'source', root / 'destination'
            source.write_text('new', encoding='utf-8')
            destination.write_text('old', encoding='utf-8')
            remove = fs._remove_entry

            def fail_backup_cleanup(path):
                if '.backup.' in path.name:
                    raise OSError(errno.EACCES, 'cleanup failed')
                return remove(path)

            with patch.object(fs, 'CRITICAL_PATHS', set()), patch.object(fs, '_remove_entry', fail_backup_cleanup):
                result = fs.copy_path(str(source), str(destination), overwrite=True)
            self.assertEqual(destination.read_text(encoding='utf-8'), 'new')
            self.assertEqual(source.read_text(encoding='utf-8'), 'new')
            self.assertTrue(Path(result['recovery_backup']).exists())

    def test_partial_directory_backup_cleanup_keeps_new_destination(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, destination = root / 'source', root / 'destination'
            source.mkdir()
            (source / 'new.txt').write_text('new', encoding='utf-8')
            destination.mkdir()
            (destination / 'old.txt').write_text('old', encoding='utf-8')
            (destination / 'other.txt').write_text('also old', encoding='utf-8')

            def partial_rmtree(path):
                children = list(Path(path).iterdir())
                children[0].unlink()
                raise OSError(errno.EIO, 'cleanup interrupted')

            with patch.object(fs, 'CRITICAL_PATHS', set()), patch.object(fs.shutil, 'rmtree', partial_rmtree):
                result = fs.copy_path(str(source), str(destination), overwrite=True)
            self.assertEqual((destination / 'new.txt').read_text(encoding='utf-8'), 'new')
            self.assertTrue(Path(result['recovery_backup']).is_dir())

    def test_move_publish_failure_restores_both_source_and_destination(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, destination = root / 'source', root / 'destination'
            source.write_text('new', encoding='utf-8')
            destination.write_text('old', encoding='utf-8')
            def fail_publish(staged, target, **kwargs):
                raise OSError(errno.EIO, 'publish failed')

            with patch.object(fs, 'CRITICAL_PATHS', set()), patch.object(fs, '_publish_staged', fail_publish):
                with self.assertRaisesRegex(fs.FileOperationError, 'cannot move'):
                    fs.move_path(str(source), str(destination), overwrite=True)
            self.assertEqual(source.read_text(encoding='utf-8'), 'new')
            self.assertEqual(destination.read_text(encoding='utf-8'), 'old')

    def test_move_source_cleanup_failure_names_recoverable_copy(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, destination = root / 'source', root / 'destination'
            source.write_text('new', encoding='utf-8')
            destination.write_text('old', encoding='utf-8')
            remove = fs._remove_entry

            def fail_source_cleanup(path):
                if '.move-backup.' in path.name:
                    raise OSError(errno.EACCES, 'cleanup failed')
                return remove(path)

            with patch.object(fs, 'CRITICAL_PATHS', set()), patch.object(fs, '_remove_entry', fail_source_cleanup):
                result = fs.move_path(str(source), str(destination), overwrite=True)
            recoverable = Path(result['recovery_backup'])
            self.assertTrue(recoverable.exists())
            self.assertEqual(recoverable.read_text(encoding='utf-8'), 'new')
            self.assertEqual(destination.read_text(encoding='utf-8'), 'new')
            self.assertFalse(source.exists())


if __name__ == '__main__':
    unittest.main()
