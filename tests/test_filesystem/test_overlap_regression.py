"""Regression coverage for overlapping filesystem copy and move paths."""
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

import filesystem.filesystem as fs


class OverlappingPathRegressionTests(unittest.TestCase):
    def test_overwrite_rejects_destination_ancestor_of_source_before_mutation(self):
        for operation in (fs.copy_path, fs.move_path):
            with self.subTest(operation=operation.__name__), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                source = root / 'tree' / 'source.txt'
                source.parent.mkdir()
                source.write_text('preserve me', encoding='utf-8')
                with patch.object(fs, 'CRITICAL_PATHS', set()):
                    with self.assertRaisesRegex(fs.FileOperationError, 'overlap'):
                        operation(str(source), str(root / 'tree'), overwrite=True)
                self.assertEqual(source.read_text(encoding='utf-8'), 'preserve me')

    def test_rejects_source_ancestor_of_destination(self):
        for operation in (fs.copy_path, fs.move_path):
            with self.subTest(operation=operation.__name__), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                source = root / 'tree'
                source.mkdir()
                nested = source / 'nested'
                nested.mkdir()
                with patch.object(fs, 'CRITICAL_PATHS', set()):
                    with self.assertRaisesRegex(fs.FileOperationError, 'overlap'):
                        operation(str(source), str(nested / 'copy'), overwrite=True)
                self.assertTrue(source.is_dir())
                self.assertTrue(nested.is_dir())

    def test_parent_symlink_and_dotdot_aliases_are_normalized(self):
        for operation in (fs.copy_path, fs.move_path):
            with self.subTest(operation=operation.__name__), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                tree = root / 'tree'
                tree.mkdir()
                source = tree / 'source.txt'
                source.write_text('preserve me', encoding='utf-8')
                parent_alias = root / 'parent-alias'
                parent_alias.symlink_to(root, target_is_directory=True)
                aliased_destination = parent_alias / 'tree' / '..' / 'tree'
                with patch.object(fs, 'CRITICAL_PATHS', set()):
                    with self.assertRaisesRegex(fs.FileOperationError, 'overlap'):
                        operation(str(source), str(aliased_destination), overwrite=True)
                self.assertEqual(source.read_text(encoding='utf-8'), 'preserve me')

    def test_dotdot_after_parent_symlink_uses_real_target_parent(self):
        for operation in (fs.copy_path, fs.move_path):
            with self.subTest(operation=operation.__name__), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                alias_root = root / 'aliases'
                actual_root = root / 'actual'
                alias_root.mkdir()
                branch = actual_root / 'branch'
                (branch / 'child').mkdir(parents=True)
                source = branch / 'source.txt'
                source.write_text('preserve me', encoding='utf-8')
                (alias_root / 'link').symlink_to(branch / 'child', target_is_directory=True)
                # Resolving link/.. yields actual/branch, an ancestor of source.
                destination = alias_root / 'link' / '..'
                with patch.object(fs, 'CRITICAL_PATHS', set()):
                    with self.assertRaisesRegex(fs.FileOperationError, 'overlap'):
                        operation(str(source), str(destination), overwrite=True)
                self.assertEqual(source.read_text(encoding='utf-8'), 'preserve me')

    def test_rejects_distinct_hardlink_names_before_overwrite(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / 'source.txt'
            destination = root / 'destination.txt'
            source.write_text('same inode', encoding='utf-8')
            destination.hardlink_to(source)
            with patch.object(fs, 'CRITICAL_PATHS', set()):
                for operation in (fs.copy_path, fs.move_path):
                    with self.subTest(operation=operation.__name__):
                        with self.assertRaisesRegex(fs.FileOperationError, 'overlap'):
                            operation(str(source), str(destination), overwrite=True)
            self.assertEqual(source.read_text(encoding='utf-8'), 'same inode')
            self.assertEqual(destination.read_text(encoding='utf-8'), 'same inode')

    def test_final_symlink_copy_and_move_keep_link_semantics(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / 'target.txt'
            target.write_text('target contents', encoding='utf-8')
            source_link = root / 'source-link'
            source_link.symlink_to(target.name)
            copied_link = root / 'copied-link'
            moved_link = root / 'moved-link'
            with patch.object(fs, 'CRITICAL_PATHS', set()):
                fs.copy_path(str(source_link), str(copied_link))
                fs.move_path(str(source_link), str(moved_link))
            self.assertTrue(copied_link.is_symlink())
            self.assertTrue(moved_link.is_symlink())
            self.assertEqual(copied_link.readlink(), Path(target.name))
            self.assertEqual(moved_link.readlink(), Path(target.name))
            self.assertFalse(source_link.exists())
            self.assertEqual(target.read_text(encoding='utf-8'), 'target contents')

    def test_removing_ancestor_of_protected_path_is_blocked(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            ancestor = root / 'container'
            protected = ancestor / 'keep'
            protected.mkdir(parents=True)
            marker = protected / 'marker.txt'
            marker.write_text('keep', encoding='utf-8')
            allowed_descendant = protected / 'ordinary.txt'
            allowed_descendant.write_text('ordinary', encoding='utf-8')
            with patch.object(fs, 'CRITICAL_PATHS', {protected}):
                with self.assertRaisesRegex(fs.FileOperationError, 'cannot delete'):
                    fs.delete_path(str(ancestor), recursive=True)
                fs.delete_path(str(allowed_descendant))
            self.assertTrue(marker.exists())
            self.assertFalse(allowed_descendant.exists())


if __name__ == '__main__':
    unittest.main()
