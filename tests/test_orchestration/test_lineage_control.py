import asyncio,json,sys
from pathlib import Path
import pytest
from orchestration.agent_orchestrator import AgentOrchestrator
from orchestration.mcp_server import OrchestratorMCP


@pytest.mark.asyncio
async def test_cancel_parent_stops_owned_process_group_and_leaves_other_work(tmp_path):
    goals=tmp_path/'.jarvis-learning/task-agents';goals.mkdir(parents=True)
    parent='task-0123456789ab'
    workspace=tmp_path/'parent-workspace';workspace.mkdir()
    (goals/(parent+'.json')).write_text(json.dumps({'id':parent,'coordinator_owner':'hermes','owner_generation':1,'state':'running','workspace':str(workspace)}))
    def command(*args):
        return [sys.executable,'-c','import time; time.sleep(30)']
    orch=AgentOrchestrator(executables={'codex':sys.executable},command_builder=command)
    bridge=OrchestratorMCP(tmp_path/'.jarvis-orchestration',workspace_roots=[tmp_path],orchestrator=orch)
    socket=tmp_path/'control.sock'
    server=await asyncio.start_unix_server(bridge.control,path=socket)
    try:
        first=await bridge.delegate('codex','Owned assignment','one',parent_task_id=parent,owner_generation=1)
        second=await bridge.delegate('codex','Independent assignment','two')
        with pytest.raises(ValueError,match='stale'):
            await bridge.delegate('codex','Stale assignment','stale',parent_task_id=parent,owner_generation=2)
        await asyncio.sleep(.1)
        reader,writer=await asyncio.open_unix_connection(socket)
        writer.write(json.dumps({'operation':'cancel_parent','parent_task_id':parent,'owner_generation':1}).encode()+b'\n');await writer.drain()
        result=json.loads(await asyncio.wait_for(reader.readline(),10))
        writer.close();await writer.wait_closed()
        assert result['acknowledged'] and result['matched_workers']==1
        assert bridge._get(first['id'])['state']=='cancelled'
        assert not orch.processes.get(first['worker_id'])
        assert bridge._get(second['id'])['state']=='running'
    finally:
        server.close();await server.wait_closed();await bridge.close()
