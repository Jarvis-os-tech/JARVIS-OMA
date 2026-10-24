"""Filesystem skill integration tests using an isolated temporary directory."""
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from skills import DesktopSkills, SkillError
import filesystem as fs


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
            await skills.execute('edit_file', {'path': str(original), 'old': 'hello', 'new': 'hello world'})
            self.assertEqual((await skills.execute('read_file', {'path': str(original)}))['content'], 'hello world')
            copied = root / 'copy.txt'
            await skills.execute('copy_path', {'source': str(original), 'destination': str(copied)})
            self.assertEqual(copied.read_text(), 'hello world')
            self.assertEqual((await skills.execute('search_files', {'path': str(root), 'query': 'note'}))['matches'], [str(original)])
            destination = root / 'moved.txt'
            await skills.execute('move_path', {'source': str(original), 'destination': str(destination)})
            self.assertEqual({item['name'] for item in (await skills.execute('list_files', {'path': str(root)}))['entries']}, {'copy.txt', 'moved.txt'})
            result = await skills.execute('trash_path', {'path': str(destination)})
            self.assertFalse(destination.exists())
            self.assertTrue(Path(result['trash_path']).exists())

    async def test_read_is_bounded_and_supports_offset(self):
        skills = DesktopSkills()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'large.txt'
            path.write_text('abcdefghijklmnopqrstuvwxyz', encoding='utf-8')
            result = await skills.execute('read_file', {'path': str(path), 'offset': 0, 'max_chars': 10})
            self.assertEqual(result['content'], 'abcdefghij')
            self.assertTrue(result['truncated'])
            self.assertTrue(result['has_more'])
            self.assertEqual(result['total_bytes'], 26)

            # Read with offset
            result2 = await skills.execute('read_file', {'path': str(path), 'offset': 10, 'max_chars': 10})
            self.assertEqual(result2['content'], 'klmnopqrst')
            self.assertTrue(result2['has_more'])

            # Read end
            result3 = await skills.execute('read_file', {'path': str(path), 'offset': 20, 'max_chars': 10})
            self.assertEqual(result3['content'], 'uvwxyz')
            self.assertFalse(result3['has_more'])

    async def test_unicode_character_offsets_and_pagination(self):
        skills = DesktopSkills()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'unicode.txt'
            # Offsets count Unicode code points, as Python string slicing does.
            text = 'éनमस्ते🙂 café\nREADY'
            path.write_text(text, encoding='utf-8')
            for offset in (1, 2, 6, 8, len(text), len(text) + 10):
                with self.subTest(offset=offset):
                    result = await skills.execute('read_file', {
                        'path': str(path), 'offset': offset, 'max_chars': 3})
                    self.assertEqual(result['content'], text[offset:offset + 3])
                    self.assertEqual(result['chars_read'], len(text[offset:offset + 3]))
                    self.assertEqual(result['has_more'], offset + 3 < len(text))
            parts = []
            offset = 0
            while True:
                page = await skills.execute('read_file', {
                    'path': str(path), 'offset': offset, 'max_chars': 3})
                parts.append(page['content'])
                offset += page['chars_read']
                if not page['has_more']:
                    break
            self.assertEqual(''.join(parts), text)
            path.write_text('é' * 9000 + 'READY', encoding='utf-8')
            page = await skills.execute('read_file', {
                'path': str(path), 'offset': 9000, 'max_chars': 5})
            self.assertEqual(page['content'], 'READY')
            self.assertFalse(page['has_more'])

    async def test_append_file_creates_and_extends_content(self):
        skills = DesktopSkills()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'log.txt'
            # Append creates file if not present
            res1 = await skills.execute('append_file', {'path': str(path), 'content': 'line 1\n'})
            self.assertEqual(res1['status'], 'appended')
            self.assertEqual(path.read_text(), 'line 1\n')

            # Append extends content
            res2 = await skills.execute('append_file', {'path': str(path), 'content': 'line 2\n'})
            self.assertEqual(res2['status'], 'appended')
            self.assertEqual(path.read_text(), 'line 1\nline 2\n')

    async def test_inspect_file_returns_detailed_metadata(self):
        skills = DesktopSkills()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'info.txt'
            path.write_text('hello\nworld\nautonomous\n', encoding='utf-8')

            info = await skills.execute('inspect_file', {'path': str(path)})
            self.assertTrue(info['exists'])
            self.assertEqual(info['name'], 'info.txt')
            self.assertEqual(info['type'], 'file')
            self.assertEqual(info['line_count'], 3)
            self.assertTrue(info['is_readable'])
            self.assertTrue(info['is_writable'])

            missing = await skills.execute('inspect_file', {'path': str(Path(directory) / 'missing.txt')})
            self.assertFalse(missing['exists'])

    async def test_search_file_content_finds_lines_and_snippets(self):
        skills = DesktopSkills()
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory) / 'src'
            work.mkdir()
            f1 = work / 'main.py'
            f1.write_text('def start():\n    print("JARVIS online")\n    return True\n', encoding='utf-8')
            f2 = work / 'config.py'
            f2.write_text('AUTONOMY_LEVEL = "FULL"\nAGENT = "JARVIS"\n', encoding='utf-8')

            result = await skills.execute('search_file_content', {'path': str(work), 'query': 'JARVIS'})
            self.assertFalse(result['truncated'])
            self.assertEqual(len(result['matches']), 2)
            paths = {m['path'] for m in result['matches']}
            self.assertEqual(paths, {str(f1), str(f2)})

            # Single file search
            res_single = await skills.execute('search_file_content', {'path': str(f1), 'query': 'online'})
            self.assertEqual(len(res_single['matches']), 1)
            self.assertEqual(res_single['matches'][0]['line_number'], 2)
            self.assertIn('JARVIS online', res_single['matches'][0]['line'])

    async def test_copy_and_move_with_overwrite(self):
        skills = DesktopSkills()
        with tempfile.TemporaryDirectory() as directory:
            src = Path(directory) / 'src.txt'
            dst = Path(directory) / 'dst.txt'
            src.write_text('v1', encoding='utf-8')
            dst.write_text('v0', encoding='utf-8')

            with self.assertRaisesRegex(SkillError, 'already exists'):
                await skills.execute('copy_path', {'source': str(src), 'destination': str(dst)})

            await skills.execute('copy_path', {'source': str(src), 'destination': str(dst), 'overwrite': True})
            self.assertEqual(dst.read_text(), 'v1')

            # Move with overwrite
            src2 = Path(directory) / 'src2.txt'
            src2.write_text('v2', encoding='utf-8')
            await skills.execute('move_path', {'source': str(src2), 'destination': str(dst), 'overwrite': True})
            self.assertFalse(src2.exists())
            self.assertEqual(dst.read_text(), 'v2')

    async def test_delete_path_permanent_removal_and_recursive(self):
        skills = DesktopSkills()
        with tempfile.TemporaryDirectory() as directory:
            file_to_del = Path(directory) / 'temp.txt'
            file_to_del.write_text('delete me', encoding='utf-8')
            res = await skills.execute('delete_path', {'path': str(file_to_del)})
            self.assertEqual(res['status'], 'deleted')
            self.assertFalse(file_to_del.exists())

            # Non-empty directory requires recursive=True
            folder = Path(directory) / 'subfolder'
            folder.mkdir()
            (folder / 'inner.txt').write_text('inside', encoding='utf-8')
            with self.assertRaisesRegex(SkillError, 'directory is not empty'):
                await skills.execute('delete_path', {'path': str(folder), 'recursive': False})
            self.assertTrue(folder.exists())

            res_dir = await skills.execute('delete_path', {'path': str(folder), 'recursive': True})
            self.assertEqual(res_dir['status'], 'deleted')
            self.assertFalse(folder.exists())

    async def test_critical_roots_are_protected_from_deletion_and_move(self):
        skills = DesktopSkills()
        for critical in ('/', '/etc', '/boot', '/root'):
            with self.subTest(critical=critical):
                with self.assertRaisesRegex(SkillError, 'system root or home directory'):
                    await skills.execute('delete_path', {'path': critical})
                with self.assertRaisesRegex(SkillError, 'system root or home directory'):
                    await skills.execute('move_path', {'source': critical, 'destination': '/tmp/target'})
