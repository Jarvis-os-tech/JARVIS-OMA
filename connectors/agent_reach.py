"""Agent-Reach sovereign connector for JARVIS OS.

Connects to the local agent-reach daemon service (http://127.0.0.1:8765)
to fetch structured content from protected and dynamic platforms.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
import httpx

log = logging.getLogger(__name__)

DEFAULT_DAEMON_URL = "http://127.0.0.1:8765"


class AgentReachError(Exception):
    def __init__(self, message: str, code: str = "ERROR", hint: Optional[str] = None):
        super().__init__(message)
        self.code = code
        self.hint = hint


class AgentReachClient:
    """Async client to the local Agent-Reach retrieval daemon."""

    def __init__(self, base_url: str = DEFAULT_DAEMON_URL, timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    async def is_available(self) -> bool:
        """Check if the Agent Reach daemon is active and responsive."""
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                res = await client.get(f"{self.base_url}/health")
                return res.status_code == 200 and res.json().get("status") == "ok"
        except Exception:
            return False

    async def read(self, url: str, backend: Optional[str] = None) -> Dict[str, Any]:
        """Read content or discussions from a URL using Agent-Reach."""
        payload: Dict[str, Any] = {"url": url, "timeout": self.timeout}
        if backend:
            payload["backend"] = backend

        try:
            async with httpx.AsyncClient(timeout=self.timeout + 5.0) as client:
                resp = await client.post(f"{self.base_url}/read", json=payload)
                if resp.status_code != 200:
                    return {
                        "ok": False,
                        "text": f"HTTP error {resp.status_code}: {resp.text[:200]}",
                        "error_code": "HTTP_ERROR",
                        "items": []
                    }
                data = resp.json()
                return self._format_response(data)
        except Exception as exc:
            return {
                "ok": False,
                "text": f"Agent Reach service error: {exc}",
                "error_code": "CONNECTION_FAILED",
                "items": []
            }

    async def search(self, channel: str, query: str, limit: int = 5, backend: Optional[str] = None) -> Dict[str, Any]:
        """Search a specific platform channel."""
        payload: Dict[str, Any] = {
            "channel": channel,
            "query": query,
            "limit": limit,
            "timeout": self.timeout
        }
        if backend:
            payload["backend"] = backend

        try:
            async with httpx.AsyncClient(timeout=self.timeout + 5.0) as client:
                resp = await client.post(f"{self.base_url}/search", json=payload)
                if resp.status_code != 200:
                    return {
                        "ok": False,
                        "text": f"HTTP error {resp.status_code}: {resp.text[:200]}",
                        "error_code": "HTTP_ERROR",
                        "items": []
                    }
                data = resp.json()
                return self._format_response(data)
        except Exception as exc:
            return {
                "ok": False,
                "text": f"Agent Reach service error: {exc}",
                "error_code": "CONNECTION_FAILED",
                "items": []
            }

    async def transcript(self, url: str) -> Dict[str, Any]:
        """Extract transcript or subtitles for a video or podcast."""
        payload: Dict[str, Any] = {"url": url, "timeout": self.timeout + 30.0}

        try:
            async with httpx.AsyncClient(timeout=self.timeout + 35.0) as client:
                resp = await client.post(f"{self.base_url}/transcript", json=payload)
                if resp.status_code != 200:
                    return {
                        "ok": False,
                        "text": f"HTTP error {resp.status_code}: {resp.text[:200]}",
                        "error_code": "HTTP_ERROR",
                        "items": []
                    }
                data = resp.json()
                return self._format_response(data)
        except Exception as exc:
            return {
                "ok": False,
                "text": f"Agent Reach service error: {exc}",
                "error_code": "CONNECTION_FAILED",
                "items": []
            }

    def _format_response(self, data: Dict[str, Any]) -> Dict[str, Any]:
        if not data.get("ok", True):
            err = data.get("error", {})
            return {
                "ok": False,
                "text": f"[{err.get('code', 'ERROR')}] {err.get('message', 'Failed')}",
                "error_code": err.get("code", "ERROR"),
                "hint": err.get("hint"),
                "items": []
            }

        items = data.get("items", [])
        formatted_lines = []
        for i, item in enumerate(items, 1):
            title = item.get("title") or "Untitled"
            url = item.get("url") or ""
            author = item.get("author") or ""
            text = item.get("text") or ""
            formatted_lines.append(f"### {i}. {title}")
            meta = []
            if author:
                meta.append(f"Author: {author}")
            if url:
                meta.append(f"URL: {url}")
            if meta:
                formatted_lines.append(" | ".join(meta))
            if text:
                formatted_lines.append(text[:3000] + ("..." if len(text) > 3000 else ""))
            formatted_lines.append("")

        full_text = "\n".join(formatted_lines).strip() or "No content items returned."
        return {
            "ok": True,
            "text": full_text,
            "items": items,
            "raw": data
        }


# Singleton client instance
_default_client: Optional[AgentReachClient] = None

def get_client() -> AgentReachClient:
    global _default_client
    if _default_client is None:
        _default_client = AgentReachClient()
    return _default_client
