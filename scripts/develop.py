#!/usr/bin/env python3
"""Run and inspect JARVIS capability-development proposals without voice/audio."""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
import signal
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from orchestration.agent_orchestrator import AGENTS, AgentOrchestrator
from orchestration.evolution import EvolutionManager, EvolutionError
from proactive.control import AutonomyControl
from jarvis_memory.paths import get_config_dir
from core.config import load_config


async def run(args):
    if args.command in ('list', 'status'):
        manager = EvolutionManager(None, args.state_dir, read_only=True)
        return manager.list_jobs() if args.command == 'list' else manager.status(args.job_id)
    cfg = load_config()
    memory_root = Path(cfg.memory.path).expanduser() if cfg.memory.path else get_config_dir()
    control = AutonomyControl(memory_root / 'proactive/control.db')
    orchestrator = AgentOrchestrator()
    manager = EvolutionManager(orchestrator, args.state_dir,
                               can_run=lambda: control.get_state().can_run)
    loop = asyncio.get_running_loop()
    task = asyncio.current_task()
    loop.add_signal_handler(signal.SIGTERM, task.cancel)
    try:
        started = await manager.start(args.goal, str(Path(args.workspace).resolve()), args.agent)
        key = started['job']['id']
        print(json.dumps({'job_id': key, 'state': 'queued'}), flush=True)
        try:
            await asyncio.shield(manager.workers[key])
        except asyncio.CancelledError:
            await manager.cancel(key)
        return manager.status(key)
    finally:
        loop.remove_signal_handler(signal.SIGTERM)
        await manager.close()
        await orchestrator.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state-dir', help='Override private development state directory')
    sub = parser.add_subparsers(dest='command', required=True)
    start = sub.add_parser('start', help='Run in foreground; Ctrl+C cancels and keeps evidence')
    start.add_argument('goal')
    start.add_argument('--workspace', default=str(Path(__file__).resolve().parents[1]))
    start.add_argument('--agent', choices=AGENTS, default='codex')
    sub.add_parser('list', help='List persisted jobs without interrupting active work')
    status = sub.add_parser('status')
    status.add_argument('job_id')
    args = parser.parse_args()
    try:
        result = asyncio.run(run(args))
    except (EvolutionError, OSError, ValueError) as error:
        print(json.dumps({'status': 'error', 'error': str(error)}), file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0 if args.command != 'start' or result['job']['state'] == 'ready_for_review' else 1


if __name__ == '__main__':
    raise SystemExit(main())
