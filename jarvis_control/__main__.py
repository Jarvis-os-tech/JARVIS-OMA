"""CLI entry point for JARVIS OS Control & Information Retrieval Core."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from jarvis_voice.config import control_config, load, load_env
from .discovery import TOPICS, lookup
from .tools import Executor, tools_for


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="jarvis-control",
        description="JARVIS OS Control & Information Retrieval CLI",
    )
    subparsers = parser.add_subparsers(dest="command")

    # list
    subparsers.add_parser("list", help="List all available tools")

    # map / discovery
    map_parser = subparsers.add_parser("map", help="Query system architecture and discovery")
    map_parser.add_argument("topic", nargs="?", default="overview", choices=TOPICS, help="Topic to explore")
    map_parser.add_argument("query", nargs="?", default="", help="Search query")
    map_parser.add_argument("--offset", type=int, default=0, help="Pagination offset")
    map_parser.add_argument("--limit", type=int, default=12, help="Result limit")

    # call
    call_parser = subparsers.add_parser("call", help="Execute a control or retrieval tool")
    call_parser.add_argument("tool", help="Tool name")
    call_parser.add_argument("args", nargs="?", default="{}", help="Tool arguments as JSON string")
    call_parser.add_argument("--dry-run", action="store_true", help="Preview without executing")

    # ground
    ground_parser = subparsers.add_parser("ground", help="Background search grounding using Google")
    ground_parser.add_argument("query", help="Query to ground with search")

    # doctor
    doctor = subparsers.add_parser("doctor", help="Check JARVIS dependencies without using providers or devices")
    doctor.add_argument('--json', action='store_true')

    vision = subparsers.add_parser('vision', help='On-demand physical camera preview and inspection')
    vision.add_argument('action', choices=['start', 'inspect', 'status', 'stop', 'quit'])
    vision.add_argument('question', nargs='*')
    vision.add_argument('--region', nargs=4, type=int)

    task = subparsers.add_parser('task', help='Manage durable background work')
    task.add_argument('--dry-run', action='store_true')
    actions = task.add_subparsers(dest='task_action', required=True)
    submit = actions.add_parser('submit', help='Submit a JSON specification file')
    submit.add_argument('spec', type=Path)
    for action in ('list', 'status', 'read', 'cancel', 'resume'):
        command = actions.add_parser(action)
        if action != 'list':
            command.add_argument('task_id')
        if action == 'read':
            command.add_argument('path')
            command.add_argument('--offset', type=int, default=0)
        if action == 'resume':
            command.add_argument('--guidance', default='')

    say = subparsers.add_parser('say', help='Send a typed request to the configured one-shot planner')
    say.add_argument('text', nargs='+')
    say.add_argument('--dry-run', action='store_true')
    say.add_argument('--no-confirm', action='store_true', help='Leave gated actions unexecuted')

    args = parser.parse_args(argv)
    try:
        voice_config = load()
        config = control_config(voice_config)
        load_env(config.api_key_env)
        load_env(config.vision_api_key_env or config.api_key_env)
    except (ValueError, OSError) as error:
        print(f'Configuration error: {error}', file=sys.stderr)
        return 1
    if getattr(args, "dry_run", False):
        config.dry_run = True

    if args.command == "list":
        tools = tools_for(config)
        print(f"Available tools ({len(tools)}):")
        for t in tools:
            print(f"  - {t['name']}: {t['description'][:80]}...")
        return 0

    elif args.command == "map":
        ok, res = lookup(args.topic, args.query, limit=args.limit, offset=args.offset)
        print(res)
        return 0 if ok else 1

    elif args.command == "call":
        try:
            call_args = json.loads(args.args)
        except Exception as e:
            print(f"Invalid JSON args: {e}", file=sys.stderr)
            return 1
        if not isinstance(call_args, dict):
            print('Tool arguments must be a JSON object', file=sys.stderr)
            return 1
        if args.tool not in {tool['name'] for tool in tools_for(config)}:
            print(f'Tool is not enabled: {args.tool}', file=sys.stderr)
            return 1
        executor = Executor(config)
        res = executor.call(args.tool, call_args)
        print(res.as_tool_result())
        return 0 if res.ok else 1

    elif args.command == "ground":
        import asyncio
        from .grounding import background_google_grounding, format_grounding_result
        res = asyncio.run(background_google_grounding(args.query))
        print(format_grounding_result(res))
        return 0 if res.get("ok") else 1

    elif args.command == "doctor":
        from .diagnostics import report
        result = report(voice_config, config)
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print('JARVIS diagnostics (no audio, camera or model calls)')
            for name, check in result['checks'].items():
                print(f"{'PASS' if check['ok'] else 'MISSING'}: {name}: {check['detail']}")
        return 0 if result['ok'] else 1

    elif args.command == 'vision':
        from .vision import VisionClient
        try:
            value = VisionClient(config).call(args.action, ' '.join(args.question), args.region)
            print(json.dumps(value, indent=2))
            return 0 if value.get('ok', True) else 1
        except (ValueError, RuntimeError, OSError) as error:
            print(f'Vision: {error}', file=sys.stderr)
            return 1

    elif args.command == 'task':
        if not config.tasks_enabled and args.task_action in {'submit', 'resume'}:
            print('Task workers are disabled in JARVIS configuration', file=sys.stderr)
            return 1
        from .cli import cmd_task
        return cmd_task(args, config)

    elif args.command == 'say':
        from .cli import cmd_say
        return cmd_say(args, config)

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
