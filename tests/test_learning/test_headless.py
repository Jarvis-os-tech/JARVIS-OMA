"""Fresh-process proof that offline refinement never initializes audio hardware."""
import asyncio
import json
from pathlib import Path
import subprocess
import sys

import pytest

from core.tool_dispatch import run_skill_call
from skills import SkillError


def test_offline_refinement_runs_with_audio_imports_forbidden(tmp_path):
    pytest.importorskip('harness2')
    repository = Path(__file__).resolve().parents[2]
    script = '''
import asyncio
import importlib.abc
import json
import sys

class NoAudio(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == 'audio' or fullname.startswith('audio.') or fullname == 'sounddevice':
            raise RuntimeError('Headless refinement attempted audio import: ' + fullname)

sys.meta_path.insert(0, NoAudio())
from learning.refinement import run_refinement
from learning.research import fixture_trial
result = run_refinement(sys.argv[1], offline=True)
fixture = asyncio.run(fixture_trial(sys.argv[1]))
assert fixture['assessment']['passed'] and fixture['tool_responses'] == 1
assert not any(name == 'audio' or name.startswith('audio.') or name == 'sounddevice'
               for name in sys.modules)
print(json.dumps({'rollouts': result['ledger']['R'],
                  'stages': result['ledger']['P'],
                  'activated': result['activated'],
                  'improvement': result['comparison']['quality_improvement_established']}))
'''
    child = subprocess.run(
        [sys.executable, '-c', script, str(tmp_path)], cwd=repository,
        capture_output=True, text=True, timeout=30,
    )
    assert child.returncode == 0, child.stderr
    assert json.loads(child.stdout) == {
        'rollouts': 4, 'stages': 3, 'activated': False, 'improvement': False,
    }


@pytest.mark.asyncio
@pytest.mark.parametrize('finish', ['cancel', 'timeout'])
async def test_dispatch_cancels_child_without_waiting_for_resistant_cleanup(finish):
    started, cancelled, release = asyncio.Event(), asyncio.Event(), asyncio.Event()
    errors = []
    loop = asyncio.get_running_loop()
    previous_handler = loop.get_exception_handler()
    loop.set_exception_handler(lambda _loop, context: errors.append(context))

    class ResistantSkill:
        async def execute(self, name, arguments):
            self.task = asyncio.current_task()
            started.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                cancelled.set()
                await release.wait()
                raise RuntimeError('Late child failure must be observed')

    skills = ResistantSkill()
    dispatch = asyncio.create_task(run_skill_call(
        skills, 'corpus_read', {}, timeout=0.01 if finish == 'timeout' else 10))
    try:
        await started.wait()
        if finish == 'cancel':
            dispatch.cancel()
            with pytest.raises(asyncio.CancelledError):
                await asyncio.wait_for(dispatch, 1)
        else:
            with pytest.raises(SkillError, match='cancelled'):
                await asyncio.wait_for(dispatch, 1)
        await asyncio.wait_for(cancelled.wait(), 1)
        # The caller has already returned even though the child's cleanup awaits release.
        assert not skills.task.done()
        release.set()
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        assert skills.task.done()
        assert not errors
    finally:
        release.set()
        await asyncio.gather(dispatch, skills.task, return_exceptions=True)
        loop.set_exception_handler(previous_handler)
