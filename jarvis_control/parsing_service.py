"""Async boundary for optional, relatively expensive temporal parsing."""
import asyncio
from datetime import datetime
import json
import os
from pathlib import Path
import sys
import tempfile

from connectors.calendar_time import DEFAULT_ZONE, calendar_zone
from jarvis_control.command_values import MAX_TEXT


async def parse_command_values(text, language='en-US', include_temporal=True,
                               anchor_datetime='', time_zone=DEFAULT_ZONE):
    if not isinstance(text, str) or not text.strip() or len(text) > MAX_TEXT:
        return {'status': 'invalid_input', 'values': [], 'candidate_only': True}
    try:
        zone = calendar_zone(time_zone)
        anchor = datetime.fromisoformat(anchor_datetime) if anchor_datetime else datetime.now(zone)
        if anchor.tzinfo is None or anchor.utcoffset() is None:
            raise ValueError('Use an explicit offset in anchor_datetime')
    except (ValueError, TypeError):
        return {'status': 'invalid_anchor_or_timezone', 'values': [], 'candidate_only': True}
    request = dict(text=text, language=language, include_temporal=include_temporal,
                   anchor=anchor.isoformat(), time_zone=zone.key)
    with tempfile.TemporaryDirectory(prefix='jarvis-parser-') as directory:
        env = {k: v for k, v in os.environ.items() if k in {'PATH', 'LANG', 'LC_ALL', 'SYSTEMROOT'}}
        env.update(HOME=directory, XDG_CONFIG_HOME=directory, XDG_DATA_HOME=directory,
                   XDG_CACHE_HOME=directory, PYTHONPATH=str(Path(__file__).resolve().parents[1]))
        process = await asyncio.create_subprocess_exec(
            sys.executable, '-m', 'jarvis_control.parsing_worker',
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL, env=env,
        )
        try:
            stdout, _ = await asyncio.wait_for(process.communicate(json.dumps(request).encode()), 10)
            if process.returncode != 0 or len(stdout) > 128 * 1024:
                raise ValueError('Parser worker failed')
            result = json.loads(stdout)
            if not isinstance(result, dict) or result.get('raw_text') != text or result.get('candidate_only') is not True:
                raise ValueError('Invalid parser reply')
            return result
        except asyncio.TimeoutError:
            return {'status': 'parser_timeout', 'values': [], 'candidate_only': True}
        except (ValueError, OSError):
            return {'status': 'parser_error', 'values': [], 'candidate_only': True}
        finally:
            if process.returncode is None:
                process.kill()
                await process.communicate()
