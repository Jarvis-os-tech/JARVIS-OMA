from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
import asyncio
import json

import pytest

from orchestration.hermes_notices import NativeNotices
from orchestration.hermes_bridge import HermesBridge
from orchestration.durable_hermes import DurableHermes
from jarvis_control.skills import UnifiedSkills
try:
    from tests.test_orchestration.test_durable_hermes import Bridge, Supervisor, GoalWorker
except ImportError:
    from test_durable_hermes import Bridge, Supervisor, GoalWorker


@pytest.mark.asyncio
async def test_scheduled_result_outbox_survives_restart_and_acknowledges_once(tmp_path):
    future=datetime.now(timezone.utc).isoformat()
    bridge=SimpleNamespace(scheduled_results=AsyncMock(return_value={'events':[]}))
    notices=NativeNotices(tmp_path,bridge)
    future=datetime.now(timezone.utc).isoformat()
    bridge.scheduled_results.return_value={'events':[{'id':'execution','name':'Daily project brief','state':'completed','finished_at':future}]}
    events=await notices.events()
    assert len(events)==1 and 'Daily project brief' in events[0]['text']
    replacement=NativeNotices(tmp_path,bridge)
    assert (await replacement.events())[0]['id']==events[0]['id']
    replacement.acknowledge(events[0]['id'])
    assert not await NativeNotices(tmp_path,bridge).events()


@pytest.mark.asyncio
async def test_stale_completion_ack_does_not_overwrite_newer_receipt(tmp_path):
    bridge=Bridge();client=DurableHermes(tmp_path,bridge=bridge,supervisor=Supervisor())
    item=client.start('Plan a change');worker=GoalWorker(tmp_path,item['id'],bridge=bridge)
    worker.update(state='completed',execution='response_received')
    desktop=SimpleNamespace(_task_agents=client)
    unified=UnifiedSkills(desktop_skills=desktop)
    client.native_notices.events=AsyncMock(return_value=[])
    events=await unified.background_events()
    worker.update(state='interrupted',owner_generation=2)
    await unified.acknowledge_event(events[0]['id'])
    current=worker.load()
    assert current['owner_generation']==2 and current['state']=='interrupted'
    assert not current['notice_acknowledged']


@pytest.mark.asyncio
async def test_approval_responses_are_choice_and_generation_fenced(tmp_path):
    bridge=HermesBridge(python='python')
    bridge.owned_sessions.add('owned')
    bridge.snapshot=AsyncMock(return_value={'prompts':[{'kind':'approval','prompt_id':'p','choices':['once','deny'],'execution_generation':2}]})
    bridge._request=AsyncMock(return_value={'accepted':True})
    with pytest.raises(ValueError,match='stale'):
        await bridge.respond_approval('owned','p','once',1)
    with pytest.raises(ValueError,match='allowed'):
        await bridge.respond_approval('owned','p','always',2)
    assert not bridge._request.called
    assert (await bridge.respond_approval('owned','p','once',2))['accepted']
