"""Connection deadlines, cleanup and bounded resumption recovery."""
import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from core.connection import connect_live, ResumeRecovery, ToolCallCache, ToolCallConflict, LiveSessionState


class ConnectionTests(unittest.IsolatedAsyncioTestCase):
    async def test_domain_leaf_execution_preserves_original_provider_response_identity(self):
        from google.genai import types
        from core.agent import LiveVoice
        skills = SimpleNamespace(
            resolve_domain_call=lambda **kwargs: ('inspect_screen', {}),
            execute=AsyncMock(return_value={'status': 'inspected', 'text_content': 'Dialog'}))
        voice = LiveVoice(None, skills=skills)
        call = types.FunctionCall(id='domain-one', name='execute_domain_tool',
            args={'domain': 'gui', 'tool_name': 'inspect_screen', 'arguments_json': '{}'})
        session = SimpleNamespace(send_tool_response=AsyncMock())
        with patch('core.agent._read_visual_frame', return_value=None):
            await voice.handle(types.LiveServerMessage(tool_call=types.LiveServerToolCall(function_calls=[call])), session)
            await asyncio.gather(*list(voice.tool_tasks.values()))
        skills.execute.assert_awaited_once_with('inspect_screen', {})
        result = session.send_tool_response.await_args.kwargs['function_responses']
        self.assertEqual((result.id, result.name), ('domain-one', 'execute_domain_tool'))
        self.assertEqual(result.response['output']['visual_input'], 'ocr_only')

    def test_result_survives_resume_and_fresh_conversation_starts_new_namespace(self):
        state = LiveSessionState()
        state.opened(resumed=False)
        self.assertEqual(state.tools.claim('call', 'open_application', {'name': 'editor'}), 'new')
        state.tools.store('call', {'status': 'opened'})
        state.disconnect()
        state.opened(resumed=True)
        self.assertEqual(state.tools.claim('call', 'open_application', {'name': 'editor'}), 'result_ready')
        self.assertEqual(state.tools.responses['call'], {'status': 'opened'})
        state.opened(resumed=False)
        self.assertEqual(state.epoch, 2)
        self.assertEqual(state.tools.claim('call', 'open_application', {'name': 'browser'}), 'new')

    def test_tool_identity_conflict_and_cache_exhaustion_never_reexecute(self):
        cache = ToolCallCache(capacity=1, max_result_bytes=1)
        cache.claim('one', 'write_file', {'path': '/tmp/a'})
        cache.store('one', {'output': 'larger than cache'})
        cache.disconnect()
        self.assertEqual(cache.claim('one', 'write_file', {'path': '/tmp/a'}), 'result_unavailable')
        with self.assertRaises(ToolCallConflict):
            cache.claim('one', 'write_file', {'path': '/tmp/b'})
        with self.assertRaises(ToolCallConflict):
            cache.claim('two', 'write_file', {'path': '/tmp/b'})

    async def test_reconnected_provider_duplicate_gets_cached_result_without_second_action(self):
        from google.genai import types
        from core.agent import LiveVoice
        skills = SimpleNamespace(execute=AsyncMock(return_value={'status': 'opened'}))
        voice = LiveVoice(None, skills=skills)
        session = SimpleNamespace(send_tool_response=AsyncMock(side_effect=ConnectionError('disconnected')))
        call = types.FunctionCall(id='one', name='open_application', args={'name': 'editor'})
        event = types.LiveServerMessage(tool_call=types.LiveServerToolCall(function_calls=[call]))
        await voice.handle(event, session)
        await asyncio.gather(*list(voice.tool_tasks.values()), return_exceptions=True)
        await voice.cancel_tools()
        voice.session_state.opened(resumed=True)
        voice.send_lock.reset()
        session.send_tool_response = AsyncMock()
        await voice.handle(event, session)
        await asyncio.gather(*list(voice.tool_tasks.values()))
        skills.execute.assert_awaited_once()
        result = session.send_tool_response.await_args.kwargs['function_responses']
        self.assertEqual(result.id, 'one')
        self.assertEqual(result.response['output']['status'], 'opened')

    async def test_interrupted_action_is_retained_as_unknown_and_never_automatically_replayed(self):
        from google.genai import types
        from core.agent import LiveVoice
        started = asyncio.Event()

        async def execute(*args):
            started.set()
            await asyncio.Event().wait()

        skills = SimpleNamespace(execute=AsyncMock(side_effect=execute))
        voice = LiveVoice(None, skills=skills)
        call = types.FunctionCall(id='one', name='write_file', args={'path': '/tmp/a', 'content': 'x'})
        event = types.LiveServerMessage(tool_call=types.LiveServerToolCall(function_calls=[call]))
        session = SimpleNamespace(send_tool_response=AsyncMock())
        await voice.handle(event, session)
        await asyncio.wait_for(started.wait(), 1)
        await voice.cancel_tools()
        voice.session_state.opened(resumed=True)
        voice.send_lock.reset()
        await voice.handle(event, session)
        await asyncio.gather(*list(voice.tool_tasks.values()))
        skills.execute.assert_awaited_once()
        result = session.send_tool_response.await_args.kwargs['function_responses'].response
        self.assertEqual(result['execution'], 'outcome_unknown')
        self.assertFalse(result['replayed'])

    def test_connection_revisions_are_atomic_and_audio_callbacks_cannot_restore_stale_ready(self):
        from core.agent import LiveVoice
        voice = LiveVoice(None)
        voice._connection_managed = True
        voice.session_state.opened(resumed=False)
        voice.publish_lifecycle_state('speaking')
        previous = voice.session_state.snapshot()['connection_revision']
        voice.session_state.disconnect()
        voice.publish_lifecycle_state('reconnecting')
        voice.publish_audio_state('listening')
        snapshot = voice.session_state.snapshot()
        self.assertEqual(snapshot['connection_state'], 'reconnecting')
        self.assertGreater(snapshot['connection_revision'], previous)
        self.assertEqual(voice.lifecycle_state, 'reconnecting')

    async def test_setup_deadline_cancels_and_cleans_pending_handshake(self):
        cleaned = asyncio.Event()

        @asynccontextmanager
        async def connect(**kwargs):
            try:
                await asyncio.Event().wait()
                yield object()
            finally:
                cleaned.set()

        client = SimpleNamespace(live=SimpleNamespace(connect=connect))
        with self.assertRaises(TimeoutError):
            async with connect_live(client, model='test', config={}, timeout=.01):
                self.fail('A hung connection must not open')
        self.assertTrue(cleaned.is_set())

    async def test_deadline_does_not_end_live_conversation_and_cleanup_is_owned(self):
        closed = []

        @asynccontextmanager
        async def connect(**kwargs):
            try:
                yield 'session'
            finally:
                closed.append(True)

        client = SimpleNamespace(live=SimpleNamespace(connect=connect))
        async with connect_live(client, model='test', config={}, timeout=.01) as session:
            await asyncio.sleep(.03)
            self.assertEqual(session, 'session')
            self.assertEqual(closed, [])
        self.assertEqual(closed, [True])

    def test_resume_retries_are_bounded_without_replaying_requests(self):
        recovery = ResumeRecovery()
        self.assertFalse(recovery.failed('handle', opened=False, code=None, transient=True))
        self.assertTrue(recovery.failed('handle', opened=False, code=None, transient=True))
        self.assertFalse(recovery.failed(None, opened=False, code=None, transient=True))

    def test_success_and_live_disconnect_reset_failed_handshakes(self):
        recovery = ResumeRecovery()
        recovery.failed('handle', opened=False, code=None, transient=True)
        recovery.opened()
        self.assertFalse(recovery.failed('new', opened=False, code=None, transient=True))
        self.assertFalse(recovery.failed('new', opened=True, code=1006, transient=True))
        self.assertEqual(recovery.failures, 0)

    def test_rejection_starts_fresh_but_rate_limits_and_config_errors_do_not(self):
        for code in (400, 1008):
            self.assertTrue(ResumeRecovery().failed('handle', opened=False, code=code, transient=False))
        for code in (429, 401, 403):
            recovery = ResumeRecovery()
            for _ in range(4):
                self.assertFalse(recovery.failed('handle', opened=False, code=code, transient=code == 429))

    def test_connection_timeout_config_validation(self):
        from core.config import Config
        for value in (0, 61, True, '10'):
            config = Config()
            config.agent.connect_timeout_seconds = value
            with self.assertRaisesRegex(ValueError, 'connect_timeout_seconds'):
                config.validate()
