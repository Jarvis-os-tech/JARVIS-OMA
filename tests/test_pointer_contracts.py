import json
import time
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, Mock

import pytest

from jarvis_control.wayland_pointer import validate_click
from jarvis_control.tools import Executor, Result
from jarvis_control.config import Config
from jarvis_control.outcomes import classify_result
from skills.gui_control import GuiControl, GuiControlError


@pytest.mark.parametrize('target', [('not-an-address',42,10,10),('0x0',42,10,10),('0x100',0,10,10),('0x100',42,'10',10)])
def test_native_pointer_rejects_unobserved_or_invalid_targets(target):
    with pytest.raises(ValueError):validate_click(*target)


def control():
    instance=GuiControl('/bin/unused')
    instance._desktop=(time.monotonic(),1920,1080)
    instance.list_windows=AsyncMock(return_value={'windows':[{
        'window_id':256,'pid':42,'address':'0x100','is_on_screen':True,
        'bounds':{'x':10,'y':20,'width':300,'height':200}}]})
    instance._query_active_window=AsyncMock(return_value={'address':'0x100','pid':42})
    return instance


@pytest.mark.asyncio
async def test_uncertain_driver_outcome_is_never_replayed_by_native_fallback(monkeypatch):
    instance=control()
    instance._call=AsyncMock(side_effect=GuiControlError('GUI driver timed out'))
    spawn=AsyncMock()
    monkeypatch.setattr('skills.gui_control.asyncio.create_subprocess_exec',spawn)
    with pytest.raises(GuiControlError):
        await instance.click_desktop(30,40,target_window_id=256,verify_active=True)
    spawn.assert_not_awaited()


@pytest.mark.asyncio
async def test_explicit_input_refusal_can_use_exact_observed_native_target(monkeypatch):
    instance=control()
    instance._call=AsyncMock(side_effect=GuiControlError('foreground_unavailable: input plugin is unavailable'))
    receipt={'status':'dispatched_unverified','verified':False,'route':'wayland_virtual_pointer'}
    process=NS(returncode=0,communicate=AsyncMock(return_value=(json.dumps(receipt).encode(),b'')))
    spawn=AsyncMock(return_value=process)
    monkeypatch.setattr('skills.gui_control.asyncio.create_subprocess_exec',spawn)
    result=await instance.click_desktop(30,40,target_window_id=256,verify_active=True)
    assert result['route']=='wayland_virtual_pointer'
    assert not classify_result(result).completed
    assert spawn.call_args.args[-5:]==('--click','0x100','42','30','40')


def test_native_text_click_backend_requires_an_observed_target_and_point(monkeypatch):
    executor=Executor(Config())
    monkeypatch.setattr('jarvis_control.tools.shutil.which',lambda _:None)
    shell=Mock(return_value=Result(True,'{"status":"dispatched_unverified","verified":false}'))
    monkeypatch.setattr(executor,'_shell',shell)
    assert not executor._press_button('left',False).ok
    shell.assert_not_called()
    assert executor._press_button('left',False,point=(30,40),target={'address':'0x100','pid':42}).ok
    assert not classify_result(shell.return_value.output).completed
