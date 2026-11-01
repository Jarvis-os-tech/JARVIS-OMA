#!/usr/bin/env python3
"""CLI utility for managing standalone JARVIS OS releases."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from orchestration.release_manager import ReleaseManager


def main() -> int:
    parser = argparse.ArgumentParser(description="JARVIS OS Release and Rollback Manager")
    parser.add_argument("--root", help="Custom runtime root directory")
    parser.add_argument("--branch", default="JARVIS-OS", help="Target GitHub branch")

    subparsers = parser.add_subparsers(dest="command", required=True)

    # check
    subparsers.add_parser("check", help="Check for remote updates on GitHub")

    # update
    subparsers.add_parser("update", help="Fetch, compile, and activate latest GitHub release")

    # rollback
    subparsers.add_parser("rollback", help="Roll back to previous release")

    # list
    subparsers.add_parser("list", help="List all installed releases")

    # prune
    prune_parser = subparsers.add_parser("prune", help="Prune historical releases")
    prune_parser.add_argument("--keep", type=int, default=3, help="Number of releases to retain")

    args = parser.parse_args()
    rm = ReleaseManager(root_dir=args.root, branch=args.branch)

    try:
        if args.command == "check":
            info = rm.check_remote_update()
            print(json.dumps(info, indent=2))
            return 0 if not info.get("error") else 1

        elif args.command == "update":
            check = rm.check_remote_update()
            if not check.get("has_update"):
                print(f"JARVIS OS is already up to date ({check.get('current_sha', '')[:7]}).")
                return 0
            print(f"Updating JARVIS OS from {check.get('current_sha', '')[:7]} to {check.get('remote_sha', '')[:7]}...")
            meta = rm.apply_update()
            print(f"Successfully activated release: {meta.get('commit', '')[:7]} ({meta.get('message', '')})")
            return 0

        elif args.command == "rollback":
            print("Rolling back to previous release...")
            meta = rm.rollback()
            print(f"Successfully rolled back to: {meta.get('commit', '')[:7]} ({meta.get('message', '')})")
            return 0

        elif args.command == "list":
            releases = rm.list_releases()
            if not releases:
                print("No releases found.")
                return 0
            print(f"{'STATUS':<20} {'RELEASE':<26} {'COMMIT':<10} {'DATE':<22} {'MESSAGE'}")
            print("-" * 90)
            for r in releases:
                status = ""
                if r.get("is_current"):
                    status = "[ACTIVE]"
                elif r.get("is_previous"):
                    status = "[ROLLBACK TARGET]"
                else:
                    status = "[HISTORICAL]"
                commit = r.get("commit", "")[:7]
                date = r.get("created_at_iso", "")[:19]
                msg = (r.get("message") or "")[:40]
                print(f"{status:<20} {r['name']:<26} {commit:<10} {date:<22} {msg}")
            return 0

        elif args.command == "prune":
            pruned = rm.prune_releases(keep=args.keep)
            print(f"Pruned {len(pruned)} old releases: {', '.join(pruned) if pruned else 'None'}")
            return 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
