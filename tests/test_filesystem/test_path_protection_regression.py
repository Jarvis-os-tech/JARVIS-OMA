"""Regression tests for normalized and symlink-aware protected paths."""
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

import filesystem.filesystem as fs


class ProtectedPathRegressionTests(unittest.TestCase):
    def test_parent_segments_cannot_bypass_protection(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            protected = root / 'protected'
            protected.mkdir()
            (protected / 'keep.txt').write_text('keep', encoding='utf-8')
            (root / 'source.txt').write_text('source', encoding='utf-8')
            alias = protected.parent / 'protected' / '..' / 'protected'

            with patch.object(fs, 'CRITICAL_PATHS', {protected}):
                with self.assertRaisesRegex(fs.FileOperationError, 'cannot delete'):
                    fs.delete_path(str(alias), recursive=True)
                with self.assertRaisesRegex(fs.FileOperationError, 'cannot move'):
                    fs.move_path(str(alias), str(root / 'moved'))
                with self.assertRaisesRegex(fs.FileOperationError, 'cannot overwrite'):
                    fs.copy_path(str(root / 'source.txt'), str(alias), overwrite=True)
                with self.assertRaisesRegex(fs.FileOperationError, 'cannot trash'):
                    fs.trash_path(str(alias))

            self.assertEqual((protected / 'keep.txt').read_text(encoding='utf-8'), 'keep')

    def test_symlink_aliases_to_protected_directory_are_blocked(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            protected = root / 'protected'
            protected.mkdir()
            marker = protected / 'keep.txt'
            marker.write_text('keep', encoding='utf-8')
            parent_alias = root / 'parent-alias'
            parent_alias.symlink_to(root, target_is_directory=True)
            final_alias = root / 'final-alias'
            final_alias.symlink_to(protected, target_is_directory=True)

            with patch.object(fs, 'CRITICAL_PATHS', {protected}):
                with self.assertRaises(fs.FileOperationError):
                    fs.delete_path(str(parent_alias / 'protected'), recursive=True)
                with self.assertRaises(fs.FileOperationError):
                    fs.delete_path(str(final_alias), recursive=True)
                with self.assertRaises(fs.FileOperationError):
                    fs.move_path(str(final_alias), str(root / 'moved'))
                with self.assertRaises(fs.FileOperationError):
                    fs.copy_path(str(root / 'source.txt'), str(final_alias), overwrite=True)
                with self.assertRaises(fs.FileOperationError):
                    fs.trash_path(str(final_alias))

            self.assertTrue(final_alias.is_symlink())
            self.assertEqual(marker.read_text(encoding='utf-8'), 'keep')

    def test_deleting_nonprotected_symlink_unlinks_link_not_target(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / 'target.txt'
            target.write_text('keep', encoding='utf-8')
            link = root / 'link.txt'
            link.symlink_to(target)

            with patch.object(fs, 'CRITICAL_PATHS', set()):
                fs.delete_path(str(link))

            self.assertFalse(link.is_symlink())
            self.assertEqual(target.read_text(encoding='utf-8'), 'keep')


if __name__ == '__main__':
    unittest.main()
