from datetime import datetime, timedelta
from pathlib import Path
import sqlite3
import tempfile
import unittest
from zoneinfo import ZoneInfo

from core.greeting import GreetingMemory


class GreetingRetentionTests(unittest.TestCase):
    def test_retention_is_bounded_and_keeps_recent_greetings(self):
        with tempfile.TemporaryDirectory() as directory:
            memory = GreetingMemory(Path(directory))
            start = datetime(2026, 10, 1, tzinfo=ZoneInfo('Asia/Kolkata'))
            identifiers = []
            latest_history = [{'role': 'user', 'content': f'context-{memory.MAX_RECORDS + 7}'}]

            for index in range(memory.MAX_RECORDS + 8):
                current = start + timedelta(minutes=index)
                key = f'context-{index}'
                if index == memory.MAX_RECORDS + 7:
                    key = memory.prepare(latest_history, current, 0)['key']
                identifier = memory.sent(key, current, f'boot-{index}')
                identifiers.append(identifier)
                if index >= memory.MAX_RECORDS:
                    memory.record_text(identifier, f'greeting-{index}')

            with sqlite3.connect(memory.path) as db:
                count = db.execute('SELECT COUNT(*) FROM greetings').fetchone()[0]
                oldest_id = db.execute('SELECT MIN(id) FROM greetings').fetchone()[0]
                newest_id = db.execute('SELECT MAX(id) FROM greetings').fetchone()[0]

            self.assertEqual(count, memory.MAX_RECORDS)
            self.assertEqual(oldest_id, identifiers[-memory.MAX_RECORDS])
            self.assertEqual(newest_id, identifiers[-1])

            latest_time = start + timedelta(minutes=memory.MAX_RECORDS + 7)
            prepared = memory.prepare(latest_history, latest_time, 0, f'boot-{memory.MAX_RECORDS + 7}')
            self.assertEqual(prepared['history'], [])
            self.assertEqual(
                prepared['previous_greetings'],
                [f'greeting-{index}' for index in range(memory.MAX_RECORDS + 7,
                                                       memory.MAX_RECORDS - 1, -1)],
            )

    def test_next_insert_prunes_legacy_excess_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            memory = GreetingMemory(Path(directory))
            current = datetime(2026, 10, 26, tzinfo=ZoneInfo('Asia/Kolkata'))
            with sqlite3.connect(memory.path) as db:
                db.executemany(
                    'INSERT INTO greetings(timestamp,day,context_key,text,boot_id) VALUES(?,?,?,?,?)',
                    [(current.timestamp() - index, current.date().isoformat(), f'legacy-{index}', '', '')
                     for index in range(memory.MAX_RECORDS + 5)],
                )

            latest_id = memory.sent('new-context', current, 'new-boot')
            with sqlite3.connect(memory.path) as db:
                count = db.execute('SELECT COUNT(*) FROM greetings').fetchone()[0]
                latest = db.execute('SELECT id FROM greetings ORDER BY id DESC LIMIT 1').fetchone()[0]

            self.assertEqual(count, memory.MAX_RECORDS)
            self.assertEqual(latest, latest_id)


if __name__ == '__main__':
    unittest.main()
