"""Voice routing and global control contracts for capability development."""
import asyncio
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, Mock, patch

from core.config import Config
from skills import DesktopSkills, SkillError
from core.agent import LiveVoice


class DevelopmentSkillsTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.env = patch.dict(os.environ, {'XDG_STATE_HOME': self.temporary.name})
        self.env.start()
        self.addCleanup(self.env.stop)
        cfg = Config()
        cfg.memory.path = str(Path(self.temporary.name) / 'memory')
        self.skills = DesktopSkills(config=cfg)

    async def test_proactive_artifact_check_is_declared_and_forwarded(self):
        runtime = Mock()
        runtime.call = AsyncMock(return_value={'status': 'queued', 'event_id': 'event-1'})
        self.skills._proactive = runtime
        check = {'path': 'result.txt', 'sha256': 'a' * 64}
        await self.skills.execute('proactive_task', {
            'prompt': 'Copy known artifact', 'workspace': self.temporary.name, 'artifact_check': check})
        runtime.call.assert_awaited_once_with('enqueue', 'Copy known artifact', self.temporary.name, None,
                                              authorized=True, verification=[check])
        with self.assertRaises(SkillError):
            await self.skills.execute('proactive_task', {
                'prompt': 'Copy artifact', 'workspace': self.temporary.name,
                'artifact_check': {'path': 'result.txt'}})

    async def test_discovery_is_lazy_and_read_only_list_does_not_create_state(self):
        self.assertIn('start_development', {item['name'] for item in self.skills.declarations})
        self.assertIsNone(self.skills._evolution)
        self.assertEqual(await self.skills.execute('list_development_jobs', {}),
                         {'status': 'success', 'jobs': []})
        self.assertFalse((Path(self.temporary.name) / 'jarvis-oma/evolution').exists())

    async def test_routes_goal_to_manager_and_validates_agent(self):
        manager = Mock()
        manager.start = AsyncMock(return_value={'status': 'success', 'job': {'id': 'dev-1'}})
        self.skills._evolution = manager
        result = await self.skills.execute('start_development', {
            'goal': 'Add a skill', 'workspace': '/project', 'agent': 'codex'})
        self.assertEqual(result['job']['id'], 'dev-1')
        manager.start.assert_awaited_once_with('Add a skill', '/project', 'codex')
        with self.assertRaises(SkillError):
            await self.skills.execute('start_development', {
                'goal': 'Do work', 'workspace': '/project', 'agent': 'arbitrary-shell'})

    async def test_missing_capability_preserves_original_request(self):
        manager = Mock()
        manager.start = AsyncMock(return_value={'status': 'success', 'job': {'id': 'dev-2'}})
        self.skills._evolution = manager
        result = await self.skills.execute('request_capability', {
            'request': 'toggle night mode', 'workspace': '/project'})
        self.assertEqual(result['job']['id'], 'dev-2')
        goal, workspace, agent = manager.start.await_args.args
        self.assertIn('Original user request: toggle night mode', goal)
        self.assertEqual((workspace, agent), ('/project', 'codex'))
        self.assertEqual(manager.start.await_args.kwargs['requested_action'], 'toggle night mode')

    async def test_pause_and_stop_cancel_development_before_advancing(self):
        manager = Mock(workers={'dev-1': object()})
        manager.cancel = AsyncMock()
        self.skills._evolution = manager
        self.assertTrue(self.skills.proactive_service_requested.is_set())
        self.assertFalse(self.skills.proactive_continuous_requested)
        self.assertEqual((await self.skills.execute('pause_jarvis', {}))['status'], 'paused')
        manager.cancel.assert_awaited_with('dev-1')
        self.assertFalse(self.skills.proactive.control.get_state().can_run)
        self.assertFalse(self.skills.proactive_service_requested.is_set())
        await self.skills._adapter_proactive_resume()
        self.assertTrue(self.skills.proactive.control.get_state().can_run)
        self.assertTrue(self.skills.proactive_service_requested.is_set())
        self.assertTrue(self.skills.proactive_continuous_requested)
        result = await self.skills._adapter_proactive_stop()
        self.assertEqual(result['status'], 'stopped')
        self.assertFalse(self.skills.proactive.control.get_state().can_run)
        self.assertFalse(self.skills.proactive_service_requested.is_set())

    async def test_shutdown_closes_development_before_agent_pool(self):
        order = []
        manager = Mock()
        manager.close = AsyncMock(side_effect=lambda: order.append('development'))
        self.skills._evolution = manager
        self.skills._agent_orchestrator.close = AsyncMock(side_effect=lambda: order.append('agents'))
        await self.skills.close_agent_jobs()
        self.assertEqual(order, ['development', 'agents'])

    async def test_completion_notification_routes_to_development_status(self):
        voice = LiveVoice(None, skills=self.skills)
        notified = asyncio.Event()
        session = Mock()
        session.send_client_content = AsyncMock(side_effect=lambda **kwargs: notified.set())
        self.skills.agent_job_events.put_nowait(
            {'kind': 'evolution', 'id': 'dev-1', 'state': 'ready_for_review'})
        worker = asyncio.create_task(voice.monitor_agents(session))
        sender = asyncio.create_task(voice.send_notifications(session))
        try:
            await asyncio.wait_for(notified.wait(), 2)
            text = session.send_client_content.call_args.kwargs['turns'].parts[0].text
            self.assertIn('development_status', text)
            self.assertIn('untrusted', text)
        finally:
            worker.cancel()
            sender.cancel()
            await asyncio.gather(worker, sender, return_exceptions=True)


if __name__ == '__main__':
    unittest.main()
