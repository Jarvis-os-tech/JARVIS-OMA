"""Stage only reviewed integration fixes over the installed runtime."""
from __future__ import annotations
import argparse
import ast
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time

SOURCE=Path(__file__).resolve().parents[1]
RUNTIME=Path.home()/'.local/share/jarvis-runtime'


def node_for(text, qualified):
    body=ast.parse(text).body
    for part in qualified.split('.'):
        node=next((n for n in body if getattr(n,'name',None)==part or
                   isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id==part for t in n.targets)),None)
        if node is None:return None
        body=getattr(node,'body',[])
    return node


def splice(installed, source, names):
    for name in names:
        new=node_for(source,name)
        if new is None:raise ValueError('Missing reviewed definition: '+name)
        old=node_for(installed,name)
        fragment=''.join(source.splitlines(keepends=True)[new.lineno-1:new.end_lineno])
        if old:
            lines=installed.splitlines(keepends=True)
            installed=''.join(lines[:old.lineno-1])+fragment+''.join(lines[old.end_lineno:])
        elif '.' not in name:
            installed+='\n\n'+fragment
        else:
            owner=node_for(installed,name.split('.')[0])
            if owner is None:raise ValueError('Installed class is missing: '+name)
            lines=installed.splitlines(keepends=True)
            installed=''.join(lines[:owner.end_lineno])+'\n'+fragment+''.join(lines[owner.end_lineno:])
    return installed


def prepare(destination):
    parent=(RUNTIME/'current').resolve(strict=True)
    if not parent.is_relative_to(RUNTIME/'releases'):raise ValueError('Unmanaged release')
    target=Path(tempfile.mkdtemp(prefix='jarvis-integration-',dir=destination))
    subprocess.run(['cp','--archive','--reflink=auto',str(parent)+'/.',str(target)],check=True)
    changed={}
    def put(relative, content):
        path=target/relative
        if path.is_symlink():raise ValueError('Linked module: '+relative)
        if path.exists():path.chmod(path.stat().st_mode|0o200)
        path.write_text(content)
        if path.suffix=='.py':compile(content,relative,'exec')
        changed[relative]=hashlib.sha256(path.read_bytes()).hexdigest()
    for relative in ('jarvis_control/outcomes.py','jarvis_control/evidence.py','jarvis_control/device_execution.py',
                     'jarvis_control/execution_policy.py','jarvis_control/tools.py',
                     'jarvis_control/wayland_keyboard.py','jarvis_control/wayland_pointer.py','core/tool_dispatch.py',
                     'skills/ground_truth.py','skills/gui_control.py'):
        put(relative,(SOURCE/relative).read_text())
    patches={
        'skills/skills.py':('skills/skills.py',['DesktopSkills._run','DesktopSkills._adapter_write_clipboard']),
        'jarvis_voice/daemon.py':('voice_layer/daemon.py',['LiveVoice.handle_tools','build_instruction',
            'LiveVoice.handle','LiveVoice._start_reply_watch','LiveVoice._action_speech_blocked','LiveVoice._finish_unverified_action']),
        'jarvis_voice/persona.py':('voice_layer/persona.py',['SPOKEN_UPDATES']),
        'jarvis_control/nlu.py':('jarvis_control/nlu.py',['NLUEngine.validate_tool_intent']),
        'connectors/composio.py':('connectors/composio.py',[
            '_execution_receipt','search_tools','execute_tool','execute_platform_action','authorize','connect_platform','open_platform_authorization']),
    }
    for deployed,(relative,names) in patches.items():
        original=(target/deployed).read_text()
        content=splice(original,(SOURCE/relative).read_text(),names)
        if deployed=='jarvis_voice/daemon.py':
            if 'from jarvis_control.evidence import requires_action_evidence, META_TOOLS' not in content:
                content=content.replace('from jarvis_control.outcomes import classify_result',
                    'from jarvis_control.outcomes import classify_result\nfrom jarvis_control.evidence import requires_action_evidence, META_TOOLS')
            if 'from jarvis_control.execution_policy import tool_timeout' not in content:
                content=content.replace('from jarvis_control.outcomes import classify_result',
                    'from jarvis_control.outcomes import classify_result\nfrom jarvis_control.execution_policy import tool_timeout')
            if not node_for(content,'MAX_TOOL_CALLS_PER_TURN'):
                content=content.replace("log = logging.getLogger('jarvis_voice')",
                    "MAX_TOOL_CALLS_PER_TURN = 64\n\nlog = logging.getLogger('jarvis_voice')")
        put(deployed,content)
    relative='skills/domains/composio.py'
    content=(target/relative).read_text()
    if '_adapter_composio_search = _adapter_search_tools' not in content:
        node=node_for(content,'ComposioDomain')
        lines=content.splitlines(keepends=True)
        content=''.join(lines[:node.end_lineno])+('\n    _adapter_composio_search = _adapter_search_tools\n'
                  '    _adapter_composio_execute = _adapter_execute_tool\n')+''.join(lines[node.end_lineno:])
    put(relative,content)
    metadata=json.loads((target/'release.json').read_text())
    metadata['system_integration_extension']={'parent':str(parent),'created_at':datetime.now(timezone.utc).isoformat(),'sha256':changed}
    path=target/'release.json';path.chmod(path.stat().st_mode|0o200)
    path.write_text(json.dumps(metadata,indent=2)+'\n')
    check='''
import asyncio,json
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock
from skills.skills import DesktopSkills
from jarvis_control.outcomes import classify_result
from jarvis_control.execution_policy import tool_timeout
from jarvis_control.wayland_keyboard import literal_plan
from jarvis_control.nlu import NLUEngine
from jarvis_voice.daemon import LiveVoice
from jarvis_voice.playback import Playback
assert not classify_result({'ground_truth_verified':False}).completed
assert not classify_result({'successful':False}).completed
assert not classify_result({'status':'awaiting_authorization'}).completed
assert tool_timeout('execute_domain_tool',{'tool_name':'read_screen'})==90
assert literal_plan('Aa!')[1]==[(30,1),(30,0),(2,1)]
assert not NLUEngine.validate_tool_intent('phone_list_contacts',{},'Open the browser on my PC')[0]
async def main():
 s=DesktopSkills()
 try:
  assert all(callable(getattr(s,s.ADAPTERS[x['adapter']],None)) for x in s._skills.values())
  execute=AsyncMock(return_value={'status':'success','verified':True})
  v=LiveVoice(Playback('test'),skills=NS(declarations=[{'name':'system_query'}],execute=execute))
  v._reply_authorized=True
  await v.handle_tools(NS(function_calls=[NS(id=str(i),name='system_query',args={}) for i in range(9)]),NS(send_tool_response=AsyncMock()))
  assert execute.await_count==9
  print(json.dumps({'staged_checks':'passed','desktop_handlers':len(s._skills),'workflow_steps':9}))
 finally:await s.close_agent_jobs()
asyncio.run(main())
'''
    subprocess.run([str(RUNTIME/'venv/bin/python'),'-c',check],cwd=target,
        env=dict(os.environ,PYTHONPATH=str(target),PYTHONDONTWRITEBYTECODE='1'),check=True,timeout=35)
    return target


