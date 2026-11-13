import asyncio
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock

import pytest
from jarvis_control.evidence import requires_action_evidence
from voice_layer.daemon import LiveVoice
from voice_layer.playback import Playback


def fixture(result=None):
    skills=NS(declarations=[{'name':'launch_app'},{'name':'list_capabilities'}],execute=AsyncMock(return_value=result))
    voice=LiveVoice(Playback('test'),skills=skills)
    voice._start_reply_watch()
    voice._filler_played=True  # This test isolates provider speech from local admission acknowledgements.
    voice._reply_authorized=True
    voice.connected=True
    voice._user_text='Open the browser'
    voice.local_router.synthesize=AsyncMock(return_value=bytes(960))
    session=NS(send_tool_response=AsyncMock(),send_client_content=AsyncMock())
    return voice,skills,session


def audio(text='The browser is open.'):
    return NS(server_content=NS(output_transcription=NS(text=text),model_turn=NS(parts=[NS(inline_data=NS(data=bytes(1920)))])))


def boundary():return NS(server_content=NS(turn_complete=True))


@pytest.mark.parametrize('text', ['Open the browser','Could you set brightness to 40 percent?','Send a WhatsApp message','Connect LinkedIn','Is GitHub connected?','What is the current volume?'])
def test_clear_operational_requests_require_receipts(text):
    assert requires_action_evidence(text)


@pytest.mark.parametrize('text',['Explain how browsers work','Start telling me a story','Why is volume not working?'])
def test_explanations_and_conversation_keep_normal_speech(text):
    assert not requires_action_evidence(text)


@pytest.mark.asyncio
async def test_spoken_success_without_any_tool_is_suppressed_and_not_saved_as_fact():
    voice,skills,session=fixture()
    await voice.handle(audio(),session)
    assert voice.player.queued_bytes==0 and voice._memory_assistant==''
    await voice.handle(boundary(),session)
    skills.execute.assert_not_awaited()
    session.send_client_content.assert_not_awaited()  # No hidden second model pass.
    assert voice.player.queued_bytes==0
    assert 'not marked it complete' in voice._memory_assistant


@pytest.mark.asyncio
@pytest.mark.parametrize('result',['ERROR: app unavailable',{'status':'queued'}, {'status':'dispatched','verified':False}])
async def test_failed_or_unverified_receipt_cannot_release_success_audio(result):
    voice,_,session=fixture(result)
    await voice.handle_tools(NS(function_calls=[NS(id='action',name='launch_app',args={'app':'browser'})]),session)
    await voice.handle(audio(),session)
    assert voice.player.queued_bytes==0
    await voice.handle(boundary(),session)
    await voice.handle(boundary(),session)
    assert voice.player.queued_bytes==0
    assert 'browser is open' not in voice._memory_assistant


@pytest.mark.asyncio
async def test_verified_result_allows_normal_model_speech_and_new_turn_resets_proof():
    voice,_,session=fixture({'status':'opened','verified':True})
    await voice.handle_tools(NS(function_calls=[NS(id='action',name='launch_app',args={'app':'browser'})]),session)
    await voice.handle(audio(),session)
    assert voice.player.queued_bytes==1920
    voice._start_reply_watch()
    assert voice._action_speech_blocked()


@pytest.mark.asyncio
async def test_capability_discovery_is_not_evidence_that_an_action_happened():
    voice,_,session=fixture({'status':'success','capabilities':[]})
    await voice.handle_tools(NS(function_calls=[NS(id='catalog',name='list_capabilities',args={})]),session)
    await voice.handle(audio(),session)
    assert voice.player.queued_bytes==0


@pytest.mark.asyncio
async def test_unverified_failure_does_not_enqueue_separate_voice():
    voice,_,_=fixture()
    assert await voice._finish_unverified_action()
    assert voice.player.queued_bytes==0


@pytest.mark.asyncio
@pytest.mark.parametrize('status,phrase',[('needs_confirmation','Say confirm or cancel'),
                                        ('awaiting_authorization','not connected yet')])
async def test_grounded_feedback_preserves_required_confirmation_and_authorization(status,phrase):
    voice,_,_=fixture()
    voice._action_evidence_status=status
    assert await voice._finish_unverified_action()
    assert phrase in voice._memory_assistant
