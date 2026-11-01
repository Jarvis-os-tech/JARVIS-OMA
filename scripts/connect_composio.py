#!/usr/bin/env python3
"""Composio CLI helper for JARVIS OS.

Enables connecting toolkits, checking connection status, and running safe tests.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from connectors import composio


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest='command', required=True)

    # status
    status_parser = subparsers.add_parser('status', help='Check status of a toolkit')
    status_parser.add_argument('toolkit', help='Toolkit slug (e.g. github, gmail, slack, notion)')
    status_parser.add_argument('--user-id', default=composio.DEFAULT_USER_ID, help='User identifier')

    # connect
    connect_parser = subparsers.add_parser('connect', help='Generate connection link for a toolkit')
    connect_parser.add_argument('toolkit', help='Toolkit slug (e.g. github, gmail, slack, notion)')
    connect_parser.add_argument('--user-id', default=composio.DEFAULT_USER_ID, help='User identifier')
    connect_parser.add_argument('--no-browser', action='store_true', help='Do not launch web browser automatically')

    # search
    search_parser = subparsers.add_parser('search', help='Search for tools in Composio')
    search_parser.add_argument('query', help='Search query (e.g. "github", "email", "weather")')
    search_parser.add_argument('--user-id', default=composio.DEFAULT_USER_ID, help='User identifier')

    # execute
    exec_parser = subparsers.add_parser('execute', help='Execute a Composio tool')
    exec_parser.add_argument('tool_slug', help='Exact tool slug (e.g. GITHUB_GET_A_REPOSITORY)')
    exec_parser.add_argument('--args', default='{}', help='JSON-encoded arguments string')
    exec_parser.add_argument('--user-id', default=composio.DEFAULT_USER_ID, help='User identifier')

    args = parser.parse_args()

    if args.command == 'status':
        result = composio.get_connection_status(args.toolkit, user_id=args.user_id)
        print(json.dumps(result, indent=2))
        return 0 if result.get('connected') else 1

    if args.command == 'connect':
        result = composio.authorize(args.toolkit, user_id=args.user_id, open_in_browser=not args.no_browser)
        print(json.dumps(result, indent=2))
        if result.get('redirect_url'):
            print(f"\nPlease visit the following link to authenticate {args.toolkit}:\n{result['redirect_url']}")
        return 0 if result.get('success') else 1

    if args.command == 'search':
        result = composio.search_tools(args.query, user_id=args.user_id)
        print(json.dumps(result, indent=2))
        return 0 if result.get('success') else 1

    if args.command == 'execute':
        try:
            parsed_args = json.loads(args.args)
        except json.JSONDecodeError as exc:
            print(f"Invalid JSON in --args: {exc}", file=sys.stderr)
            return 1
        result = composio.execute_tool(args.tool_slug, arguments=parsed_args, user_id=args.user_id)
        print(json.dumps(result, indent=2))
        return 0 if result.get('success') else 1

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
