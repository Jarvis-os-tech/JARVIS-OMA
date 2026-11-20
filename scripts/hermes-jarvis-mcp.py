#!/usr/bin/env python3
"""Stable absolute-path entry point for Hermes's local Jarvis MCP connection."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from orchestration.mcp_server import main

if __name__ == '__main__':
    main()
