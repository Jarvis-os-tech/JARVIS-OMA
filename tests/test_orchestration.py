"""Comprehensive verification tests for orchestration modules.

Tests:
1. Tool tiers partitioning (CORE_TOOLS, META_TOOLS, DOMAINS, META_SPECS, domain_for_tool, routed_arguments_match, intent_domains).
2. Agent schemas (list_system_agents, delegate_agent, delegate_team, start_agent_goal, check_agent_team).
3. AgentOrchestrator coordination (discovery, single delegation, team lifecycle, workspace locking, cancellation).
4. DesktopSkills orchestration dispatch.
5. EvolutionManager initialization and sandbox verification.
"""
from __future__ import annotations

import asyncio
import copy
import json
from pathlib import Path
import tempfile
import pytest

from orchestration import tool_tiers
from orchestration.agent_orchestrator import (
    AGENTS,
    AgentOrchestrator,
    OrchestrationError,
    command_for,
    clear_task_brief,
    validate_model,
)
from orchestration.personas import PERSONAS, software_assignments
from orchestration.model_policy import apply_model_policy
from orchestration.evolution import EvolutionManager, verification_command
from skills.skills import DesktopSkills
from skills.errors import SkillError


# ==============================================================================
# 1. TOOL TIERS PARTITIONING TESTS
# ==============================================================================

def test_tool_tiers_constants():
    """Verify tool tiers constants and sets."""
    assert len(tool_tiers.CORE_TOOLS) == 33
    assert "get_assistant_status" in tool_tiers.CORE_TOOLS
    assert "open_application" in tool_tiers.CORE_TOOLS
    assert "start_task" in tool_tiers.CORE_TOOLS

    assert tool_tiers.META_TOOLS == frozenset({'discover_domain_tools', 'execute_domain_tool'})

    expected_domains = (
        'core', 'desktop', 'filesystem', 'memory', 'workspace', 'github',
        'gui', 'cli_anything', 'orchestration', 'learning', 'phone', 'vision', 'composio'
    )
    assert tool_tiers.DOMAINS == expected_domains

    assert len(tool_tiers.META_SPECS) == 2
    spec_names = {s['name'] for s in tool_tiers.META_SPECS}
    assert spec_names == {'discover_domain_tools', 'execute_domain_tool'}


def test_domain_for_tool_mappings():
    """Test domain resolution across all tool categories."""
    assert tool_tiers.domain_for_tool('get_assistant_status') == 'core'
    assert tool_tiers.domain_for_tool('discover_domain_tools') == 'core'
    assert tool_tiers.domain_for_tool('execute_domain_tool') == 'core'

    assert tool_tiers.domain_for_tool('gmail_list_threads') == 'workspace'
    assert tool_tiers.domain_for_tool('calendar_create_event') == 'workspace'
    assert tool_tiers.domain_for_tool('tasks_list') == 'workspace'
    assert tool_tiers.domain_for_tool('drive_search') == 'workspace'
    assert tool_tiers.domain_for_tool('docs_read') == 'workspace'
    assert tool_tiers.domain_for_tool('sheets_update') == 'workspace'
    assert tool_tiers.domain_for_tool('google_login') == 'workspace'

    assert tool_tiers.domain_for_tool('github_create_issue') == 'github'
    assert tool_tiers.domain_for_tool('gui_click_button') == 'gui'
    assert tool_tiers.domain_for_tool('cli_hub_search') == 'cli_anything'
    assert tool_tiers.domain_for_tool('phone_send_sms') == 'phone'

    assert tool_tiers.domain_for_tool('start_agent_goal') == 'orchestration'
    assert tool_tiers.domain_for_tool('list_system_agents') == 'orchestration'
    assert tool_tiers.domain_for_tool('delegate_agent') == 'orchestration'
    assert tool_tiers.domain_for_tool('delegate_team') == 'orchestration'
    assert tool_tiers.domain_for_tool('check_agent_team') == 'orchestration'

    assert tool_tiers.domain_for_tool('write_file') == 'filesystem'
    assert tool_tiers.domain_for_tool('edit_file') == 'filesystem'
    assert tool_tiers.domain_for_tool('sync_memory_vault') == 'memory'
    assert tool_tiers.domain_for_tool('capture_camera_frame') == 'vision'
    assert tool_tiers.domain_for_tool('unknown_custom_tool') == 'desktop'


