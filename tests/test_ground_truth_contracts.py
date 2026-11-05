import json
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, Mock

import pytest

from jarvis_control.outcomes import classify_result
from jarvis_control.tools import Executor
from jarvis_control.config import Config
from skills import ground_truth
from connectors import composio
from skills.skills import DesktopSkills
from skills.gui_control import GuiControl
import asyncio


@pytest.mark.asyncio
@pytest.mark.parametrize('code,raw', [(1, ''), (0, 'invalid json'), (0, '{}')])
async def test_failed_window_inventory_cannot_prove_window_closed(monkeypatch, code, raw):
    monkeypatch.setattr(ground_truth.shutil, 'which', lambda _: '/bin/hyprctl')
    monkeypatch.setattr(ground_truth, '_run_command', AsyncMock(return_value=(code, raw, '')))
    result = await ground_truth.verify_window_state('editor', expected_open=False, timeout=.1)
    assert not result['verified'] and 'inventory' in result['reason']


@pytest.mark.asyncio
async def test_ambiguous_window_class_never_selects_first_match(monkeypatch):
    windows = [{'address': '0x1', 'pid': 1, 'class': 'editor'},
               {'address': '0x2', 'pid': 2, 'class': 'editor'}]
    monkeypatch.setattr(ground_truth.shutil, 'which', lambda _: '/bin/hyprctl')
    monkeypatch.setattr(ground_truth, '_run_command', AsyncMock(return_value=(0, json.dumps(windows), '')))
    monkeypatch.setattr('skills.system_control._query_active_window', AsyncMock(return_value=windows[0]))
    result = await ground_truth.verify_window_state('editor', expected_active=True, timeout=.1)
    assert not result['verified'] and 'ambiguous' in result['reason']
    assert (await ground_truth.verify_window_state('0x1', expected_active=True, timeout=.1))['verified']


@pytest.mark.asyncio
async def test_clipboard_verification_requires_entire_text_including_whitespace(monkeypatch):
    expected = ' ' + 'x'*60 + '\n'
    monkeypatch.setattr(ground_truth.shutil, 'which', lambda _: '/bin/wl-paste')
    read = AsyncMock(return_value=(0, expected[:50] + ' wrong ending', ''))
    monkeypatch.setattr(ground_truth, '_run_command', read)
    assert not (await ground_truth.verify_clipboard_state(expected_content=expected, timeout=.1))['verified']
    read.return_value = (0, expected, '')
    receipt = await ground_truth.verify_clipboard_state(expected_content=expected, timeout=.1)
    assert receipt['verified'] and receipt['details']['exact_match']
    assert read.call_args.kwargs['strip_output'] is False


@pytest.mark.asyncio
async def test_inspection_failure_does_not_prove_process_stopped(monkeypatch):
    monkeypatch.setattr(ground_truth.shutil, 'which', lambda _: '/bin/pgrep')
    monkeypatch.setattr(ground_truth, '_run_command', AsyncMock(return_value=(2, '', 'invalid query')))
    assert not (await ground_truth.verify_process_state('editor', expected_running=False, timeout=.1))['verified']
    monkeypatch.setattr(ground_truth.os, 'kill', Mock(side_effect=PermissionError))
    assert not (await ground_truth.verify_process_state(12345, expected_running=False, timeout=.1))['verified']


def test_native_clipboard_command_success_needs_exact_readback(monkeypatch):
    monkeypatch.setattr('jarvis_control.tools.shutil.which', lambda _: '/bin/tool')
    run = Mock(side_effect=[NS(returncode=0), NS(returncode=0, stdout=b'only a prefix')])
    monkeypatch.setattr('jarvis_control.tools.subprocess.run', run)
    result = Executor(Config()).call('clipboard', {'action':'write', 'text':'only a prefix and the required ending\n'})
    assert result.ok  # The write may have happened; do not silently replay it.
    assert not classify_result(result.as_tool_result()).completed
    assert run.call_args_list[0].kwargs['input'].endswith(b'ending\n')


@pytest.mark.parametrize('response', [NS(successful=False, error=None, data={}, log_id='id'),
                                    {'successful':False, 'error':None, 'data':{}}])
def test_composio_sdk_failure_survives_connector_wrapper(monkeypatch, response):
    session = NS(execute=Mock(return_value=response))
    monkeypatch.setattr(composio, 'get_session', lambda **_: session)
    result = composio.execute_tool('TEST_ACTION', {})
    assert result['success'] is False and not classify_result(result).completed


