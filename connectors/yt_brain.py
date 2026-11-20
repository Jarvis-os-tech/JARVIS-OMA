"""YouTube Knowledge Brain connector for JARVIS OS.

Connects to the local yt-brain agent bus service or falls back directly
to the SQLite knowledge base (~/jarvis-yt-brain/yt_brain/kb.sqlite).
"""
from __future__ import annotations

import asyncio
import logging
import os
import sqlite3
import sys
from contextlib import closing
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

log = logging.getLogger(__name__)

YT_BRAIN_ROOT = Path(os.environ.get("YT_BRAIN_ROOT", Path.home() / "jarvis-yt-brain"))
BUS_SOCKET = Path(os.environ.get("JARVIS_BUS_SOCKET", YT_BRAIN_ROOT / "run" / "agent_bus.sock"))
KB_SQLITE = YT_BRAIN_ROOT / "yt_brain" / "kb.sqlite"
MAX_SEARCH_RESULTS = 50
MAX_NOTE_CHARS = 50_000


def _connect_readonly(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)


def _bounded_content(content: str) -> str:
    if not isinstance(content, str):
        return ""
    if len(content) > MAX_NOTE_CHARS:
        return content[:MAX_NOTE_CHARS] + "\n[Content truncated]"
    return content


class YtBrainError(Exception):
    def __init__(self, message: str, code: str = "ERROR"):
        super().__init__(message)
        self.code = code


