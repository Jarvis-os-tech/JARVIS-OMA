"""Provider-event control boundaries, without desktop or cloud operations."""
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from jarvis_voice.daemon import LiveVoice
from jarvis_voice.playback import Playback


def control_fixture(name='system_query', result='Current time retrieved'):
    skills = SimpleNamespace(
        declarations=[{'name': name}],
        execute=AsyncMock(return_value=result),
    )
    voice = LiveVoice(Playback('default'), skills=skills)
    voice._reply_authorized = True
    session = SimpleNamespace(send_tool_response=AsyncMock())
    return voice, skills, session


def tool_event(name='system_query', args=None, *, transcript=None):
    content = None if transcript is None else SimpleNamespace(
        input_transcription=SimpleNamespace(text=transcript))
    return SimpleNamespace(
        tool_call=SimpleNamespace(function_calls=[SimpleNamespace(
            name=name, id='boundary-call', args=args or {})]),
        server_content=content,
    )


def provider_result(session):
    responses = session.send_tool_response.call_args.kwargs['function_responses']
    assert len(responses) == 1
    assert responses[0].id == 'boundary-call'
    return responses[0].response


@pytest.mark.asyncio
@pytest.mark.parametrize('blocked_state', ['muted', 'dropped_response', 'unauthorized'])
async def test_control_never_executes_outside_an_authorized_voice_turn(blocked_state):
    voice, skills, session = control_fixture()
    if blocked_state == 'muted':
        voice.muted = True
    elif blocked_state == 'dropped_response':
        voice._drop_response = True
    else:
        voice._reply_authorized = False

    await voice.handle(tool_event(args={'topic': 'time'}), session)

    skills.execute.assert_not_awaited()
    response = provider_result(session)
    assert response['ok'] is False
    assert response['status'] == 'rejected'
    assert response['error']


@pytest.mark.asyncio
async def test_control_failure_is_sent_to_provider_as_failure():
    voice, skills, session = control_fixture(result='ERROR: no matching window')

    await voice.handle(tool_event(args={'topic': 'time'}), session)

    skills.execute.assert_awaited_once_with('system_query', {'topic': 'time'})
    response = provider_result(session)
    assert response['ok'] is False
    assert response['status'] == 'failed'
    assert response['error'] == 'no matching window'


@pytest.mark.asyncio
async def test_held_control_action_is_distinct_from_success_or_failure():
    held = 'ERROR: This action needs spoken confirmation. Stop here and ask the user to confirm out loud.'
    voice, skills, session = control_fixture(name='omarchy_cli', result=held)

    await voice.handle(tool_event('omarchy_cli', {'command': 'held-fixture-action'}), session)

    response = provider_result(session)
    assert response['ok'] is False
    assert response['status'] == 'needs_confirmation'
    assert 'needs spoken confirmation' in response['error']
    assert voice._confirmation_gate_turn == voice.gate.accepted_turns


@pytest.mark.asyncio
async def test_confirmation_uses_transcript_from_the_same_provider_event():
    voice, skills, session = control_fixture(name='confirm_last', result='Confirmed fixture action')
    voice.gate.accepted_turns = 2
    voice._confirmation_gate_turn = 1
    voice._user_text = ''

    await voice.handle(tool_event('confirm_last', {'heard_phrase': 'confirm'}, transcript='Confirm.'), session)

    skills.execute.assert_awaited_once_with('confirm_last', {'heard_phrase': 'confirm'})
    response = provider_result(session)
    assert response['ok'] is True
    assert voice._user_text == 'Confirm.'


@pytest.mark.asyncio
async def test_authorized_control_success_preserves_verified_result():
    result = 'workspace 2 is active; verified'
    voice, skills, session = control_fixture(name='hypr_dispatch', result=result)
    arguments = {'lua': 'synthetic-fixture-call'}

    await voice.handle(tool_event('hypr_dispatch', arguments), session)

    skills.execute.assert_awaited_once_with('hypr_dispatch', arguments)
    response = provider_result(session)
    assert response['ok'] is True
    assert response['result'] == result


