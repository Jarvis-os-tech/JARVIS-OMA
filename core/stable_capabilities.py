"""Existing capability services, isolated from the recovered audio transport."""
import asyncio
import logging
import os
from pathlib import Path

from skills import SkillError

log = logging.getLogger('gemini_voice')


def read_visual_frame(path):
    """Read only a bounded image returned by a user-requested visual tool."""
    if not isinstance(path, str):
        return None
    try:
        candidate = Path(path).resolve()
        roots = [Path('/tmp'), Path(os.getenv('XDG_RUNTIME_DIR') or '/tmp')]
        if not any(candidate.is_relative_to(root) for root in roots):
            return None
        if candidate.suffix.lower() not in ('.jpg', '.jpeg', '.png'):
            return None
        if candidate.stat().st_uid != os.getuid():
            return None
        with candidate.open('rb') as stream:
            data = stream.read(2_000_001)
        return data if 0 < len(data) <= 2_000_000 else None
    except OSError:
        return None


class CapabilityServices:
    def __init__(self, skills, config):
        self.skills = skills
        self.config = config
        self.memory_ready = False

    def reject_streaming(self, mode):
        self.skills.vision_mode = 'off'
        if mode != 'off':
            raise SkillError('Continuous streaming is unavailable; use on-demand screen or camera tools')

    async def context(self):
        if self.skills is None or not self.config.memory.enabled:
            return ''
        try:
            await asyncio.wait_for(self.skills.memory_call('start'), 3)
            context = await asyncio.wait_for(self.skills.memory_call('context'), 3)
            self.memory_ready = True
            return context
        except Exception as error:
            self.memory_ready = False
            log.warning('Memory context unavailable: %s', type(error).__name__)
            return ''

    async def run(self):
        """Advance authorized durable jobs without blocking voice or speaking unasked."""
        while True:
            try:
                if self.config.proactive.enabled or self.skills.proactive_continuous_requested:
                    runtime = await self.skills.get_proactive(activate=False)
                    await runtime.tick()
            except Exception as error:
                log.warning('Background capability tick unavailable: %s', type(error).__name__)
            if (self.memory_ready and self.config.memory.obsidian_auto_sync
                    and self.config.memory.obsidian_vault):
                try:
                    await self.skills.memory_call('sync_obsidian', force=False)
                except Exception as error:
                    log.warning('Memory vault sync unavailable: %s', type(error).__name__)
            await asyncio.sleep(self.config.proactive.poll_interval_seconds)