class YtBrainClient:
    """Client for personal YouTube Brain queries via agent bus or direct SQLite."""

    def __init__(self, socket_path: Path = BUS_SOCKET, kb_path: Path = KB_SQLITE):
        self.socket_path = socket_path
        self.kb_path = kb_path

    async def _bus_request(self, topic: str, payload: dict, timeout: float = 3.0) -> Optional[dict]:
        """Try querying the agent bus if socket exists."""
        if not self.socket_path.exists():
            return None
        try:
            core_engine_path = str(YT_BRAIN_ROOT / "core_engine")
            if core_engine_path not in sys.path:
                sys.path.insert(0, core_engine_path)
            from core_engine import AgentBusClient

            async with asyncio.timeout(timeout):
                async with AgentBusClient(
                    agent_id=f"jarvis-voice-client-{uuid4().hex}",
                    socket_path=str(self.socket_path),
                ) as client:
                    reply = await client.request(topic, payload, timeout=timeout)
                    if reply and reply.type in ("task.complete", "reply") and isinstance(reply.payload, dict):
                        return reply.payload
        except Exception as exc:
            log.debug("AgentBus query '%s' failed, falling back to SQLite: %s", topic, exc)
        return None

    async def search(self, query: str, limit: int = 5) -> Dict[str, Any]:
        """Search watched video notes and transcripts."""
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
            return {"ok": False, "error": "limit must be a positive integer", "results": []}
        limit = min(limit, MAX_SEARCH_RESULTS)
        bus_res = await self._bus_request("yt-brain.search", {"query": query, "limit": limit})
        if bus_res is not None:
            if bus_res.get("ok") is False:
                return bus_res
            return {"ok": True, "results": bus_res.get("results", []), "query": query, "source": "agent_bus"}

        # Direct SQLite fallback
        return await asyncio.to_thread(self._direct_search, query, limit)

    def _direct_search(self, query: str, limit: int = 5) -> Dict[str, Any]:
        if not self.kb_path.exists():
            return {"ok": False, "error": f"KB not found at {self.kb_path}", "results": []}

        try:
            # Escape FTS5 special characters
            clean_q = " ".join(f'"{token}"' for token in query.replace('"', "").split() if token)
            if not clean_q:
                clean_q = f'"{query.replace(chr(34), "")}"'

            with closing(_connect_readonly(self.kb_path)) as conn:
                cur = conn.cursor()
                try:
                    rows = cur.execute(
                        """
                        SELECT n.title, n.url, n.watched, n.path, n.video_id,
                               snippet(notes_fts, 2, '<b>', '</b>', '...', 32) as snippet
                        FROM notes_fts f
                        JOIN notes n ON n.video_id = f.video_id
                        WHERE notes_fts MATCH ?
                        ORDER BY rank
                        LIMIT ?
                        """,
                        (clean_q, limit),
                    ).fetchall()
                except sqlite3.OperationalError:
                    # Fallback to simple LIKE search if FTS query syntax error occurs
                    rows = cur.execute(
                        """
                        SELECT title, url, watched, path, video_id, ''
                        FROM notes
                        WHERE title LIKE ? OR topic LIKE ?
                        ORDER BY watched DESC
                        LIMIT ?
                        """,
                        (f"%{query}%", f"%{query}%", limit),
                    ).fetchall()

                results = [
                    {
                        "title": r[0],
                        "url": r[1],
                        "watched": r[2],
                        "path": r[3],
                        "video_id": r[4],
                        "snippet": r[5] or "",
                    }
                    for r in rows
                ]
                return {"ok": True, "results": results, "query": query, "source": "sqlite_fallback"}
        except Exception as exc:
            log.exception("Direct search failed: %s", exc)
            return {"ok": False, "error": str(exc), "results": []}

    async def get(self, video_id: Optional[str] = None, path: Optional[str] = None) -> Dict[str, Any]:
        """Get full note content and metadata for a video."""
        bus_res = await self._bus_request("yt-brain.get", {"video_id": video_id, "path": path})
        if bus_res is not None:
            if bus_res.get("ok") is False:
                return bus_res
            if not bus_res.get("meta"):
                return {"ok": False, "error": "Note not found"}
            content = _bounded_content(bus_res.get("content", ""))
            if not content:
                return {"ok": False, "error": "Note file not found"}
            return {"ok": True, "content": content, "meta": bus_res["meta"]}

        return await asyncio.to_thread(self._direct_get, video_id, path)

    def _direct_get(self, video_id: Optional[str] = None, path: Optional[str] = None) -> Dict[str, Any]:
        if not self.kb_path.exists():
            return {"ok": False, "error": f"KB not found at {self.kb_path}"}

        try:
            with closing(_connect_readonly(self.kb_path)) as conn:
                cur = conn.cursor()
                if video_id:
                    row = cur.execute(
                        "SELECT title, url, watched, path, video_id, topic FROM notes WHERE video_id = ?",
                        (video_id,),
                    ).fetchone()
                else:
                    row = cur.execute(
                        "SELECT title, url, watched, path, video_id, topic FROM notes WHERE path = ?",
                        (path,),
                    ).fetchone()

            if not row:
                return {"ok": False, "error": "Note not found"}

            meta = {
                "title": row[0],
                "url": row[1],
                "watched": row[2],
                "path": row[3],
                "video_id": row[4],
                "topic": row[5],
            }
            note_file = Path(row[3])
            if not note_file.is_file():
                return {"ok": False, "error": "Note file not found"}
            with note_file.open(encoding="utf-8") as handle:
                content = _bounded_content(handle.read(MAX_NOTE_CHARS + 1))
            return {"ok": True, "content": content, "meta": meta}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    async def topics(self) -> Dict[str, Any]:
        """List topics and note counts."""
        bus_res = await self._bus_request("yt-brain.topics", {})
        if bus_res is not None:
            if bus_res.get("ok") is False:
                return bus_res
            return {"ok": True, "topics": bus_res.get("topics", {}), "source": "agent_bus"}

        return await asyncio.to_thread(self._direct_topics)

    def _direct_topics(self) -> Dict[str, Any]:
        if not self.kb_path.exists():
            return {"ok": False, "error": f"KB not found at {self.kb_path}", "topics": {}}

        try:
            with closing(_connect_readonly(self.kb_path)) as conn:
                rows = conn.execute(
                    "SELECT topic, count(*) FROM notes GROUP BY topic ORDER BY count(*) DESC"
                ).fetchall()
                topics = {r[0] or "uncategorized": r[1] for r in rows}
                return {"ok": True, "topics": topics, "source": "sqlite_fallback"}
        except Exception as exc:
            return {"ok": False, "error": str(exc), "topics": {}}

    async def status(self) -> Dict[str, Any]:
        """Get operational status and stats."""
        bus_res = await self._bus_request("yt-brain.status", {})
        if bus_res is not None:
            return {**bus_res, "ok": bus_res.get("ok", bus_res.get("status") == "online"),
                    "source": "agent_bus", "worker_reachable": True}

        return await asyncio.to_thread(self._direct_status)

    def _direct_status(self) -> Dict[str, Any]:
        if not self.kb_path.exists():
            return {
                "ok": False,
                "status": "database_missing",
                "error": f"KB not found at {self.kb_path}",
                "total_notes": 0,
            }

        try:
            with closing(_connect_readonly(self.kb_path)) as conn:
                cur = conn.cursor()
                total = cur.execute("SELECT count(*) FROM notes").fetchone()[0]
                latest = cur.execute(
                    "SELECT title, url, watched, topic FROM notes ORDER BY watched DESC LIMIT 1"
                ).fetchone()
                topics_res = cur.execute(
                    "SELECT topic, count(*) FROM notes GROUP BY topic ORDER BY count(*) DESC"
                ).fetchall()
                topics = {r[0] or "uncategorized": r[1] for r in topics_res}

            latest_info = (
                {"title": latest[0], "url": latest[1], "watched": latest[2], "topic": latest[3]}
                if latest
                else None
            )
            return {
                "ok": True,
                "status": "archive_available",
                "worker_reachable": False,
                "total_notes": total,
                "topics": topics,
                "latest_note": latest_info,
                "source": "sqlite_direct",
            }
        except Exception as exc:
            return {"ok": False, "status": "error", "error": str(exc), "total_notes": 0}


_CLIENT: Optional[YtBrainClient] = None


def get_client() -> YtBrainClient:
    global _CLIENT
    if _CLIENT is None:
        _CLIENT = YtBrainClient()
    return _CLIENT