def status():
    result=subprocess.run([str(RUNTIME/'current/bin/jarvis-voice'),'status','--json'],capture_output=True,text=True,timeout=5)
    return json.loads(result.stdout) if result.returncode==0 else {}


def ipc(command):
    path=Path(os.environ.get('XDG_RUNTIME_DIR',f'/run/user/{os.getuid()}'))/'jarvis/control.sock'
    with socket.socket(socket.AF_UNIX) as client:
        client.settimeout(5);client.connect(str(path));client.sendall((json.dumps(command)+'\n').encode())
        return json.loads(client.recv(65536))


def activate(staged):
    staged=Path(staged).resolve(strict=True)
    metadata=json.loads((staged/'release.json').read_text())['system_integration_extension']
    parent=Path(metadata['parent'])
    before=status()
    sys.path.insert(0,str(parent))
    from orchestration.release_manager import ReleaseManager
    manager=ReleaseManager(RUNTIME)
    name=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'-system-integration'
    installed=manager.install_prepared_release(staged,name,expected_current=parent,
        expected_hashes=metadata['sha256'],timeout=25)
    try:
        after={}
        for _ in range(40):
            try:after=status()
            except (ValueError,OSError):pass
            if after.get('control_enabled'):break
            time.sleep(.25)
        if not after.get('control_enabled'):raise RuntimeError('Control execution did not become available')
        if before.get('muted'):ipc({'command':'set_mute','muted':True})
        if before.get('standby'):ipc({'command':'standby'})
        if before.get('microphone',{}).get('muted') is True:
            source=after.get('microphone',{}).get('source','')
            if source.startswith('jarvis_aec_'):
                subprocess.run(['pactl','set-source-mute',source,'1'],check=True,timeout=5)
        if not before.get('standby') and not before.get('muted'):
            for _ in range(40):
                after=status()
                if after.get('connected') or after.get('standby'):break
                time.sleep(.25)
            if not after.get('connected') and not after.get('standby'):raise RuntimeError('Voice connection failed')
        final=status()
    except Exception:
        manager._switch_release(parent,25,expected_current=installed)
        raise
    report={'installed':str(installed),'parent':str(parent),'status':final,'privacy_before':{
        key:before.get(key) for key in ('muted','standby')},'module_hashes':metadata['sha256']}
    Path('/tmp/jarvis-system-deployment.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'installed':str(installed),'parent':str(parent),'connected':final.get('connected'),
        'standby':final.get('standby'),'tools':final.get('tool_count'),'error':final.get('error')},indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--prepare',type=Path)
    group.add_argument('--activate',type=Path)
    args=parser.parse_args()
    if args.prepare:print(json.dumps({'prepared':str(prepare(args.prepare))}))
    else:activate(args.activate)
