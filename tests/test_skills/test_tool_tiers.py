"""Compact Live catalogs retain exact-schema access to all registered domains."""
import json
from unittest.mock import AsyncMock, patch

import pytest
from google.genai import types

from core.config import Config
from core.harness_config import live_config
from skills import DesktopSkills, SkillError
from orchestration.groq_tool_router import GroqToolRouter
from orchestration.tool_tiers import CORE_TOOLS, META_TOOLS, domain_for_tool


def test_voice_catalog_is_bounded_without_removing_registered_tools():
    skills = DesktopSkills()
    all_names = {item['name'] for item in skills.declarations}
    initial_names = {item['name'] for item in skills.live_declarations}
    assert len(initial_names) <= 35
    assert {'open_application', 'enter_standby', 'recall_memory', *META_TOOLS} <= initial_names
    assert 'github_get_issue' in all_names and 'github_get_issue' not in initial_names
    assert len(json.dumps(skills.live_declarations)) < len(json.dumps(skills.declarations)) * .3
    assert 'github_get_issue' not in skills.capability_context()
    assert 'On-demand domains:' in skills.capability_context()


def test_groq_live_session_does_not_expand_the_remote_catalog():
    skills = DesktopSkills()
    config = Config()
    config.agent.tool_router = 'groq'
    with patch('core.harness_config.configured_groq_api_keys', return_value=['test']):
        payload = live_config('Aoede', skills=skills, config=config)
    validated = types.LiveConnectConfig.model_validate(payload)
    names = {item.name for item in validated.tools[0].function_declarations}
    assert len(names) <= 36
    assert 'route_local_command' in names
    assert 'execute_domain_tool' in names
    assert 'gmail_search' not in names


@pytest.mark.asyncio
async def test_domain_discovery_returns_exact_schemas_without_executing_or_expanding_live_tier():
    skills = DesktopSkills()
    before = skills.live_declarations
    result = await skills.execute('discover_domain_tools', {'domain': 'github', 'query': 'issue'})
    assert result['tools']
    assert all(item['name'].startswith('github_') for item in result['tools'])
    assert all('parameters_json_schema' in item for item in result['tools'])
    assert 'github' in skills.active_domains
    assert skills.live_declarations == before


@pytest.mark.asyncio
async def test_domain_execution_uses_registered_adapter_and_its_schema():
    skills = DesktopSkills()
    with patch('connectors.github.dispatch', new=AsyncMock(return_value={'repositories': []})) as dispatch:
        result = await skills.execute('execute_domain_tool', {
            'domain': 'github', 'tool_name': 'github_list_repositories',
            'arguments_json': json.dumps({'max_results': 2}),
        })
    assert result == {'repositories': []}
    dispatch.assert_awaited_once_with('github_list_repositories', {'max_results': 2})


@pytest.mark.asyncio
@pytest.mark.parametrize('domain,name,arguments', [
    ('workspace', 'github_list_repositories', '{}'),
    ('github', 'github_list_repositories', '{"max_results": "two"}'),
    ('github', 'github_list_repositories', '{"max_results": 2, "shell": "arbitrary"}'),
    ('github', 'github_list_repositories', '[]'),
    ('github', 'github_list_repositories', 'not json'),
    ('core', 'execute_domain_tool', '{}'),
    ('core', 'discover_domain_tools', '{}'),
    ('github', '__import__', '{}'),
])
async def test_domain_routes_reject_cross_domain_invalid_or_recursive_requests(domain, name, arguments):
    skills = DesktopSkills()
    with patch('connectors.github.dispatch', new=AsyncMock()) as dispatch:
        with pytest.raises(SkillError):
            await skills.execute('execute_domain_tool', {
                'domain': domain, 'tool_name': name, 'arguments_json': arguments,
            })
    dispatch.assert_not_awaited()


@pytest.mark.asyncio
async def test_domain_routing_cannot_bypass_memory_disable_or_mute_policy():
    config = Config()
    config.memory.enabled = False
    skills = DesktopSkills(config=config)
    assert 'recall_memory' not in {item['name'] for item in skills.live_declarations}
    with pytest.raises(SkillError):
        await skills.execute('execute_domain_tool', {
            'domain': 'core', 'tool_name': 'recall_memory', 'arguments_json': '{}'})
    with patch.object(skills, '_adapter_enter_standby', new=AsyncMock(return_value={'status': 'standby'})) as standby:
        result = await skills.execute('execute_domain_tool', {
            'domain': 'core', 'tool_name': 'set_volume',
            'arguments_json': '{"action":"mute"}'})
    standby.assert_awaited_once()
    assert result['system_audio_changed'] is False


def test_groq_activates_requested_domains_and_resolves_known_collisions():
    skills = DesktopSkills()
    router = GroqToolRouter('test-key', skills.declarations)
    names = lambda command: {item['function']['name'] for item in router._tools_for(command)}
    assert names('mute yourself') == {'enter_standby'}
    meeting = names('create a calendar meeting tomorrow at 9')
    assert 'calendar_create_event' in meeting
    assert 'tasks_create_task' not in meeting
    github = names('read a GitHub issue in this repository')
    assert 'github_get_issue' in github
    assert not any(name.startswith('gmail_') for name in github)
    assert not META_TOOLS & github


def test_extracted_domains_are_real_method_owners_with_shared_error_identity():
    from skills.errors import SkillError as SharedError
    from skills.domains.workspace import WorkspaceDomain
    from skills.domains.github import GithubDomain
    from skills.domains.orchestration import OrchestrationDomain
    assert SkillError is SharedError
    assert DesktopSkills._adapter_google_gmail_search is WorkspaceDomain._adapter_google_gmail_search
    assert DesktopSkills._adapter_github_get_issue is GithubDomain._adapter_github_get_issue
    assert DesktopSkills._adapter_delegate_agent is OrchestrationDomain._adapter_delegate_agent
    assert domain_for_tool('start_harness_check') == 'learning'
