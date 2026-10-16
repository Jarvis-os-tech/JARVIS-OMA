from datetime import datetime, timedelta
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from core.greeting import GreetingMemory, greeting_prompt
from core.agent import LiveVoice
from core.config import Config, MemoryConfig


class GreetingTests(unittest.TestCase):
    def test_restart_suppression_and_next_day_continuity(self):
        with tempfile.TemporaryDirectory() as directory:
            store = GreetingMemory(Path(directory))
            now = datetime(2026, 10, 14, 23, 30, tzinfo=ZoneInfo('Asia/Kolkata'))
            history = [{'role': 'user', 'content': 'Continue Claude authentication tomorrow', 'timestamp': 123}]
            prepared = store.prepare(history, now, 14400)
            self.assertEqual(prepared['history'], history)
            identifier = store.sent(prepared['key'], now)
            store.record_text(identifier, 'Shall we pick up the Claude authentication issue?')
            restarted = GreetingMemory(Path(directory))
            self.assertTrue(restarted.prepare(history, now + timedelta(minutes=5), 14400)['suppressed'])
            next_day = restarted.prepare(history, now + timedelta(hours=1), 14400)
            self.assertFalse(next_day['suppressed'])
            self.assertEqual(next_day['history'], [])
            self.assertIn('Shall we pick up', next_day['previous_greetings'][0])
            new_history = history + [{'role': 'user', 'content': 'Now fix Codex', 'timestamp': 456}]
            self.assertEqual(restarted.prepare(new_history, now + timedelta(days=1), 14400)['history'], new_history)

    def test_assistant_greetings_do_not_make_old_work_fresh(self):
        with tempfile.TemporaryDirectory() as directory:
            store = GreetingMemory(Path(directory))
            now = datetime.now().astimezone()
            history = [{'role': 'user', 'content': 'Build the desktop launcher', 'timestamp': 10}]
            prepared = store.prepare(history, now, 0)
            store.sent(prepared['key'], now)
            history.append({'role': 'assistant', 'content': 'Welcome back', 'timestamp': 11})
            self.assertEqual(store.prepare(history, now, 0)['history'], [])

    def test_prompt_restricts_followups_to_evidence(self):
        prompt = greeting_prompt('Jarvis', 'English', datetime.now().astimezone(), [], [])
        self.assertIn('at most ONE', prompt)
        self.assertIn('completed, cancelled', prompt)
        self.assertIn('untrusted', prompt)
        self.assertIn('Do not execute tools', prompt)


class GreetingIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_saved_context_reaches_greeting_once_across_restarts(self):
        with tempfile.TemporaryDirectory() as directory:
            history = [{'role': 'user', 'content': 'Claude task was interrupted; continue tomorrow', 'timestamp': 123}]
            memory = SimpleNamespace(root=Path(directory), recall_history=lambda *args: history)
            skills = SimpleNamespace(memory=memory)
            config = Config(memory=MemoryConfig(path=directory))
            session = AsyncMock()
            voice = LiveVoice(None, config=config, skills=skills)
            await voice.greet(session)
            self.assertIn('Claude task was interrupted', session.send_client_content.call_args.kwargs['turns'].parts[0].text)
            restarted = LiveVoice(None, config=config, skills=skills)
            await restarted.greet(session)
            self.assertEqual(session.send_client_content.await_count, 1)
