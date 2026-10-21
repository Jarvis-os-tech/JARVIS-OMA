"""Standalone entry point for the Universal Memory MCP server."""

from __future__ import annotations

def main() -> None:
    """Execute the vendored MCP server without importing JARVIS-OMA."""
    from .mcp_server import main as mcp_main

    mcp_main()


if __name__ == "__main__":
    main()