def test_intent_domains_parsing():
    """Verify natural language hints extraction."""
    assert 'workspace' in tool_tiers.intent_domains("Check my calendar for tomorrow")
    assert 'github' in tool_tiers.intent_domains("Review open pull requests on github")
    assert 'orchestration' in tool_tiers.intent_domains("Delegate task to claude agent")
    assert 'desktop' in tool_tiers.intent_domains("Turn up the volume")
    assert 'filesystem' in tool_tiers.intent_domains("Copy the file to another folder")


def test_routed_arguments_match_validation():
    """Verify strict JSON-Schema matching for meta tools."""
    discover_schema = tool_tiers.META_SPECS[0]['parameters_json_schema']

    # Valid
    assert tool_tiers.routed_arguments_match({'domain': 'orchestration'}, discover_schema)
    assert tool_tiers.routed_arguments_match({'domain': 'filesystem', 'query': 'read', 'limit': 10}, discover_schema)

    # Invalid domain
    assert not tool_tiers.routed_arguments_match({'domain': 'invalid'}, discover_schema)
    # Missing required 'domain'
    assert not tool_tiers.routed_arguments_match({'query': 'read'}, discover_schema)
    # Exceeding limit range (max 20)
    assert not tool_tiers.routed_arguments_match({'domain': 'core', 'limit': 50}, discover_schema)


# ==============================================================================
# 2. SCHEMA AND AGENT DEFINITIONS TESTS
# ==============================================================================

@pytest.mark.asyncio
async def test_agent_manifest_schemas():
    """Verify list_system_agents and delegate_agent schemas against DesktopSkills."""
    skills = DesktopSkills()
    decl_map = {d['name']: d for d in skills.declarations}

    # list_system_agents
    assert 'list_system_agents' in decl_map
    lsa_schema = decl_map['list_system_agents']['parameters_json_schema']
    assert lsa_schema['type'] == 'object'
    assert lsa_schema['required'] == []
    assert lsa_schema['additionalProperties'] is False

    # delegate_agent
    assert 'delegate_agent' in decl_map
    da_schema = decl_map['delegate_agent']['parameters_json_schema']
    assert da_schema['type'] == 'object'
    assert set(da_schema['required']) == {'agent', 'prompt', 'workspace'}
    for agent in AGENTS:
        assert agent in da_schema['properties']['agent']['enum']

    # Strict rejection of invalid arguments
    with pytest.raises(SkillError, match="invalid arguments for list_system_agents"):
        await skills.execute('list_system_agents', {'unexpected': True})

    with pytest.raises(SkillError, match="invalid arguments for delegate_agent"):
        await skills.execute('delegate_agent', {'agent': 'fake_agent', 'prompt': 'test', 'workspace': '/tmp'})


def test_agent_command_construction():
    """Test command line builder for all system agents."""
    prompt = "Fix issue #42 in database"
    for agent in AGENTS:
        cmd = command_for(agent, f"/bin/{agent}", prompt)
        assert cmd[0] == f"/bin/{agent}"
        assert any("Fix issue #42 in database" in arg for arg in cmd)

    # Test model flag injection
    claude_cmd = command_for('claude', '/bin/claude', prompt, model='sonnet')
    assert claude_cmd[1:3] == ['--model', 'sonnet']

    codex_cmd = command_for('codex', '/bin/codex', prompt, model='gpt-5')
    assert codex_cmd[2:4] == ['--model', 'gpt-5']


# ==============================================================================
# 3. AGENT ORCHESTRATOR & TEAM LIFECYCLE TESTS
# ==============================================================================

