import asyncio
import json
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock

import pytest
from voice_layer.local_speech import LocalSpeechConfig
from voice_layer.needle_router import NeedleRouter, validate_prediction


def prediction(name, args, confidence=.95):
    return {'confidence': confidence, 'function_calls': [{'name': name, 'arguments': args}]}


@pytest.mark.parametrize('name,args,text,expected', [
    ('set_volume', {'value': 40}, 'please set the volume to forty', ('system_control', {'action':'volume_set','value':40})),
    ('change_volume', {'direction':'down'}, 'make the speakers quieter', ('system_control', {'action':'volume_adjust','value':-5})),
    ('change_brightness', {'direction':'up'}, 'make my screen brighter', ('system_control', {'action':'brightness_adjust','value':5})),
    ('open_application', {'app':'firefox'}, 'please open firefox for me', ('launch_app', {'app':'firefox'})),
    ('switch_workspace', {'workspace':2}, 'move me to workspace two', ('system_control', {'action':'workspace_switch','workspace':'2'})),
])
def test_grounded_offline_commands(name, args, text, expected):
    assert validate_prediction(prediction(name,args),text,{'firefox':'firefox'}) == expected


@pytest.mark.parametrize('text', ['do not open firefox', "don't open firefox", 'why open firefox',
                                   'explain how to open firefox', 'open firefox and delete documents',
                                   'if I open firefox', 'never open firefox'])
def test_negated_explanatory_or_multiple_actions_are_not_executed(text):
    assert validate_prediction(prediction('open_application', {'app':'firefox'}),text,{'firefox':'firefox'}) is None


@pytest.mark.parametrize('result,text', [
    (prediction('set_volume', {'value':70}), 'set volume 40'),
    (prediction('set_volume', {'value':140}), 'set volume 140'),
    (prediction('set_volume', {'value':True}), 'set volume one'),
    (prediction('change_volume', {'direction':'up'}), 'make the sound quieter'),
    (prediction('change_volume', {'direction':'down'}), 'lower the volume by ten'),
    (prediction('run_shell', {'command':'rm -rf ~'}), 'do a cleanup'),
    (prediction('open_application', {'app':'terminal'}), 'open firefox'),
    (prediction('set_volume', {'value':40}, .2), 'set volume 40'),
    (prediction('set_volume', {'value':40}, None), 'set volume 40'),
    (prediction('set_volume', {'value':40}, float('nan')), 'set volume 40'),
])
def test_unsafe_unconfident_and_ungrounded_predictions_are_rejected(result,text):
    assert validate_prediction(result,text,{'firefox':'firefox'}) is None


@pytest.mark.asyncio
async def test_timeout_stops_native_worker():
    config=LocalSpeechConfig(needle_enabled=True,needle_timeout=.05)
    router=NeedleRouter(config)
    killed=asyncio.Event()
    async def forever(): await asyncio.Event().wait()
    router.process=NS(stdin=NS(write=lambda data:None,drain=AsyncMock()),stdout=NS(readline=forever),
                      returncode=None,kill=killed.set,wait=AsyncMock())
    router.ready=True
    assert await router.route('make the sound quieter') is None
    assert killed.is_set()
    assert not router.ready


@pytest.mark.parametrize('name,text,expected', [
    ('decrease_volume', 'make the speakers quieter', ('system_control', {'action':'volume_adjust','value':-5})),
    ('increase_brightness', 'make the display brighter', ('system_control', {'action':'brightness_adjust','value':5})),
])
def test_single_action_schemas_still_require_grounded_direction(name,text,expected):
    assert validate_prediction(prediction(name,{}),text,{}) == expected


@pytest.mark.asyncio
async def test_needles_offline_prediction_uses_existing_executor_once():
    from voice_layer.config import Config
    from voice_layer.daemon import LiveVoice
    from voice_layer.playback import Playback
    voice=LiveVoice(Playback('test'),config=Config(),skills=NS(execute=AsyncMock(return_value={'ok':True,'status':'completed'})))
    voice.local_speech=NS(transcribe=AsyncMock(return_value='make the speakers quieter'))
    voice.local_router=NS(config=LocalSpeechConfig(needle_enabled=True),ready=True,
                          route=AsyncMock(return_value=('system_control',{'action':'volume_adjust','value':-5})),
                          synthesize=AsyncMock(return_value=bytes(960)))
    assert await voice._try_local_command(bytes(640),(0,0))
    voice.skills.execute.assert_awaited_once_with('system_control',{'action':'volume_adjust','value':-5})
    voice.local_router.synthesize.assert_awaited_once_with('Volume decreased.')
    assert not voice._reply_authorized


@pytest.mark.asyncio
async def test_needle_does_not_delay_online_conversation():
    from voice_layer.config import Config
    from voice_layer.daemon import LiveVoice
    from voice_layer.playback import Playback
    voice=LiveVoice(Playback('test'),config=Config())
    voice.connected=True
    voice.local_speech=NS(transcribe=AsyncMock(return_value='tell me about the weather'))
    voice.local_router=NS(config=LocalSpeechConfig(needle_enabled=True),route=AsyncMock())
    assert not await voice._try_local_command(bytes(640),(0,0))
    voice.local_router.route.assert_not_awaited()


def test_offline_feedback_never_claims_unverified_success():
    from jarvis_control.outcomes import classify_result
    from voice_layer.offline_speech import result_text
    text=result_text('system_control',{'action':'volume_set','value':40},classify_result({'ok':True,'status':'unverified'}))
    assert 'could not verify' in text
    assert 'set to' not in text


@pytest.mark.parametrize('text', ['is the screen brighter', 'are the speakers quieter',
                                   'could the screen be brighter', 'the volume is forty'])
def test_observations_and_questions_are_not_actions(text):
    assert validate_prediction(prediction('increase_brightness',{}),text,{}) is None


def test_compound_number_cannot_be_truncated_to_its_last_digit():
    assert validate_prediction(prediction('set_volume',{'value':1}), 'set volume to forty one',{}) is None
    assert validate_prediction(prediction('set_volume',{'value':41}), 'set volume to forty one',{}) == ('system_control',{'action':'volume_set','value':41})
