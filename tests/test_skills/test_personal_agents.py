"""Voice adapters retain queued semantics and forward only declared task inputs."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from skills.skills import DesktopSkills, SkillError


@pytest.mark.asyncio
async def test_personal_agent_voice_adapters_keep_job_identity_and_lifecycle():
    skills = DesktopSkills(exclude_unavailable=False)
    manager = SimpleNamespace(
        start=Mock(return_value={'id': 'helper-1', 'status': 'queued'}),
        status=Mock(return_value={'id': 'helper-1', 'status': 'running'}),
        list=Mock(return_value={'jobs': []}),
        capabilities=AsyncMock(return_value={'status': 'success'}),
        followup=Mock(return_value={'id': 'helper-2', 'status': 'queued'}),
        cancel=AsyncMock(return_value={'status': 'cancel_requested'}), close=AsyncMock())
    skills._task_agents = manager
    try:
        assert (await skills.execute('create_task_agent', {
            'task': 'Draft a packing list', 'role': 'travel planner'}))['status'] == 'queued'
        manager.start.assert_called_once_with('Draft a packing list', role='travel planner',
                                              context='', timeout_seconds=300)
        assert (await skills.execute('task_agent_status', {'job_id': 'helper-1'}))['status'] == 'running'
        await skills.execute('followup_task_agent', {'job_id': 'helper-1', 'message': 'Make it shorter'})
        manager.followup.assert_called_once_with('helper-1', 'Make it shorter')
        await skills.execute('cancel_task_agent', {'job_id': 'helper-1'})
        manager.cancel.assert_awaited_once_with('helper-1')
        assert (await skills.execute('get_hermes_status', {}))['status'] == 'success'
        with pytest.raises(SkillError):
            await skills.execute('create_task_agent', {'task': 'hello', 'executable': 'evil'})
    finally:
        await skills.close_agent_jobs()
    manager.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_refinement_voice_tool_cannot_bypass_learning_requirement():
    skills = DesktopSkills(exclude_unavailable=False)
    try:
        with pytest.raises(SkillError, match='Initialize'):
            await skills.execute('start_harness_refinement', {'feedback_ids': ['observation']})
    finally:
        await skills.close_agent_jobs()