def test_agent_orchestrator_discovery():
    """Verify discovery reports all 8 agents and personas."""
    orch = AgentOrchestrator()
    disco = orch.discover()
    assert disco['status'] == 'success'
    discovered_names = {a['name'] for a in disco['agents']}
    assert discovered_names == set(AGENTS)
    for agent_entry in disco['agents']:
        assert 'available' in agent_entry
        assert 'role' in agent_entry
        assert agent_entry['role'] == PERSONAS[agent_entry['name']]['role']


@pytest.mark.asyncio
async def test_team_lifecycle_execution(tmp_path):
    """Test full sequential team delegation, status check, and completion."""
    def mock_builder(agent, executable, prompt, model=None):
        return ["python3", "-c", f"import sys; print('Output from {agent}'); sys.exit(0)"]

    orch = AgentOrchestrator(
        executables={'hermes': '/bin/true', 'claude': '/bin/true', 'opencode': '/bin/true'},
        command_builder=mock_builder
    )

    team_res = orch.delegate_team(
        goal="Test Autonomous Feature Goal",
        assignments=[
            {'agent': 'hermes', 'prompt': 'Step 1: Plan architecture'},
            {'agent': 'claude', 'prompt': 'Step 2: Implement code'},
            {'agent': 'opencode', 'prompt': 'Step 3: Run independent QA tests'},
        ],
        workspace=str(tmp_path),
        timeout_seconds=60
    )
    team_id = team_res['team']['id']
    assert team_res['status'] == 'success'
    assert team_res['team']['state'] in ('queued', 'running')

    # Status check while queued/running
    status_mid = orch.team_status(team_id)
    assert status_mid['team']['id'] == team_id

    # Wait for completion
    worker = orch.team_workers.get(team_id)
    if worker:
        await worker

    status_final = orch.team_status(team_id)
    assert status_final['team']['state'] == 'completed'
    assert len(status_final['team']['jobs']) == 3

    # Verify chained execution output
    for jid in status_final['team']['jobs']:
        jstat = orch.status(jid)
        assert jstat['job']['state'] == 'completed'
        assert f"Output from {jstat['job']['agent']}" in jstat['job']['output']

    await orch.close()


@pytest.mark.asyncio
async def test_workspace_reservation_conflict(tmp_path):
    """Verify that multiple teams/jobs cannot overlap the same workspace directory."""
    orch = AgentOrchestrator(
        executables={'hermes': '/bin/true', 'claude': '/bin/true'},
        command_builder=lambda a, e, p, model=None: ["python3", "-c", "import time; time.sleep(10)"]
    )

    job1 = orch.delegate('hermes', 'Task 1', str(tmp_path), timeout_seconds=30)
    assert job1['status'] == 'success'

    # Attempting to delegate second job in same workspace must fail
    with pytest.raises(OrchestrationError, match="workspace is reserved"):
        orch.delegate('claude', 'Task 2', str(tmp_path), timeout_seconds=30)

    # Subdirectory conflict must also fail
    subdir = tmp_path / "subdir"
    subdir.mkdir()
    with pytest.raises(OrchestrationError, match="workspace is reserved"):
        orch.delegate('claude', 'Task 2 in sub', str(subdir), timeout_seconds=30)

    await orch.stop_all()
    await orch.close()


@pytest.mark.asyncio
async def test_team_cancellation(tmp_path):
    """Verify team cancellation halts active jobs and updates state."""
    orch = AgentOrchestrator(
        executables={'hermes': '/bin/true', 'claude': '/bin/true'},
        command_builder=lambda a, e, p, model=None: ["python3", "-c", "import time; time.sleep(30)"]
    )

    team_res = orch.delegate_team(
        goal="Cancelled Goal",
        assignments=[{'agent': 'hermes', 'prompt': 'Long task'}],
        workspace=str(tmp_path),
        timeout_seconds=60
    )
    team_id = team_res['team']['id']
    cancel_res = await orch.cancel_team(team_id)
    assert cancel_res['team']['state'] == 'cancelled'

    await orch.close()


