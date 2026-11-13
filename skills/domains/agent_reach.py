"""Agent Reach domain adapters for JARVIS OS.

Enables JARVIS OS DesktopSkills to read structured content,
search across platforms, extract video/podcast transcripts, and check status.
"""
from __future__ import annotations

from typing import Any, Dict, Optional
from connectors.agent_reach import get_client
from skills.errors import SkillError


ADAPTERS = {
    "agent_reach.search": "_adapter_reach_search",
    "agent_reach.read": "_adapter_reach_read",
    "agent_reach.transcript": "_adapter_reach_transcript",
    "agent_reach.status": "_adapter_reach_status",
}

ADAPTER_COMMANDS = {
    "agent_reach.search": (),
    "agent_reach.read": (),
    "agent_reach.transcript": (),
    "agent_reach.status": (),
}


class AgentReachDomain:
    async def _adapter_reach_search(
        self, channel: str, query: str, limit: int = 5, backend: Optional[str] = None
    ) -> Dict[str, Any]:
        """Search a specific platform channel via Agent Reach."""
        if not channel or not channel.strip():
            raise SkillError("Platform channel must be specified.")
        if not query or not query.strip():
            raise SkillError("Search query must be specified.")
        client = get_client()
        res = await client.search(channel=channel.strip(), query=query.strip(), limit=limit, backend=backend)
        if not res.get("ok", True):
            raise SkillError(res.get("text") or "Reach search failed")
        return res

    async def _adapter_reach_read(
        self, url: str, backend: Optional[str] = None
    ) -> Dict[str, Any]:
        """Read content or discussions from a URL using Agent-Reach."""
        if not url or not url.strip():
            raise SkillError("URL must be specified.")
        client = get_client()
        res = await client.read(url=url.strip(), backend=backend)
        if not res.get("ok", True):
            raise SkillError(res.get("text") or "Reach read failed")
        return res

    async def _adapter_reach_transcript(self, url: str) -> Dict[str, Any]:
        """Extract transcript or subtitles for a video or podcast."""
        if not url or not url.strip():
            raise SkillError("URL must be specified.")
        client = get_client()
        res = await client.transcript(url=url.strip())
        if not res.get("ok", True):
            raise SkillError(res.get("text") or "Reach transcript extraction failed")
        return res

    async def _adapter_reach_status(self) -> Dict[str, Any]:
        """Check status and available channels of Agent Reach."""
        client = get_client()
        return await client.status()
