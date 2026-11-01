import asyncio
import hashlib
import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from orchestration.durable_hermes import DurableHermes, GoalWorker
from orchestration.hermes_bridge import HermesBridge


class Supervisor:
    def __init__(self): self.calls=[]
    def start(self, root, job): self.calls.append(job['id'])


class Bridge:
    def __init__(self):
        self.submits=[]
        self.value={'status':'started'}
        self.cancelled=[]
    async def create_session(self, **kw): return 'native-owned'
    async def admit(self, session_id, prompt, submission_id):
        self.submits.append(submission_id)
        return {'admission_id':'admission-one','status':'started'}
    async def receipt(self, *args): return self.value
    async def cancel_admission(self,*args): return {'status':'terminal','outcome':'cancelled'}
    async def cancel(self, session):
        self.cancelled.append(session);return {'acknowledged':True}
    async def close(self): pass


@pytest.mark.asyncio
async def test_voice_restart_does_not_cancel_or_replay_native_work(tmp_path):
    bridge=Bridge();supervisor=Supervisor()
    client=DurableHermes(tmp_path,bridge=bridge,supervisor=supervisor)
    item=client.start('Write report', request_key='voice-turn-one')
    worker=GoalWorker(tmp_path,item['id'],bridge=bridge)
    assert not await worker.step()
    assert len(bridge.submits)==1
    await client.close()
    assert not bridge.cancelled
    returning=DurableHermes(tmp_path,bridge=bridge,supervisor=supervisor)
    same=returning.start('Write report',request_key='voice-turn-one')
    assert same['id']==item['id'] and len(supervisor.calls)==1
    assert not await worker.step()
    assert len(bridge.submits)==1
    bridge.value={'status':'terminal','outcome':'completed','result':{'final_response':'Report summary.'}}
    assert await worker.step()
    await returning.refresh()
    assert returning.status(item['id'])['state']=='completed'
    assert returning.status(item['id'])['output']=='Report summary.'
    assert not returning.status(item['id'])['verified']
    with pytest.raises(ValueError,match='different goal'):
        returning.start('A different report',request_key='voice-turn-one')


@pytest.mark.asyncio
async def test_missing_required_artifact_fails_after_successful_native_exit(tmp_path):
    bridge=Bridge();client=DurableHermes(tmp_path,bridge=bridge,supervisor=Supervisor())
    job=client.start('Create result',acceptance_checks=[{'path':'result.txt','sha256':hashlib.sha256(b'42').hexdigest()}])
    worker=GoalWorker(tmp_path,job['id'],bridge=bridge)
    await worker.step()
    bridge.value={'status':'terminal','outcome':'completed','result':{'final_response':'Done'}}
    assert await worker.step()
    client._recover()
    assert client.status(job['id'])['state']=='failed'
    assert client.status(job['id'])['acceptance']['status']=='failed'


@pytest.mark.asyncio
async def test_unknown_receipt_is_not_replayed(tmp_path):
    bridge=Bridge();client=DurableHermes(tmp_path,bridge=bridge,supervisor=Supervisor())
    job=client.start('Read a document');worker=GoalWorker(tmp_path,job['id'],bridge=bridge)
    await worker.step()
    bridge.value={'status':'unknown'}
    assert await worker.step()
    assert len(bridge.submits)==1
    assert worker.load()['execution']=='unknown'


@pytest.mark.asyncio
async def test_cancel_waits_for_native_and_descendant_receipts(tmp_path, monkeypatch):
    bridge=Bridge();client=DurableHermes(tmp_path,bridge=bridge,supervisor=Supervisor())
    job=client.start('Research');worker=GoalWorker(tmp_path,job['id'],bridge=bridge)
    await worker.step();await client.cancel(job['id'])
    monkeypatch.setattr(worker,'cancel_children',AsyncMock(return_value=False))
    assert await worker.step()
    assert worker.load()['execution']=='unknown'
    assert bridge.cancelled==['native-owned']


@pytest.mark.asyncio
async def test_handoff_is_generation_fenced_and_preserves_saved_work(tmp_path):
    bridge=Bridge();client=DurableHermes(tmp_path,bridge=bridge,supervisor=Supervisor())
    item=client.start('Prepare a plan');worker=GoalWorker(tmp_path,item['id'],bridge=bridge)
    await worker.step()
    r=await client.handoff(item['id'],'jarvis',1)
    assert r['coordinator_owner']=='jarvis' and r['owner_generation']==2
    assert r['session_id']=='native-owned'
    with pytest.raises(ValueError,match='Stale'):
        await client.handoff(item['id'],'hermes',1)
    assert await worker.step()


@pytest.mark.asyncio
async def test_worker_completion_wakes_hermes_once_with_same_event_identity(tmp_path, monkeypatch):
    bridge=Bridge();client=DurableHermes(tmp_path,bridge=bridge,supervisor=Supervisor())
    item=client.start('Implement and review');worker=GoalWorker(tmp_path,item['id'],bridge=bridge)
    await worker.step()
    bridge.value={'status':'terminal','outcome':'completed','result':{'final_response':'Worker started'}}
    child={'id':'child-one','state':'completed','name':'Write implementation'}
    monkeypatch.setattr(worker,'children',lambda j:[child])
    assert not await worker.step()
    assert worker.load()['review_round']==1
    assert worker.load()['submission_id'].startswith('review-')
    assert await worker.step()  # admits review, reads its completion; no repeated child event
    assert len(bridge.submits)==2


@pytest.mark.asyncio
async def test_private_session_registry_survives_client_restart(tmp_path):
    (tmp_path / '.git').mkdir()
    first=HermesBridge(python='python',ownership_path=tmp_path/'owned.json')
    first._request=AsyncMock(return_value={'session_id':'mine'})
    await first.create_session(workspace=tmp_path)
    second=HermesBridge(python='python',ownership_path=tmp_path/'owned.json')
    second._owned('mine')
    with pytest.raises(ValueError,match='Only sessions'):
        second._owned('foreign')
    assert (tmp_path/'owned.json').stat().st_mode & 0o777==0o600
