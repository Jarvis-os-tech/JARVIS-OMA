"""Prevent unsolicited client turns from preempting a live conversation."""
import asyncio
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock

import pytest
from google.genai import types

from core.agent import LiveVoice
from core.config import Config


@pytest.mark.asyncio
@pytest.mark.parametrize('busy', ['listening', 'thinking', 'pending', 'muted', 'tool'])
async def test_notice_waits_for_conversation_and_playback_to_finish(busy):
    engine = NS(speaking=False, muted=busy == 'muted')
    voice = LiveVoice(engine)
    if busy in ('listening', 'thinking'):
        voice.publish_lifecycle_state(busy)
        voice._speculative_thinking = busy == 'thinking'
    voice._request_pending = busy == 'pending'
    if busy == 'tool':
        voice.tool_tasks['work'] = object()
    session = NS(send_client_content=AsyncMock())
    voice._queue_notice('Background task completed')
    task = asyncio.create_task(voice.send_notifications(session))
    try:
        await asyncio.sleep(.12)
        session.send_client_content.assert_not_awaited()
        voice._request_pending = False
        voice.tool_tasks.clear()
        engine.muted = False
        voice.publish_lifecycle_state('idle')
        async with asyncio.timeout(1):
            while not session.send_client_content.await_count:
                await asyncio.sleep(.01)
        session.send_client_content.assert_awaited_once()
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


@pytest.mark.asyncio
async def test_slow_greeting_cannot_interrupt_user_who_started_talking():
    config = Config()
    config.agent.greeting_prompt = 'A welcome greeting'
    voice = LiveVoice(None, config=config)
    session = NS(send_client_content=AsyncMock())
    await voice.send_lock.acquire()
    task = asyncio.create_task(voice.greet(session))
    await asyncio.sleep(0)
    await voice.handle(types.LiveServerMessage(server_content=types.LiveServerContent(
        input_transcription=types.Transcription(text='Continue our conversation'))))
    voice.send_lock.release()
    await asyncio.wait_for(task, 1)
    session.send_client_content.assert_not_awaited()
    assert voice.has_greeted


@pytest.mark.asyncio
async def test_provider_interruption_is_counted_without_transcript_logging():
    voice = LiveVoice(None)
    await voice.handle(types.LiveServerMessage(
        server_content=types.LiveServerContent(interrupted=True)))
    assert voice.provider_interruptions == 1
