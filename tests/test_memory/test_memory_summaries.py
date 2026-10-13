from datetime import datetime, timezone
from contextlib import closing
from pathlib import Path
import re
import sqlite3
import tempfile
from types import SimpleNamespace
import unittest

from jarvis_memory.obsidian import FOLDER, plain, publish
from jarvis_memory.summaries import render_daily_summary


class MemorySummaryTests(unittest.TestCase):
    def test_extracts_verbatim_claims_with_provenance(self):
        texts = ['Please fix the service', 'I prefer short answers',
                 'I decided to use local storage', 'I fixed it; tests passed',
                 'Tomorrow we could follow up', 'I cannot confirm completion']
        turns = [(i, 'user' if i < 4 else 'assistant', text, datetime(2026, 10, 12))
                 for i, text in enumerate(texts, 1)]
        result = render_daily_summary(turns)
        for i, text in enumerate(texts, 1):
            self.assertIn(f'message {i}', result)
            self.assertIn(text, result)
        self.assertIn('Assistant reported outcomes (unverified)', result)
        self.assertIn('Explicit follow-up mentions', result)
        self.assertIn('User decisions', result)
        self.assertIn('User preferences', result)
        self.assertNotIn('Tasks completed', result)
        self.assertNotIn('Explicit follow-up mentions', render_daily_summary(turns[:4]))

    def test_dictionary_and_empty_input(self):
        result = render_daily_summary([{'id': 9, 'role': 'user', 'content': 'Please help'}])
        self.assertIn('message 9 (user)', result)
        self.assertIn('Please help', result)
        self.assertIn('No supported dialogue', render_daily_summary([]))

    def test_long_days_are_bounded_excerpts_not_duplicate_transcripts(self):
        turns = [(index, 'user', 'Please finish the feature ' + 'details ' * 100,
                  datetime(2026, 10, 13)) for index in range(30)]
        result = render_daily_summary(turns)
        self.assertIn('Excerpt ends', result)
        self.assertIn('22 additional mentions', result)
        self.assertLess(len(result), sum(len(turn[2]) for turn in turns))

    def test_export_links_escaping_timezone_and_manual_edits(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            vault = root / 'vault'
            vault.mkdir()
            state = root / 'state'
            state.mkdir()
            before = datetime(2026, 10, 12, 18, 29, tzinfo=timezone.utc).timestamp()
            after = datetime(2026, 10, 12, 18, 31, tzinfo=timezone.utc).timestamp()
            malicious = 'Please quote <script>alert(1)</script> [[Injected]] <!-- marker -->'
            with closing(sqlite3.connect(state / 'sessions.db')) as connection, connection:
                connection.execute('CREATE TABLE sessions (session_id TEXT, user_id TEXT)')
                connection.execute('CREATE TABLE session_messages '
                                   '(id INTEGER, session_id TEXT, role TEXT, content TEXT, timestamp REAL)')
                connection.execute('INSERT INTO sessions VALUES (?, ?)', ('test', 'local-user'))
                connection.executemany('INSERT INTO session_messages VALUES (?, ?, ?, ?, ?)', [
                    (1, 'test', 'user', malicious, before),
                    (2, 'test', 'assistant', 'I completed the change', before),
                    (3, 'test', 'user', 'I prefer local tools; follow up tomorrow', after)])
            # Isolate escaping from scanner policy: all fixture text reaches plain().
            memory = SimpleNamespace(root=state,
                config=SimpleNamespace(record_sessions=True, obsidian_timezone='Asia/Kolkata'),
                store=SimpleNamespace(list=lambda: []),
                scanner=SimpleNamespace(scan=lambda text: SimpleNamespace(is_clean=True)))
            self.assertEqual(publish(memory, vault)['status'], 'synced')
            base = vault / FOLDER
            monday = base / 'Summaries/2026-10-12 - Monday.md'
            tuesday = base / 'Summaries/2026-10-13 - Tuesday.md'
            summary = monday.read_text()
            self.assertIn(plain(malicious), summary)
            self.assertNotIn('<script>', summary)
            self.assertNotIn('[[Injected]]', summary)
            self.assertIn('message 2 (assistant)', summary)
            self.assertIn('unverified', summary)
            self.assertNotIn('I prefer local tools', summary)
            self.assertIn('I prefer local tools', tuesday.read_text())
            transcript = (base / 'Conversations/2026-10-12 - Monday.md').read_text()
            self.assertIn('[23:59:00]', transcript)
            self.assertIn(plain(malicious), transcript)
            self.assertIn('[[JARVIS-OMA Memory/Summaries/2026-10-12 - Monday]]', transcript)
            self.assertIn('[[JARVIS-OMA Memory/Conversations/2026-10-12 - Monday]]', summary)
            self.assertIn('[[JARVIS-OMA Memory/Summaries]]', (base / 'Memory Map.md').read_text())
            self.assertIn(plain(malicious), (base / 'Conversations/conversation.md').read_text())
            for note in base.rglob('*.md'):
                for target in re.findall(r'\[\[([^\]]+)\]\]', note.read_text()):
                    self.assertTrue((vault / (target + '.md')).is_file(), target)
            self.assertEqual(publish(memory, vault)['written'], 0)
            manual = summary + '\nPersonal summary annotation\n'
            monday.write_text(manual)
            with closing(sqlite3.connect(state / 'sessions.db')) as connection, connection:
                connection.execute('INSERT INTO session_messages VALUES (?, ?, ?, ?, ?)',
                                   (4, 'test', 'user', 'Please check again', before))
            result = publish(memory, vault)
            self.assertIn('Summaries/2026-10-12 - Monday.md', result['conflicts'])
            self.assertEqual(monday.read_text(), manual)
            self.assertIn('Please check again',
                          (base / 'Conversations/2026-10-12 - Monday.md').read_text())


if __name__ == '__main__':
    unittest.main()
