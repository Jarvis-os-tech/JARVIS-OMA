#!/usr/bin/env python3
"""Launch Google and GitHub read-only checks concurrently; print status only."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from skills import DesktopSkills


async def probe(skills, service, tool, arguments):
    try:
        result = await asyncio.wait_for(skills.execute(tool, arguments), timeout=40)
        checks = {'service': service, 'connected': result.get('success', False),
                  'setup_required': bool(result.get('setup_required'))}
        if not checks['connected']:
            checks['error'] = result.get('error', 'Connector did not report success')
        return checks
    except asyncio.TimeoutError:
        return {'service': service, 'connected': False, 'error': 'Connection check timed out'}
    except Exception:
        return {'service': service, 'connected': False, 'error': 'Connector check failed; values withheld'}


async def check():
    skills = DesktopSkills()
    try:
        results = await asyncio.gather(
            probe(skills, 'google', 'gmail_list_labels', {}),
            probe(skills, 'github', 'github_connection_status', {}))
        print(json.dumps({'checks': results}, indent=2))
        return 0 if all(item['connected'] for item in results) else 1
    finally:
        await skills.close_agent_jobs()


if __name__ == '__main__':
    raise SystemExit(asyncio.run(check()))
