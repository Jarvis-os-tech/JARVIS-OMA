"""YouTube Knowledge Brain domain adapter for JARVIS OS.

Enables JARVIS OS DesktopSkills and Gemini Live to query watched videos,
extract notes, search transcripts, and inspect topics.
"""
from __future__ import annotations

from typing import Any, Dict, Optional
from connectors.yt_brain import get_client
from skills.errors import SkillError


# Mirrors the five stages defined by yt_brain/main.py in Jarvis YouTube Brain.
AGENT_NAMES = (
    "History Classifier",
    "Transcript Fetcher",
    "Video Summarizer",
    "Note Classifier",
    "Final Reviewer",
)


ADAPTERS = {
    "yt_brain.search": "_adapter_yt_brain_search",
    "yt_brain.get": "_adapter_yt_brain_get",
    "yt_brain.topics": "_adapter_yt_brain_topics",
    "yt_brain.status": "_adapter_yt_brain_status",
}

ADAPTER_COMMANDS = {
    "yt_brain.search": (),
    "yt_brain.get": (),
    "yt_brain.topics": (),
    "yt_brain.status": (),
}


class YtBrainDomain:
    """Domain adapter for YouTube Knowledge Brain in JARVIS OS."""

    async def _adapter_yt_brain_search(self, query: str, limit: int = 5) -> Dict[str, Any]:
        """Search watched video notes and transcripts."""
        if not query or not query.strip():
            raise SkillError("Search query must be specified.")
        client = get_client()
        res = await client.search(query=query.strip(), limit=limit)
        if not res.get("ok", True):
            raise SkillError(res.get("error") or "YouTube brain search failed")
        return res

    async def _adapter_yt_brain_get(
        self, video_id: Optional[str] = None, path: Optional[str] = None
    ) -> Dict[str, Any]:
        """Retrieve full note content by video_id or path."""
        if not video_id and not path:
            raise SkillError("Must specify either video_id or path.")
        client = get_client()
        res = await client.get(video_id=video_id, path=path)
        if not res.get("ok", True):
            raise SkillError(res.get("error") or "YouTube note retrieval failed")
        return res

    async def _adapter_yt_brain_topics(self) -> Dict[str, Any]:
        """List topics and categories in YouTube brain."""
        client = get_client()
        res = await client.topics()
        if not res.get("ok", True):
            raise SkillError(res.get("error") or "YouTube brain topics failed")
        return res

    async def _adapter_yt_brain_status(self) -> Dict[str, Any]:
        """Check operational status of YouTube brain."""
        client = get_client()
        return await client.status()
