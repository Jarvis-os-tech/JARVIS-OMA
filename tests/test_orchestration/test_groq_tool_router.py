import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from orchestration.groq_tool_router import (
    GroqToolRouter, configured_groq_api_keys, ROUTER_DECLARATION,
    partition_declarations_for_router, SYSTEM_TOOL_NAMES)


def declaration(index):
    return {'name': f'tool_{index}', 'description': f'Operate item {index}',
            'parameters_json_schema': {'type': 'object', 'properties': {}}}


def test_partition_declarations_for_router():
    decls = [
        {'name': 'open_application', 'description': 'Open an app'},
        {'name': 'type_text', 'description': 'Type text'},
        {'name': 'switch_workspace', 'description': 'Switch workspace'},
        {'name': 'set_volume', 'description': 'Set volume'},
        {'name': 'read_file', 'description': 'Read a local file'},
        {'name': 'create_todo', 'description': 'Create a native todo'},
        {'name': 'internet_search', 'description': 'Search the web'},
        {'name': 'gmail_search', 'description': 'Search emails'},
        {'name': 'calendar_list_events', 'description': 'List calendar events'},
        {'name': 'github_list_repositories', 'description': 'List repos'},
    ]
    local_decls, remote_decls = partition_declarations_for_router(decls)
    local_names = {d['name'] for d in local_decls}
    remote_names = {d['name'] for d in remote_decls}

    assert local_names == {'open_application', 'type_text', 'switch_workspace', 'set_volume', 'read_file', 'create_todo'}
    assert remote_names == {'internet_search', 'gmail_search', 'calendar_list_events', 'github_list_repositories'}
    assert ROUTER_DECLARATION['name'] == 'route_local_command'


def test_router_bounds_large_tool_catalog():
    router = GroqToolRouter('secret', [declaration(i) for i in range(185)])
    assert len(router._tools_for('operate item 184')) == 40
    assert any(tool['function']['name'] == 'tool_184'
               for tool in router._tools_for('operate item 184'))


def test_configured_keys_support_numbered_variables_and_deduplicate():
    assert configured_groq_api_keys({
        'GROQ_API_KEY_1': 'first', 'GROQ_API_KEY_2': 'second',
        'GROQ_API_KEY': 'first',
    }) == ['first', 'second']


@pytest.mark.asyncio
async def test_router_parses_function_arguments():
    response = AsyncMock()
    response.raise_for_status = lambda: None
    response.json = lambda: {'choices': [{'message': {'tool_calls': [{
        'function': {'name': 'tool_1', 'arguments': json.dumps({'value': 3})}
    }]}}]}
    client = AsyncMock()
    client.__aenter__.return_value = client
    client.post.return_value = response
    with patch('orchestration.groq_tool_router.httpx.AsyncClient', return_value=client):
        calls = await GroqToolRouter('secret', [declaration(1)]).route('do it')
    assert calls == [{'name': 'tool_1', 'arguments': {'value': 3}}]


@pytest.mark.asyncio
async def test_router_rotates_to_second_key_after_rate_limit():
    limited = httpx.Response(
        429, headers={'Retry-After': '30'},
        request=httpx.Request('POST', 'https://api.groq.com/openai/v1/chat/completions'))
    success = httpx.Response(
        200, json={'choices': [{'message': {'tool_calls': [{
            'function': {'name': 'tool_1', 'arguments': '{}'}
        }]}}]},
        request=httpx.Request('POST', 'https://api.groq.com/openai/v1/chat/completions'))
    client = AsyncMock()
    client.__aenter__.return_value = client
    client.post.side_effect = [limited, success]

    with patch('orchestration.groq_tool_router.httpx.AsyncClient', return_value=client):
        calls = await GroqToolRouter(['first-key', 'second-key'], [declaration(1)]).route('do it')

    assert calls == [{'name': 'tool_1', 'arguments': {}}]
    assert [call.kwargs['headers']['Authorization'] for call in client.post.await_args_list] == [
        'Bearer first-key', 'Bearer second-key']


@pytest.mark.asyncio
async def test_router_round_robins_successful_requests_across_keys():
    def success():
        return httpx.Response(
            200, json={'choices': [{'message': {'tool_calls': [{
                'function': {'name': 'tool_1', 'arguments': '{}'}
            }]}}]},
            request=httpx.Request('POST', 'https://api.groq.com/openai/v1/chat/completions'))

    client = AsyncMock()
    client.__aenter__.return_value = client
    client.post.side_effect = [success(), success()]
    router = GroqToolRouter(['first-key', 'second-key'], [declaration(1)])

    with patch('orchestration.groq_tool_router.httpx.AsyncClient', return_value=client):
        await router.route('first command')
        await router.route('second command')

    assert [call.kwargs['headers']['Authorization'] for call in client.post.await_args_list] == [
        'Bearer first-key', 'Bearer second-key']


@pytest.mark.asyncio
@pytest.mark.parametrize('name,arguments,reason', [
    ('undeclared_tool', '{"value":3}', 'outside the selected registered domain'),
    ('exact_tool', '{"value":true}', 'outside the selected tool schema'),
    ('exact_tool', '{"value":3,"shell":"unapproved"}', 'outside the selected tool schema'),
])
async def test_router_rejects_unselected_or_schema_invalid_calls(name, arguments, reason):
    declaration = {
        'name': 'exact_tool', 'description': 'Operate a value',
        'parameters_json_schema': {'type': 'object', 'properties': {'value': {'type': 'integer'}},
                                   'required': ['value'], 'additionalProperties': False},
    }
    response = httpx.Response(200, json={'choices': [{'message': {'tool_calls': [
        {'function': {'name': name, 'arguments': arguments}}]}}]},
        request=httpx.Request('POST', 'https://api.groq.com/openai/v1/chat/completions'))
    client = AsyncMock()
    client.__aenter__.return_value = client
    client.post.return_value = response
    with patch('orchestration.groq_tool_router.httpx.AsyncClient', return_value=client):
        with pytest.raises(ValueError, match=reason):
            await GroqToolRouter('test-key', [declaration]).route('operate a value')
