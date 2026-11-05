#!/usr/bin/env python3
"""Composio CLI helper for JARVIS OS.

Enables connecting platforms, checking connection status, running actions, and managing integrations.
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
    status_parser = subparsers.add_parser('status', help='Check status of a platform or toolkit')
    status_parser.add_argument('platform', help='Platform name or slug (e.g. github, gmail, slack, notion)')
    status_parser.add_argument('--user-id', default=composio.DEFAULT_USER_ID, help='User identifier')

    # connect
    connect_parser = subparsers.add_parser('connect', help='Connect to a platform with automatic browser auth')
    connect_parser.add_argument('platform', help='Platform name or slug (e.g. github, gmail, slack, notion)')
    connect_parser.add_argument('--reconnect', action='store_true', help='Force reconnection even if already active')
    connect_parser.add_argument('--no-browser', action='store_true', help='Do not open browser automatically')
    connect_parser.add_argument('--user-id', default=composio.DEFAULT_USER_ID, help='User identifier')

    # list
    list_parser = subparsers.add_parser('list', help='List all connected platforms')
    list_parser.add_argument('--user-id', default=composio.DEFAULT_USER_ID, help='User identifier')

    # disconnect
    dc_parser = subparsers.add_parser('disconnect', help='Disconnect a platform')
    dc_parser.add_argument('platform', help='Platform name to disconnect')
    dc_parser.add_argument('--user-id', default=composio.DEFAULT_USER_ID, help='User identifier')

    # action
    action_parser = subparsers.add_parser('action', help='Execute a platform action')
    action_parser.add_argument('platform', help='Platform name (e.g. github, slack, notion)')
    action_parser.add_argument('action_desc', help='Action description (e.g. "list my repositories", "get user profile")')
    action_parser.add_argument('--args', default='{}', help='JSON-encoded arguments dictionary')
    action_parser.add_argument('--user-id', default=composio.DEFAULT_USER_ID, help='User identifier')

    # search
    search_parser = subparsers.add_parser('search', help='Search for tools in Composio')
    search_parser.add_argument('query', help='Search query (e.g. "github", "email", "weather")')
    search_parser.add_argument('--user-id', default=composio.DEFAULT_USER_ID, help='User identifier')

    # execute
    exec_parser = subparsers.add_parser('execute', help='Execute a Composio tool slug directly')
    exec_parser.add_argument('tool_slug', help='Exact tool slug (e.g. GITHUB_GET_A_REPOSITORY)')
    exec_parser.add_argument('--args', default='{}', help='JSON-encoded arguments string')
    exec_parser.add_argument('--user-id', default=composio.DEFAULT_USER_ID, help='User identifier')

    args = parser.parse_args()

    if args.command == 'status':
        result = composio.get_connection_status(args.platform, user_id=args.user_id)
        print(json.dumps(result, indent=2))
        return 0 if result.get('connected') else 1

    if args.command == 'connect':
        result = composio.connect_platform(
            args.platform,
            user_id=args.user_id,
            reconnect=args.reconnect,
            open_in_browser=not args.no_browser,
        )
        print(json.dumps(result, indent=2))
        if result.get('redirect_url') and not result.get('browser_opened'):
            print(f"\nPlease visit the following link to authenticate {result.get('toolkit')}:\n{result['redirect_url']}")
        return 0 if result.get('success') else 1

    if args.command == 'list':
        result = composio.list_connected_platforms(user_id=args.user_id)
        print(json.dumps(result, indent=2))
        return 0 if result.get('success') else 1

    if args.command == 'disconnect':
        result = composio.disconnect_platform(args.platform, user_id=args.user_id)
        print(json.dumps(result, indent=2))
        return 0 if result.get('success') else 1

    if args.command == 'action':
        try:
            parsed_args = json.loads(args.args)
        except json.JSONDecodeError as exc:
            print(f"Invalid JSON in --args: {exc}", file=sys.stderr)
            return 1
        result = composio.execute_platform_action(
            args.platform,
            args.action_desc,
            arguments=parsed_args,
            user_id=args.user_id,
        )
        print(json.dumps(result, indent=2))
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