# ==============================================================================
# 4. DESKTOPSKILLS ORCHESTRATION DISPATCH TESTS
# ==============================================================================

@pytest.mark.asyncio
async def test_desktop_skills_list_system_agents():
    """Verify DesktopSkills executes list_system_agents tool."""
    desktop = DesktopSkills()
    res = await desktop.execute('list_system_agents', {})
    assert res['status'] == 'success'
    assert len(res['agents']) == 8
    await desktop.close_agent_jobs()


@pytest.mark.asyncio
async def test_desktop_skills_start_agent_goal_dispatch(tmp_path):
    """Verify DesktopSkills.execute('start_agent_goal', ...) dispatches 4-stage pipeline."""
    desktop = DesktopSkills()

    dispatched = []
    def mock_delegate_team(goal, assignments, workspace, timeout_seconds=900):
        dispatched.append({
            'goal': goal,
            'assignments': assignments,
            'workspace': workspace,
            'timeout': timeout_seconds,
        })
        return {
            'status': 'success',
            'summary': 'Team queued.',
            'next_actions': ['check_agent_team'],
            'artifacts': ['team-goal-mock', workspace],
            'team': {'id': 'team-goal-mock', 'state': 'queued', 'assignments': assignments}
        }

    desktop._agent_orchestrator.delegate_team = mock_delegate_team

    result = await desktop.execute('start_agent_goal', {
        'goal': 'Implement autonomous user preference cache',
        'workspace': str(tmp_path),
        'cost_profile': 'configured'
    })

    assert result['status'] == 'success'
    assert result['team']['id'] == 'team-goal-mock'
    assert result['cost_policy']['profile'] == 'configured'
    assert len(dispatched) == 1

    assignments = dispatched[0]['assignments']
    assert len(assignments) == 4
    # hermes -> developer (claude) -> opencode -> claude
    assert assignments[0]['agent'] == 'hermes'
    assert assignments[1]['agent'] == 'claude'
    assert assignments[2]['agent'] == 'opencode'
    assert assignments[3]['agent'] == 'claude'

    await desktop.close_agent_jobs()


@pytest.mark.asyncio
async def test_desktop_skills_delegate_team_and_status(tmp_path):
    """Verify DesktopSkills executes delegate_team, check_agent_team, and cancel_agent_team."""
    desktop = DesktopSkills()

    # delegate_team with visible=False to run in background mode
    res = await desktop.execute('delegate_team', {
        'goal': 'Test team execution',
        'workspace': str(tmp_path),
        'assignments': [
            {'agent': 'opencode', 'prompt': 'Run health check', 'visible': False}
        ],
        'timeout_seconds': 60
    })
    assert res['status'] == 'success'
    team_id = res['team']['id']

    # check_agent_team
    st = await desktop.execute('check_agent_team', {'team_id': team_id})
    assert st['status'] == 'success'
    assert st['team']['id'] == team_id

    # cancel_agent_team
    canceled = await desktop.execute('cancel_agent_team', {'team_id': team_id})
    assert canceled['status'] == 'success'
    assert canceled['team']['state'] == 'cancelled'

    await desktop.close_agent_jobs()


# ==============================================================================
# 5. EVOLUTION & SELF-HEALING TESTS
# ==============================================================================

def test_evolution_manager_initialization_and_sandbox(tmp_path):
    """Verify EvolutionManager initialization, job persistence, and bwrap sandbox command."""
    orch = AgentOrchestrator()
    mgr = EvolutionManager(orch, state_dir=str(tmp_path / "state"))
    assert mgr.state_dir.exists()
    jobs = mgr.list_jobs()
    assert jobs['status'] == 'success'
    assert len(jobs['jobs']) == 0

    workspace = tmp_path / "repo"
    workspace.mkdir()
    cmd = verification_command(workspace)
    assert cmd[0].endswith("bwrap")
    assert "--unshare-all" in cmd
    assert "--clearenv" in cmd
