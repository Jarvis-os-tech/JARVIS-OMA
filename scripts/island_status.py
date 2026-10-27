#!/usr/bin/env python3
"""Bounded, content-free daemon telemetry for the desktop island."""
from __future__ import annotations

import asyncio
import json
import math
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.orbit_status import status


def snapshot(payload: dict) -> dict:
    """Forward only UI metadata, never transcripts, memory, or tool arguments."""
    state = str(payload.get('state', 'offline')).lower()
    connection = str(payload.get('connection_state', state)).lower()
    waiting = connection in ('connecting', 'reconnecting')
    online = not waiting and connection not in ('offline', 'error') and payload.get('status') != 'offline'
    muted = bool(payload.get('muted', False)) if online else False
    rms = payload.get('microphone_rms')
    valid_rms = (isinstance(rms, (int, float)) and not isinstance(rms, bool)
                 and math.isfinite(rms) and rms >= 0 and online)
    jobs = payload.get('active_jobs', 0)
    return {
        'state': connection if waiting else state if online else 'offline',
        'activity': str(payload.get('activity') or state.title())[:160] if online else
                    ('Reconnecting to JARVIS' if connection == 'reconnecting' else
                     'Connecting to JARVIS' if waiting else 'JARVIS is offline'),
        'connection_state': connection if connection in ('connecting', 'reconnecting', 'listening', 'speaking', 'standby') else
                            ('listening' if online else 'offline'),
        'connection_revision': payload.get('connection_revision') if type(payload.get('connection_revision')) is int and
                               0 <= payload['connection_revision'] <= 2**53 else 0,
        'muted': muted,
        'standby': bool(payload.get('standby', False)) if online else False,
        'model': str(payload.get('model') or '')[:100] if online else '',
        'active_jobs': min(999, max(0, jobs)) if isinstance(jobs, int) and not isinstance(jobs, bool) and online else 0,
        'microphone_rms': min(1.0, float(rms)) if valid_rms and not muted else 0.0,
        'level_available': valid_rms and not muted,
        'vision_mode': str(payload.get('vision_mode') or 'off')[:20] if online else 'off',
    }


async def stream(fetch=status, emit=print, sleep=asyncio.sleep) -> None:
    previous = None
    while True:
        current = snapshot(await fetch())
        if current != previous:
            emit(json.dumps(current, separators=(',', ':'), allow_nan=False), flush=True)
            previous = current
        active = current['state'] in ('listening', 'speaking', 'ducked', 'barged_in')
        await sleep(0.25 if active else 1.0)


if __name__ == '__main__':
    try:
        asyncio.run(stream())
    except KeyboardInterrupt:
        pass
