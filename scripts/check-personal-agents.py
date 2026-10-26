#!/usr/bin/env python3
"""Inspect the existing Hermes gateway; optionally run one harmless round-trip."""
import argparse
import asyncio
import json
from pathlib import Path
import sys

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--smoke', action='store_true',
                        help='Send one no-tools request using the configured Hermes provider')
    parser.add_argument('--state-dir', type=Path, default=PROJECT / '.jarvis-learning' / 'task-agents')
    args = parser.parse_args()
    from orchestration.task_agents import TaskAgents
    jobs = TaskAgents(args.state_dir)
    try:
        health = await jobs.capabilities()
        print(json.dumps(health, indent=2))
        if (health.get('status') in {'error', 'unavailable'} or health.get('available') is False
                or health.get('connected') is False):
            return 1
        if args.smoke:
            job = jobs.start('Reply exactly JARVIS_HERMES_OK. Do not use tools, write files, '
                             'change settings, or contact anyone.', role='connection tester',
                             timeout_seconds=60)
            for _ in range(70):
                result = jobs.status(job['id'])
                if result.get('status') not in {'queued', 'running'}:
                    print(json.dumps(result, indent=2))
                    return (0 if result.get('status') == 'completed' and
                            result.get('output', '').strip() == 'JARVIS_HERMES_OK' else 1)
                await asyncio.sleep(1)
            print(json.dumps(await jobs.cancel(job['id']), indent=2))
            return 1
        return 0
    finally:
        await jobs.close()


if __name__ == '__main__':
    raise SystemExit(asyncio.run(main()))
