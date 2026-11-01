import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from orchestration.agent_orchestrator import AgentOrchestrator
from orchestration.mcp_server import OrchestratorMCP, TOOLS
from jarvis_control.skills import UnifiedSkills
from orchestration.task_agents import TaskAgents
from skills.skills import DesktopSkills
from jarvis_voice.daemon import build_instruction


def worker():
    import sys
    return AgentOrchestrator(executables={'codex': sys.executable, 'hermes': sys.executable},
        command_builder=lambda *args: [sys.executable, '-c', 'from pathlib import Path; Path("answer.txt").write_text("42"); print("answer.txt")'])


@pytest.mark.asyncio
async def test_mcp_idempotency_results_and_restart(tmp_path):
    bridge = OrchestratorMCP(tmp_path / 'state', orchestrator=worker())
    try:
        tools = await bridge.handle({'jsonrpc':'2.0','id':1,'method':'tools/list'})
        assert any(t['name'] == 'jarvis_delegate' for t in tools['result']['tools'])
        assert not any(x['name'] == 'hermes' for x in (await bridge.call('jarvis_capabilities', {}))['workers'])
        first = await bridge.call('jarvis_delegate', {'agent':'codex','prompt':'Write answer.txt','request_key':'one'})
        repeat = await bridge.call('jarvis_delegate', {'agent':'codex','prompt':'Write answer.txt','request_key':'one'})
        assert repeat['id'] == first['id']
        with pytest.raises(ValueError, match='different task'):
            await bridge.call('jarvis_delegate', {'agent':'codex','prompt':'Other task','request_key':'one'})
        await asyncio.gather(*list(bridge.watchers))
        result = await bridge.call('jarvis_job_status', {'job_id':first['id']})
        assert result['state'] == 'completed'
        assert result['verification']['status'] == 'passed'
        assert result['verified'] is False
        assert Path(result['workspace'], 'answer.txt').read_text() == '42'
        with pytest.raises(ValueError, match='invalid arguments'):
            await bridge.call('jarvis_delegate', {'agent':'hermes','prompt':'Loop','request_key':'bad'})
    finally:
        await bridge.close()
    recovered = OrchestratorMCP(tmp_path / 'state', orchestrator=worker())
    try:
        same = await recovered.call('jarvis_delegate', {'agent':'codex','prompt':'Write answer.txt','request_key':'one'})
        assert same['id'] == first['id'] and same['state'] == 'completed'
        assert not recovered.orchestrator.workers
    finally:
        await recovered.close()


@pytest.mark.asyncio
async def test_mcp_refuses_foreign_workspace_and_competing_owner(tmp_path):
    bridge = OrchestratorMCP(tmp_path / 'state', orchestrator=worker())
    try:
        with pytest.raises(ValueError, match='Another Jarvis'):
            OrchestratorMCP(tmp_path / 'state', orchestrator=worker())
        result = await bridge.call('jarvis_delegate', {'agent':'codex','prompt':'Write a file','request_key':'outside','workspace':str(tmp_path)})
        assert result['state'] == 'failed'
        assert not bridge.orchestrator.workers
        invalid = await bridge.handle({'id':2,'method':'tools/call','params':{'name':'jarvis_job_status','arguments':{'job_id':'foreign'}}})
        assert invalid['result']['isError']
    finally:
        await bridge.close()


@pytest.mark.asyncio
async def test_goal_is_registered_routes_to_hermes_and_notice_is_acknowledged(tmp_path):
    skills = DesktopSkills()
    bridge = SimpleNamespace(capabilities=AsyncMock(return_value={'available':True}),
                             close=AsyncMock())
    agents = TaskAgents(tmp_path, bridge=bridge)
    skills._task_agents = agents
    unified = UnifiedSkills(desktop_skills=skills)
    try:
        assert 'start_hermes_goal' in {s['name'] for s in skills.declarations}
        instruction = build_instruction([{'function_declarations':unified.declarations}])
        assert 'Hermes is the main orchestrator' in instruction
        assert 'Jarvis is also a primary orchestrator' in instruction
        start = agents.start
        agents.start = lambda *a, **kw: {'goal':a[0], 'role':kw['role'], 'status':'queued'}
        result = json.loads(await unified.execute('start_hermes_goal', {'goal':'Plan this project'}))
        assert result['role'] == 'main orchestrator'
        agents.start = start
        agents.jobs['task-123456789abc'] = {'id':'task-123456789abc','kind':'task_agent', 'state':'completed','summary':'Response received; effects unverified.'}
        events = await unified.background_events()
        assert events[0]['id'] == 'hermes:task-123456789abc'
        await unified.acknowledge_event(events[0]['id'])
        assert not await unified.background_events()
    finally:
        await unified.close_agent_jobs()


def test_service_discovers_installed_agents_without_running_wrappers(tmp_path, monkeypatch):
    from orchestration.executables import installed_executables
    binary = tmp_path / '.local/share/mise/installs/codex/latest/bin/codex'
    binary.parent.mkdir(parents=True)
    binary.write_text('#!/bin/sh\nexit 0\n')
    binary.chmod(0o700)
    monkeypatch.setenv('PATH', '/nonexistent')
    assert installed_executables(tmp_path)['codex'] == str(binary)
    assert installed_executables(tmp_path)['gemini'] is None
