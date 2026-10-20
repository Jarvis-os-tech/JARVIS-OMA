import asyncio
from datetime import datetime, timedelta, timezone
import tempfile
import unittest
from pathlib import Path
from proactive.runtime import ProactiveRuntime

class FakeOrchestrator:
    def __init__(self): self.workers={}; self.jobs={}; self.calls=[]
    def delegate(self, agent, prompt, workspace, timeout):
        self.calls.append((agent,prompt,workspace,timeout)); key=f'job-{len(self.calls)}'
        self.jobs[key]={'id':key,'state':'running'}
        return {'job': {'id': key}}
    async def cancel(self, job):
        self.workers.pop(job, None)
        self.jobs[job]['state'] = 'cancelled'
    def stop_admission(self): self.stopped = True
    def resume(self): self.stopped = False
    async def stop_all(self):
        self.stop_admission()
        for job in list(self.workers):
            await self.cancel(job)

class ProactiveRuntimeTests(unittest.TestCase):
    def test_focus_is_proactive_prioritized_and_durable(self):
        async def scenario(root):
            orchestrator = FakeOrchestrator()
            runtime = ProactiveRuntime(root, orchestrator)
            today = datetime(2026, 10, 18, tzinfo=timezone.utc)
            tasks = [{'title': 'Low task', 'priority': 'low'},
                     {'title': 'Critical task', 'priority': 'critical'},
                     {'title': 'Done', 'completed': True},
                     {'title': 'Backlog', 'status': 'backlog'}]
            self.assertEqual(len(runtime.observe_focus(tasks, root, now=today)), 1)
            result = await runtime.tick()
            suggestion = result['results'][0]
            self.assertEqual(suggestion['status'], 'suggested')
            self.assertEqual([item['title'] for item in suggestion['tasks']],
                             ['Critical task', 'Low task'])
            self.assertEqual(orchestrator.calls, [])
            await runtime.close()
            restarted = ProactiveRuntime(root, orchestrator)
            self.assertEqual(restarted.observe_focus(tasks, root, now=today), [])
            self.assertEqual(len(restarted.observe_focus(
                tasks, root, now=today + timedelta(days=1))), 1)
            await restarted.close()
        with tempfile.TemporaryDirectory() as root:
            asyncio.run(scenario(root))

    def test_focus_respects_controls_and_empty_lists(self):
        async def scenario(root):
            runtime = ProactiveRuntime(root, FakeOrchestrator())
            tasks = [{'title': 'Prepare report'}]
            self.assertEqual(runtime.observe_focus([], root), [])
            runtime.pause()
            self.assertEqual(runtime.observe_focus(tasks, root), [])
            runtime.resume()
            self.assertEqual(len(runtime.observe_focus(tasks, root)), 1)
            runtime.pause()
            self.assertEqual((await runtime.tick())['status'], 'paused')
            runtime.resume()
            self.assertEqual((await runtime.tick())['results'][0]['status'], 'suggested')
            await runtime.stop_all()
            self.assertEqual(runtime.observe_focus(tasks, root), [])
            await runtime.close()
        with tempfile.TemporaryDirectory() as root:
            asyncio.run(scenario(root))

    def test_queue_plan_delegate_and_persist_activity(self):
        with tempfile.TemporaryDirectory() as root:
            orchestrator=FakeOrchestrator(); runtime=ProactiveRuntime(Path(root), orchestrator)
            queued=runtime.enqueue('Implement the parser', root, authorized=True)
            result=asyncio.run(runtime.tick())
            self.assertEqual(result['results'][0]['status'], 'delegated')
            self.assertEqual(orchestrator.calls[0][0], 'codex')
            self.assertEqual(runtime.status()['pending_events'], 0)
            self.assertTrue(runtime.status()['recent_activity'])

    def test_pause_resume_and_stop(self):
        with tempfile.TemporaryDirectory() as root:
            runtime=ProactiveRuntime(root, FakeOrchestrator())
            self.assertEqual(runtime.pause()['status'], 'paused')
            self.assertEqual(asyncio.run(runtime.tick())['status'], 'paused')
            self.assertEqual(runtime.resume()['status'], 'active')
            self.assertEqual(asyncio.run(runtime.stop_all())['status'], 'stopped')

    def test_observes_todos_without_voice_assignment_and_deduplicates(self):
        with tempfile.TemporaryDirectory() as root:
            orchestrator=FakeOrchestrator(); runtime=ProactiveRuntime(root, orchestrator)
            tasks=[{'id':'t1','title':'Fix parser tests','description':'repair the repository',
                    'priority':'high','status':'ongoing','completed':False}]
            self.assertEqual(runtime.observe_todos(tasks, root), ['todo:t1'])
            self.assertEqual(runtime.observe_todos(tasks, root), [])
            result=asyncio.run(runtime.tick())
            self.assertEqual(result['results'][0]['status'], 'approval_required')
            self.assertEqual(orchestrator.calls, [])

if __name__ == '__main__': unittest.main()
