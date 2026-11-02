"""Deliver control results without interrupting speech or running result text."""
from __future__ import annotations

import asyncio
import logging
import shutil
import subprocess

log = logging.getLogger('jarvis_voice')


def desktop_notification(text: str) -> bool:
    if not shutil.which('notify-send'):
        return False
    try:
        result = subprocess.run(
            ['notify-send', '-a', 'JARVIS', '-u', 'normal', '--',
             'JARVIS background result', text[:2400]],
            capture_output=True, timeout=3,
        )
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


async def deliver_once(voice, control, notify=desktop_notification) -> None:
    events = await control.background_events()
    for event in events:
        # Muting, disconnection and private standby never start a cloud session.
        offline = (not voice.connected or voice.muted or voice.standby_active
                   or voice.standby.engaged)
        if offline:
            if not control.config.notify:
                return
            delivered = await asyncio.to_thread(notify, event['text'])
        else:
            delivered = await voice.announce_background(event['text'])
        if not delivered:
            return  # Leave the result pending for an idle turn or a later retry.
        await control.acknowledge_event(event['id'])
        if not offline:
            return  # One spoken announcement at a time.


async def monitor(voice, control, interval=2.0) -> None:
    if control is None:
        return
    while True:
        await asyncio.sleep(interval)
        try:
            await deliver_once(voice, control)
        except Exception:
            # A missing supervisor/notification bus must not disconnect audio.
            log.warning('Background result delivery failed', exc_info=True)
