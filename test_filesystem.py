"""Filesystem skill integration tests using an isolated temporary directory."""
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from skills import DesktopSkills, SkillError


class FilesystemSkillTests(unittest.IsolatedAsyncioTestCase):
    async def test_create_read_search_move_and_trash(self):
        skills = DesktopSkills()
        with tempfile.TemporaryDirectory() as directory, patch.dict('os.environ', {'XDG_DATA_HOME': directory}):
            root = Path(directory) / 'work'
            await skills.execute('make_directory', {'path': str(root)})
            original = root / 'note.txt'
            await skills.execute('write_file', {'path': str(original), 'content': 'hello'})
            with self.assertRaisesRegex(SkillError, 'file exists'):
                await skills.execute('write_file', {'path': str(original), 'content': 'replace'})
            self.assertEqual((await skills.execute('read_file', {'path': str(original)}))['content'], 'hello')
            self.assertEqual((await skills.execute('search_files', {'path': str(root), 'query': 'note'}))['matches'], [str(original)])
            destination = root / 'moved.txt'
            await skills.execute('move_path', {'source': str(original), 'destination': str(destination)})
            self.assertEqual((await skills.execute('list_files', {'path': str(root)}))['entries'][0]['name'], 'moved.txt')
            result = await skills.execute('trash_path', {'path': str(destination)})
            self.assertFalse(destination.exists())
            self.assertTrue(Path(result['trash_path']).exists())

    async def test_read_is_bounded(self):
        skills = DesktopSkills()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'large.txt'
            path.write_text('a' * 100, encoding='utf-8')
            result = await skills.execute('read_file', {'path': str(path), 'max_chars': 10})
            self.assertEqual(result['content'], 'a' * 10)
            self.assertTrue(result['truncated'])
