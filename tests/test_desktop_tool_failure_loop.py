from types import SimpleNamespace as NS
from unittest.mock import AsyncMock
import pytest
from voice_layer.daemon import LiveVoice
from voice_layer.playback import Playback


@pytest.mark.asyncio
@pytest.mark.parametrize('raises', [True, False])
async def test_failed_desktop_calls_stop_across_provider_batches(raises):
    execute = AsyncMock(side_effect=ValueError('application name is not unique')) if raises else AsyncMock(return_value={'ok': False, 'status': 'failed', 'error': 'launch failed'})
    voice = LiveVoice(Playback('test'), skills=NS(declarations=[{'name': 'open_application'}], execute=execute))
    voice._reply_authorized = True
    session = NS(send_tool_response=AsyncMock())
    for i in range(5):
        await voice.handle_tools(NS(function_calls=[NS(id=str(i), name='open_application', args={'name': 'file manager'})]), session)
    assert execute.await_count == 2
    response = session.send_tool_response.call_args.kwargs['function_responses'][0].response
    assert response['status'] == 'stopped'


@pytest.mark.asyncio
async def test_control_timing_preserves_result_and_hides_arguments(caplog):
    from jarvis_control.skills import ControlSkills
    from jarvis_control.config import Config
    control = ControlSkills(Config())
    try:
        with caplog.at_level('INFO', logger='jarvis_control.skills'):
            result = await control._run(lambda value: value, 'private-note-content')
        assert result == 'private-note-content'
        assert 'queue_ms=' in caplog.text and 'handler_ms=' in caplog.text
        assert 'private-note-content' not in caplog.text
    finally:
        await control.close()