@pytest.mark.parametrize('candidates', [['SLACK_SEND_MESSAGE'], ['GITHUB_LIST_ISSUES', 'GITHUB_DELETE_ISSUE']])
def test_platform_discovery_never_executes_an_unrelated_or_ambiguous_tool(monkeypatch, candidates):
    execute = Mock(return_value=NS(data={'results':[{'primary_tool_slugs':candidates}]}))
    monkeypatch.setattr(composio, 'resolve_platform', lambda *_, **__: 'github')
    monkeypatch.setattr(composio, 'get_connection_status', lambda *_, **__: {'connected':True})
    monkeypatch.setattr(composio, 'get_session', lambda **_: NS(execute=execute))
    result = composio.execute_platform_action('github', 'check my issues')
    assert result['success'] is False
    execute.assert_called_once_with('COMPOSIO_SEARCH_TOOLS', arguments={'query':'github check my issues'})


@pytest.mark.asyncio
async def test_service_search_and_execution_are_wired_through_registry(monkeypatch):
    dispatch = AsyncMock(return_value={'success':True, 'data':[]})
    monkeypatch.setattr(composio, 'dispatch', dispatch)
    skills = DesktopSkills()
    try:
        await skills.execute('composio_search_tools', {'query':'github repositories'})
        assert dispatch.call_args.args == ('composio_search_tools', {'query':'github repositories', 'user_id':'local-user'})
        await skills.execute('composio_execute_tool', {'tool_slug':'TEST_ACTION', 'arguments':{'value':1}})
        assert dispatch.call_args.args == ('composio_execute_tool', {'tool_slug':'TEST_ACTION', 'arguments':{'value':1}, 'user_id':'local-user'})
    finally:
        await skills.close_agent_jobs()


@pytest.mark.asyncio
async def test_cancelled_desktop_command_is_killed_and_reaped(monkeypatch):
    killed = False

    async def communicate():
        if killed:
            return b'', b''
        await asyncio.Event().wait()

    def kill():
        nonlocal killed
        killed = True

    process = NS(returncode=None, communicate=AsyncMock(side_effect=communicate), kill=Mock(side_effect=kill))
    monkeypatch.setattr('skills.skills.asyncio.create_subprocess_exec', AsyncMock(return_value=process))
    skills = DesktopSkills.__new__(DesktopSkills)
    skills._command_timeout = 10
    task = asyncio.create_task(skills._run('owned-test-command'))
    await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert killed and process.communicate.await_count == 2


def test_authorization_link_does_not_complete_service_connection(monkeypatch):
    monkeypatch.setattr(composio, 'resolve_platform', lambda *_, **__: 'github')
    monkeypatch.setattr(composio, 'get_connection_status', lambda *_, **__: {'connected':False})
    monkeypatch.setattr(composio, 'authorize', lambda *_, **__: {'success':True, 'redirect_url':'https://example.test/auth', 'browser_opened':False})
    receipt = composio.connect_platform('github')
    assert receipt['success'] and not classify_result(receipt).completed
    assert 'have opened' not in receipt['message']
    opened=composio.open_platform_authorization('github')
    assert opened['success'] and not classify_result(opened).completed


@pytest.mark.asyncio
async def test_driver_window_ids_are_bound_to_observed_compositor_identities(monkeypatch):
    driver=GuiControl('/bin/unused')
    driver._call=AsyncMock(return_value={'windows':[{'window_id':256,'pid':42,'bounds':{'x':10,'y':20,'width':300,'height':200}}]})
    monkeypatch.setattr('skills.system_control._query_open_windows',AsyncMock(return_value=[
        {'address':'0x100','pid':42,'at':[10,20],'size':[300,200]},
        {'address':'0x200','pid':42,'at':[20,30],'size':[300,200]}]))
    assert (await driver.list_windows())['windows'][0]['address']=='0x100'


@pytest.mark.asyncio
async def test_ambiguous_driver_identity_is_never_guessed_from_pid(monkeypatch):
    driver=GuiControl('/bin/unused')
    driver._call=AsyncMock(return_value={'windows':[{'window_id':123,'pid':42,'bounds':{'x':10,'y':20,'width':300,'height':200}}]})
    monkeypatch.setattr('skills.system_control._query_open_windows',AsyncMock(return_value=[
        {'address':'0x100','pid':42,'at':[10,20],'size':[300,200]},
        {'address':'0x200','pid':42,'at':[10,20],'size':[300,200]}]))
    assert (await driver.list_windows())['windows'][0]['address'] is None
