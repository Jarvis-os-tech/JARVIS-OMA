import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from orchestration.groq_tool_router import GroqToolRouter, configured_groq_api_keys


def declaration(index):
    return {'name': f'tool_{index}', 'description': f'Operate item {index}',
            'parameters_json_schema': {'type': 'object', 'properties': {}}}


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