@pytest.mark.asyncio
@pytest.mark.parametrize('first_result', [
    'ERROR: no matching fixture window',
    'ERROR: This action needs spoken confirmation. Stop here and ask the user to confirm out loud.',
])
async def test_failed_or_held_action_stops_remaining_batch(first_result):
    voice, skills, session = control_fixture(name='first_action', result=first_result)
    skills.declarations.append({'name': 'dependent_action'})
    batch = SimpleNamespace(function_calls=[
        SimpleNamespace(name='first_action', id='first', args={}),
        SimpleNamespace(name='dependent_action', id='dependent', args={}),
    ])

    await voice.handle_tools(batch, session)

    skills.execute.assert_awaited_once_with('first_action', {})
    responses = session.send_tool_response.call_args.kwargs['function_responses']
    assert len(responses) == 2
    assert responses[1].response['ok'] is False
    assert responses[1].response['status'] == 'not_run'


@pytest.mark.asyncio
@pytest.mark.parametrize('changed_token', ['speech_turn', 'playback_generation'])
async def test_stale_batch_cannot_continue_under_a_new_authorized_turn(changed_token):
    voice, skills, session = control_fixture(name='first_action')
    skills.declarations.append({'name': 'dependent_action'})

    async def change_turn_during_execution(name, arguments):
        if changed_token == 'speech_turn':
            voice.gate.accepted_turns += 1
        else:
            voice.player.generation += 1
        # A new user turn may already have authorization; a boolean alone is insufficient.
        voice._reply_authorized = True
        return 'First fixture action completed'

    skills.execute.side_effect = change_turn_during_execution
    batch = SimpleNamespace(function_calls=[
        SimpleNamespace(name='first_action', id='first', args={}),
        SimpleNamespace(name='dependent_action', id='dependent', args={}),
    ])

    await voice.handle_tools(batch, session)

    skills.execute.assert_awaited_once_with('first_action', {})
    responses = session.send_tool_response.call_args.kwargs['function_responses']
    assert responses[0].response['ok'] is True
    assert responses[1].response['ok'] is False
    assert responses[1].response['status'] in ('rejected', 'not_run')


@pytest.mark.asyncio
async def test_old_tool_event_cannot_complete_new_user_turn():
    voice, skills, session = control_fixture()
    async def new_turn(name, args):
        voice.gate.accepted_turns += 1
        voice._reply_authorized = True
        return 'Old action completed'
    skills.execute.side_effect = new_turn
    event = tool_event()
    event.server_content = SimpleNamespace(turn_complete=True)
    await voice.handle(event, session)
    assert voice._reply_authorized


@pytest.mark.asyncio
async def test_startup_greeting_cannot_initiate_desktop_actions():
    voice, skills, session = control_fixture()
    voice._greeting_active = True
    await voice.handle(tool_event(), session)
    skills.execute.assert_not_awaited()
    assert provider_result(session)['status'] == 'rejected'


@pytest.mark.asyncio
async def test_unacknowledged_interruption_rejects_old_tool_only_event():
    voice, skills, session = control_fixture()
    voice._barge_pending = True
    await voice.handle(tool_event(), session)
    skills.execute.assert_not_awaited()
    assert provider_result(session)['status'] == 'rejected'


@pytest.mark.asyncio
async def test_phone_cannot_execute_for_an_unqualified_pc_command():
    voice, skills, session = control_fixture(name='phone_control')
    await voice.handle(tool_event('phone_control', {'action': 'open_app', 'package_name': 'com.whatsapp'},
                                  transcript='Open WhatsApp'), session)
    skills.execute.assert_not_awaited()
    assert not provider_result(session)['ok']


