import asyncio
import sys
import tempfile
import unittest

from orchestration.agent_orchestrator import AgentOrchestrator
from orchestration.personas import software_assignments


class AutonomousGoalsTests(unittest.IsolatedAsyncioTestCase):
    def runner(self, code):
        runner = AgentOrchestrator(
            {name: sys.executable for name in ('hermes', 'codex', 'opencode', 'claude')},
            lambda agent, executable, prompt: [executable, '-c', code, agent, prompt])
        self.addAsyncCleanup(runner.close)
        return runner

    async def test_role_pipeline_handoff_and_background_responsiveness(self):
        runner = self.runner("import sys,time; time.sleep(.05); print(sys.argv[1] + ' evidence')")
        with tempfile.TemporaryDirectory() as workspace:
            result = runner.delegate_team('Build feature', software_assignments(runner.executables), workspace)
            key = result['team']['id']
            self.assertEqual(result['team']['state'], 'queued')
            ticks = 0
            while key in runner.team_workers:
                ticks += 1
                await asyncio.sleep(.01)
            team = runner.team_status(key)['team']
            self.assertEqual(team['state'], 'completed')
            self.assertEqual([runner.jobs[j]['agent'] for j in team['jobs']],
                             ['hermes', 'claude', 'opencode', 'claude'])
            self.assertGreater(ticks, 4)
            notices = []
            while not runner.events.empty():
                notices.append(runner.events.get_nowait())
            self.assertTrue(any(e.get('kind') == 'team' and e['id'] == key for e in notices))

    async def test_failure_does_not_launch_later_stages(self):
        runner = self.runner("import sys; sys.exit(2)")
        with tempfile.TemporaryDirectory() as workspace:
            key = runner.delegate_team('Build', software_assignments(runner.executables), workspace)['team']['id']
            await runner.team_workers[key]
            self.assertEqual(runner.teams[key]['state'], 'failed')
            self.assertEqual(len(runner.teams[key]['jobs']), 1)

    async def test_cancellation_prevents_followup_launch(self):
        runner = self.runner("import time; time.sleep(30)")
        with tempfile.TemporaryDirectory() as workspace:
            key = runner.delegate_team('Build', software_assignments(runner.executables), workspace)['team']['id']
            while not runner.teams[key]['jobs']:
                await asyncio.sleep(.01)
            await runner.cancel_team(key)
            self.assertEqual(runner.teams[key]['state'], 'cancelled')
            self.assertEqual(len(runner.teams[key]['jobs']), 1)
            self.assertFalse(runner.processes)

    def test_missing_core_agent_is_explicit(self):
        with self.assertRaisesRegex(ValueError, 'hermes'):
            software_assignments({'codex': '/bin/codex'})
