"""Model selections reach the actual supervised subprocess command."""
import asyncio
import sys
from unittest.mock import AsyncMock, patch

import pytest

from orchestration.agent_orchestrator import AgentOrchestrator, OrchestrationError, clear_task_brief, command_for
from orchestration.desktop_execution import DesktopAgentOrchestrator, interactive_command


@pytest.mark.parametrize('agent', ['codex', 'claude', 'hermes', 'opencode'])
def test_batch_model_option_preserves_prompt(agent):
    command = command_for(agent, agent, 'test assignment', model='provider/small')
    assert command[command.index('--model') + 1] == 'provider/small'
    assert command[-1].endswith('test assignment')
    if agent == 'hermes':
        assert command[command.index('-z') + 1] == command[-1]


def test_json_envelope_is_rendered_as_clear_english_brief():
    prompt = '{"task":"Fix the listener","context":"The service must remain responsive.","deliverables":["Add a regression test"],"constraints":["Do not touch audio files"]}'
    brief = clear_task_brief(prompt)
    assert brief == (
        "Task\nFix the listener\n\nContext\nThe service must remain responsive.\n\n"
        "Expected result\n- Add a regression test\n\nConstraints\n- Do not touch audio files"
    )
    command = command_for('claude', 'claude', prompt)
    message = command[-1]
    assert 'Task\nFix the listener' in message
    assert '{"task"' not in message


@pytest.mark.parametrize('agent', ['codex', 'claude', 'opencode', 'gemini', 'omp', 'pi'])
def test_worker_prompt_uses_human_readable_output(agent):
    command = command_for(agent, agent, 'Explain the change')
    assert not any('json' in str(value).lower() or 'stream-' in str(value).lower() for value in command[:-1])


@pytest.mark.parametrize('model', ['', ' ', '--flag', 'a\nb', 123])
def test_invalid_model_rejected(model):
    with pytest.raises(OrchestrationError):
        command_for('codex', 'codex', 'task', model=model)
    with pytest.raises(OrchestrationError):
        interactive_command('codex', 'codex', model=model)


def test_legacy_custom_builder_still_runs(tmp_path):
    async def run():
        calls = []
        def builder(agent, executable, prompt):
            calls.append((agent, executable, prompt))
            return [sys.executable, '-c', 'print("done")']
        runner = AgentOrchestrator({'codex': sys.executable}, command_builder=builder)
        result = runner.delegate('codex', 'task', str(tmp_path), model='small')
        job_id = result['job']['id']
        await runner.workers[job_id]
        assert calls == [('codex', sys.executable, 'task')]
        assert runner.jobs[job_id]['state'] == 'completed'
    asyncio.run(run())


@pytest.mark.parametrize('runner_type', [AgentOrchestrator, DesktopAgentOrchestrator])
def test_background_team_model_reaches_subprocess(tmp_path, runner_type):
    async def run():
        runner = runner_type({'codex': sys.executable})
        assignment = {'agent': 'codex', 'model': 'small', 'task_type': 'coding', 'visible': False}
        fake = AsyncMock()
        fake.pid = 123456789
        fake.returncode = 0
        fake.stdout.read.side_effect = [b'', b'']
        fake.stderr.read.side_effect = [b'', b'']
        with patch('asyncio.create_subprocess_exec', AsyncMock(return_value=fake)) as launch:
            result = runner._delegate_team_assignment(assignment, 'task', str(tmp_path), 10)
            await runner.workers[result['job']['id']]
            command = launch.call_args.args
            assert command[command.index('--model') + 1] == 'small'
            assert runner.jobs[result['job']['id']]['model'] == 'small'
    asyncio.run(run())