@pytest.mark.asyncio
async def test_polite_desktop_action_executes_automatically():
    voice, skills, session = control_fixture(name='system_control_extension', result='Volume changed; verified')
    args = {'category': 'audio', 'action': 'volume_up'}
    await voice.handle(tool_event('system_control_extension', args,
                                  transcript='Could you increase the volume?'), session)
    skills.execute.assert_awaited_once_with('system_control_extension', args)
    assert provider_result(session)['ok']


@pytest.mark.asyncio
@pytest.mark.parametrize('result', [
    '{"status":"error","error":"Desktop unavailable"}',
    '{"success":false,"error":"Action failed"}',
    '{"ok":false,"error":"Target missing"}',
    '{"status":"unverified","message":"No matching window appeared"}',
])
async def test_structured_adapter_failure_is_not_reported_as_completed(result):
    voice, skills, session = control_fixture(name='launch_app', result=result)
    await voice.handle(tool_event('launch_app', {'app': 'fixture'}, transcript='Open fixture'), session)
    response = provider_result(session)
    assert not response['ok']
    assert response['status'] != 'completed'


@pytest.mark.asyncio
async def test_uncertain_adapter_result_preserves_unknown_status():
    voice, skills, session = control_fixture(result='{"status":"unknown","error":"Connection lost after dispatch"}')
    await voice.handle(tool_event(transcript='Check the time'), session)
    assert provider_result(session)['status'] == 'unknown'


@pytest.mark.asyncio
async def test_completed_phone_turn_does_not_select_phone_for_next_command():
    voice, skills, session = control_fixture(name='phone_control', result='Phone inspected')
    await voice.handle(tool_event('phone_control', {'action': 'status'},
                                  transcript='Check my phone'), session)
    assert provider_result(session)['ok']
    voice._reply_started = True
    await voice.handle(SimpleNamespace(server_content=SimpleNamespace(turn_complete=True)), session)
    voice._reply_authorized = True
    voice.gate.accepted_turns += 1
    await voice.handle(tool_event('phone_control', {'action': 'status'},
                                  transcript='Open the browser'), session)
    assert skills.execute.await_count == 1
    assert not provider_result(session)['ok']


@pytest.mark.asyncio
async def test_spoken_acknowledgement_cannot_end_an_in_flight_action_batch():
    import asyncio

    voice, skills, session = control_fixture(name='first_action')
    skills.declarations.append({'name': 'second_action'})
    started, release = asyncio.Event(), asyncio.Event()

    async def execute(name, args):
        if name == 'first_action':
            started.set()
            await release.wait()
        return 'Verified fixture result'

    skills.execute.side_effect = execute
    batch = SimpleNamespace(function_calls=[
        SimpleNamespace(name='first_action', id='first', args={}),
        SimpleNamespace(name='second_action', id='second', args={}),
    ])
    running = asyncio.create_task(voice.handle_tools(batch, session))
    try:
        await asyncio.wait_for(started.wait(), 1)
        # A spoken preamble is not the completion of the requested actions.
        await voice.handle(SimpleNamespace(server_content=SimpleNamespace(model_turn=SimpleNamespace(parts=[
            SimpleNamespace(inline_data=SimpleNamespace(data=bytes(960)))]))), session)
        await voice.handle(SimpleNamespace(server_content=SimpleNamespace(turn_complete=True)), session)
        assert voice._reply_authorized
    finally:
        release.set()
        await running
    assert [call.args[0] for call in skills.execute.await_args_list] == ['first_action', 'second_action']


@pytest.mark.asyncio
@pytest.mark.parametrize('result', [
    '{"status":"blocked","reason":"Wrong window"}',
    '{"status":"unverified_effect","verified":false}',
    '{"status":"success","verified":false}',
    '{"status":"dispatched","reobserve_required":true}',
])
async def test_unverified_input_is_never_complete(result):
    voice, skills, session = control_fixture(result=result)
    await voice.handle(tool_event(transcript='Check the current state'), session)
    assert not provider_result(session)['ok']
    assert provider_result(session)['status'] != 'completed'
