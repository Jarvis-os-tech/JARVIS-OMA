import ast
import asyncio
import base64
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest

from pma_voice_only import voice
from pma_voice_only.config import Config

@pytest.fixture
def engine(tmp_path, monkeypatch):
    monkeypatch.setattr(voice,'RUNTIME_DIR',tmp_path/'run')
    monkeypatch.setattr(voice,'STATE_FILE',tmp_path/'run/state.json')
    monkeypatch.setattr(voice,'LEVEL_FILE',tmp_path/'run/level')
    speaker=SimpleNamespace(write=AsyncMock(),interrupt=AsyncMock(),close=AsyncMock(),_proc=None,
                            is_playing=lambda *args:False,level_now=lambda:0.0)
    session=voice.VoiceSession(Config(),speaker)
    session.send=AsyncMock()
    return session

def test_setup_exposes_audio_and_no_tools():
    setup=voice.setup_message(Config())['setup']
    assert setup['tools']==[]
    assert setup['generationConfig']['responseModalities']==['AUDIO']
    assert setup['model']=='models/gemini-3.8-live'
    assert setup['generationConfig']['speechConfig']['voiceConfig']['prebuiltVoiceConfig']['voiceName']=='Puck'

def test_no_imports_from_full_pma_or_jarvis():
    root=Path(voice.__file__).parent
    forbidden={'omarchy_voice','core','skills','connectors','tools','capabilities','vision','tasks','browser','planner'}
    for p in root.glob('*.py'):
        for n in ast.walk(ast.parse(p.read_text())):
            if isinstance(n,ast.Import):
                assert all(a.name.split('.')[0] not in forbidden for a in n.names)
            if isinstance(n,ast.ImportFrom):
                assert (n.module or '').split('.')[0] not in forbidden

@pytest.mark.asyncio
async def test_unsolicited_tools_are_refused_without_execution(engine):
    await engine.handle(json.dumps({'toolCall':{'functionCalls':[{'id':'1','name':'run_shell','args':{'command':'touch forbidden'}}]}}))
    result=engine.send.call_args.args[0]['toolResponse']['functionResponses'][0]
    assert result['id']=='1'
    assert 'error' in result['response']
    assert engine.stats['blocked_tool_calls']==1
    engine.speaker.write.assert_not_called()

@pytest.mark.asyncio
async def test_pcm_audio_is_played_and_counted(engine):
    engine.active=True
    pcm=b'\x01\x00'*100
    await engine.handle(json.dumps({'serverContent':{'modelTurn':{'parts':[{'inlineData':{'mimeType':'audio/pcm;rate=24000','data':base64.b64encode(pcm).decode()}}]}}}))
    engine.speaker.write.assert_awaited_once_with(pcm)
    assert engine.stats['output_bytes']==200

@pytest.mark.asyncio
async def test_muted_session_drops_late_audio(engine):
    await engine.handle(json.dumps({'serverContent':{'modelTurn':{'parts':[{'inlineData':{'mimeType':'audio/pcm;rate=24000','data':'AQACAA=='}}]}}}))
    engine.speaker.write.assert_not_called()

@pytest.mark.asyncio
async def test_provider_interruption_discards_audio(engine):
    engine.active=True
    await engine.handle(json.dumps({'serverContent':{'interrupted':True,'modelTurn':{'parts':[{'inlineData':{'mimeType':'audio/pcm','data':'AQACAA=='}}]}}}))
    engine.speaker.interrupt.assert_awaited_once()
    engine.speaker.write.assert_not_called()

@pytest.mark.asyncio
async def test_partial_pcm_is_rejected(engine):
    engine.active=True
    with pytest.raises(ValueError):
        await engine.handle(json.dumps({'serverContent':{'modelTurn':{'parts':[{'inlineData':{'mimeType':'audio/pcm','data':'AQ=='}}]}}}))

@pytest.mark.asyncio
async def test_stop_closes_capture_playback_and_connection(engine):
    engine.active=engine.connected=True
    engine.ws=SimpleNamespace(close=AsyncMock())
    engine.stop_capture=AsyncMock()
    assert await engine.set_active(False)=='idle'
    engine.stop_capture.assert_awaited_once()
    engine.speaker.interrupt.assert_awaited_once()
    engine.ws.close.assert_awaited_once()
    assert not engine.active and not engine.wanted.is_set()

@pytest.mark.asyncio
async def test_setup_ack_precedes_microphone_start_and_mute_is_not_fatal(engine,monkeypatch):
    closed=asyncio.Event()
    capture_started=asyncio.Event()
    acked=False
    class Socket:
        async def send(self,payload):
            assert json.loads(payload)['setup']['tools']==[]
        async def recv(self):
            nonlocal acked
            acked=True
            return '{"setupComplete":{}}'
        async def close(self):
            closed.set()
        async def __aenter__(self):return self
        async def __aexit__(self,*args):return False
        async def __aiter__(self):
            await closed.wait()
            if False:yield None
    monkeypatch.setattr(voice.websockets,'connect',lambda *a,**kw:Socket())
    async def capture():
        assert acked
        capture_started.set()
        await asyncio.Event().wait()
    engine.capture=capture
    engine.active=True
    worker=asyncio.create_task(engine.connect('synthetic-test-key'))
    await asyncio.wait_for(capture_started.wait(),1)
    await engine.set_active(False)
    await asyncio.wait_for(worker,1)
    assert not worker.cancelled()

def test_error_output_redacts_key(monkeypatch):
    monkeypatch.setenv('GEMINI_API_KEY','synthetic-secret-123')
    assert 'synthetic-secret-123' not in voice.safe_error(RuntimeError('failed synthetic-secret-123'))

def test_nonvoice_control_is_not_available(engine):
    engine.loop=object()
    assert engine.control('confirm').startswith('error:')
    assert engine.control('vision start').startswith('error:')
    assert engine.control('task run').startswith('error:')

def test_status_advertises_only_voice(engine):
    status=json.loads(engine.control('status'))
    assert status['tools_enabled'] is False
    assert set(status['features'])=={'microphone','speech','playback','interruptions'}
