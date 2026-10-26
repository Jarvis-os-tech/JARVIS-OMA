"""Shared skill policy and bounded execution for voice and headless harnesses."""
from __future__ import annotations

import asyncio
import logging

from skills import SkillError

log = logging.getLogger('gemini_voice')


def _consume_completion(task):
    """Observe a detached cancellation result without delaying its caller."""
    if not task.cancelled():
        task.exception()


async def run_skill_call(skills, name, arguments, *, timeout=45):
    """Execute through the same policy regardless of the model transport."""
    ambiguous_system_mute = (
        name in ('set_volume', 'control_microphone') and
        arguments.get('action') == 'mute' and
        arguments.get('explicit_system_target') is not True)
    if ambiguous_system_mute:
        log.warning('Redirecting ambiguous %s mute request to JARVIS standby', name)
        result = await skills.execute('enter_standby', {})
        return {**result, 'redirected_from': name, 'system_audio_changed': False}
    if name == 'control_microphone' and arguments.get('action') in ('mute', 'toggle'):
        raise SkillError('JARVIS is not permitted to mute or toggle the system microphone')
    execution = asyncio.create_task(
        skills.execute(name, arguments), name=f'jarvis-tool-{name}')
    try:
        done, _ = await asyncio.wait({execution}, timeout=timeout)
    except asyncio.CancelledError:
        execution.cancel()
        execution.add_done_callback(_consume_completion)
        raise
    if not done:
        execution.cancel()
        execution.add_done_callback(_consume_completion)
        log.warning('Desktop skill %s exceeded the %.0fs response deadline', name, timeout)
        raise SkillError(f'{name} did not respond in time; its operation was cancelled')
    return execution.result()
