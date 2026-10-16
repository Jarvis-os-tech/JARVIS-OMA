import asyncio
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

class ProactiveRuntimeTests(unittest.TestCase):
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
