from unittest.mock import AsyncMock
from types import SimpleNamespace
import sys

import pytest

from orchestration.hermes_bridge import HermesBridge, HermesBridgeError
from orchestration._hermes_gateway_worker import operate
try:
    from tests.test_orchestration.test_hermes_bridge import fake_gateway
except ImportError:
    from test_hermes_bridge import fake_gateway

from orchestration.tool_tiers import domain_for_tool, intent_domains
from skills.skills import DesktopSkills


@pytest.mark.asyncio
async def test_features_read_live_native_catalog_without_creating_session(monkeypatch):
    methods = []
    async def rpc(method, **kwargs):
        methods.append(method)
        if method == 'tools.list':
            return {'toolsets':[{'name':'kanban','enabled':True,'tools':['kanban_list']},
                                {'name':'cronjob','enabled':True}, {'name':'disabled','enabled':False}]}
        assert method == 'commands.catalog'
        return {'pairs':[['/kanban','Native board'],['/cron','Native scheduler']]}
    fake_gateway(monkeypatch, SimpleNamespace(rpc=rpc))
    result = await operate({'operation':'features','query':'board'})
    assert [x['name'] for x in result['features']] == ['kanban']
    assert methods == ['tools.list','commands.catalog']
    assert result['commands']['pairs'][0][0] == '/kanban'


@pytest.mark.asyncio
async def test_native_command_is_dispatched_without_a_model_or_replacement(monkeypatch):
    rpc = AsyncMock(return_value={'type':'exec','output':'No scheduled jobs.'})
    fake_gateway(monkeypatch, SimpleNamespace(rpc=rpc))
    result = await operate({'operation':'command','session_id':'mine','command':'cron','arguments':'list'})
    rpc.assert_awaited_once_with('command.dispatch',session_id='mine',name='cron',arg='list',_timeout=110)
    assert result['native_result']['output'] == 'No scheduled jobs.'
    assert not result['requires_agent']


@pytest.mark.asyncio
async def test_native_prompt_directive_is_not_claimed_as_executed(monkeypatch):
    rpc = AsyncMock(return_value={'type':'send','message':'Native skill prompt'})
    fake_gateway(monkeypatch, SimpleNamespace(rpc=rpc))
    result = await operate({'operation':'command','session_id':'mine','command':'plan','arguments':'Build a report'})
    assert result['requires_agent']
    assert rpc.await_count == 1


@pytest.mark.asyncio
async def test_bridge_command_uses_own_session_and_does_not_accept_shell_syntax(tmp_path):
    (tmp_path / '.git').mkdir()
    bridge = HermesBridge(python=sys.executable)
    bridge._request = AsyncMock(side_effect=[{'session_id':'owned'}, {'native_result':{}}, {'native_result':{}}])
    await bridge.command('/cron','list',workspace=tmp_path)
    await bridge.command('kanban','list',workspace=tmp_path)
    assert bridge._command_session == 'owned'
    assert bridge._request.await_count == 3
    with pytest.raises(HermesBridgeError):
        await bridge.command('cron; echo bad',workspace=tmp_path)
    assert bridge._request.await_count == 3


@pytest.mark.asyncio
async def test_voice_tools_and_domains_expose_native_features():
    skills = DesktopSkills()
    try:
        names={s['name'] for s in skills.declarations}
        assert {'get_hermes_features','run_hermes_command'} <= names
        assert domain_for_tool('run_hermes_command') == 'orchestration'
        assert 'orchestration' in intent_domains('Show my kanban board')
    finally:
        await skills.close_agent_jobs()
