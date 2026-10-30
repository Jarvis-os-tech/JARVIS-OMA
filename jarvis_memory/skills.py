"""Memory skills adapter providing clean tool execution and voice integration."""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path
import sqlite3
from typing import Any

from .bridge import MemoryBridge, MemoryError as BridgeMemoryError
from .config import Config, MemoryConfig

log = logging.getLogger(__name__)


class SkillError(Exception):
    """Raised when a skill or memory tool fails."""


class MemorySkills:
    """Memory skill router and worker adapter."""

    def __init__(self, config: Config | None = None, api_key: str | None = None):
        self.config = config or Config()
        self._memory_config = getattr(self.config, "memory", MemoryConfig())
        self._memory_api_key = api_key
        self._memory_writes: set[asyncio.Task] = set()
        self.memory = MemoryBridge(self._memory_config, api_key=api_key)

        # Declarations matching manifest
        if self._memory_config.enabled:
            self.declarations = [
                {"name": "remember_memory", "description": "Save a verified user preference or fact."},
                {"name": "recall_memory", "description": "Search active memory facts and profiles."},
                {"name": "forget_memory", "description": "Remove a memory fact."},
                {"name": "clear_memory", "description": "Clear all memory facts."},
                {"name": "update_memory_profile", "description": "Update core profile notes."},
                {"name": "index_memory_document", "description": "Index a document into memory."},
                {"name": "memory_status", "description": "Retrieve memory system status."},
                {"name": "sync_memory_vault", "description": "Sync memory with Obsidian vault."},
                {"name": "correct_memory", "description": "Correct an existing memory entry."},
                {"name": "memory_history", "description": "Retrieve revision history for a memory."},
            ]
        else:
            self.declarations = []

    def memory_context(self) -> str:
        """Render recent relevant memory context within configured character budget."""
        if not self._memory_config.enabled:
            return ""
        try:
            ctx = self.memory.context()
            return ctx[:self._memory_config.context_max_chars]
        except Exception as error:
            log.warning("Memory context extraction failed: %s", error)
            return ""

    async def execute(self, tool_name: str, arguments: dict[str, Any] | None = None) -> Any:
        arguments = arguments or {}
        adapter_map = {
            "remember_memory": self._adapter_remember_memory,
            "recall_memory": self._adapter_recall_memory,
            "forget_memory": self._adapter_forget_memory,
            "clear_memory": self._adapter_clear_memory,
            "update_memory_profile": self._adapter_update_memory_profile,
            "index_memory_document": self._adapter_index_memory_document,
            "memory_status": self._adapter_memory_status,
            "sync_memory_vault": self._adapter_sync_memory_vault,
            "correct_memory": self._adapter_correct_memory,
            "memory_history": self._adapter_memory_history,
        }
        handler = adapter_map.get(tool_name)
        if not handler:
            raise SkillError(f"Unknown memory tool: {tool_name}")
        return await handler(**arguments)

    async def _memory_operation(self, method: str, **kwargs: Any) -> Any:
        try:
            fn = getattr(self.memory, method)
            if asyncio.iscoroutinefunction(fn):
                return await fn(**kwargs)
            return await asyncio.to_thread(fn, **kwargs)
        except (BridgeMemoryError, OSError, UnicodeError, sqlite3.Error, ValueError) as error:
            raise SkillError(str(error)) from None

    async def _adapter_remember_memory(self, text: str) -> dict[str, Any]:
        return await self._memory_operation("remember", text=text)

    async def _adapter_recall_memory(self, query: str = "", limit: int = 20) -> dict[str, Any]:
        return await self._memory_operation("recall", query=query, limit=limit)

    async def _adapter_forget_memory(self, text: str) -> dict[str, Any]:
        return await self._memory_operation("forget", text=text)

    async def _adapter_clear_memory(self) -> dict[str, Any]:
        return await self._memory_operation("clear")

    async def _adapter_update_memory_profile(self, name: str, content: str) -> dict[str, Any]:
        return await self._memory_operation("update_profile", name=name, content=content)

    async def _adapter_index_memory_document(self, path: str) -> dict[str, Any]:
        return await self._memory_operation("index_document", path=path)

    async def _adapter_memory_status(self) -> dict[str, Any]:
        return await self._memory_operation("status")

    async def _adapter_sync_memory_vault(self) -> dict[str, Any]:
        return await self._memory_operation("sync_obsidian")

    async def _adapter_correct_memory(self, memory_id: str, text: str) -> dict[str, Any]:
        return await self._memory_operation("correct", memory_id=memory_id, text=text)

    async def _adapter_memory_history(self, memory_id: str) -> dict[str, Any]:
        return await self._memory_operation("memory_history", memory_id=memory_id)

    def queue_memory_exchange(self, user: str, assistant: str) -> None:
        if not user and not assistant:
            return
        if len(self._memory_writes) >= 16:
            log.warning("Memory capture backlog full; dropping exchange")
            return

        async def _do_record():
            self.memory.record_exchange(user, assistant)

        task = asyncio.create_task(_do_record())
        self._memory_writes.add(task)

        def finished(done: asyncio.Task) -> None:
            self._memory_writes.discard(done)
            try:
                done.result()
            except asyncio.CancelledError:
                pass
            except Exception as error:
                log.warning("Memory capture failed: %s", type(error).__name__)

        task.add_done_callback(finished)

    async def close_agent_jobs(self) -> None:
        if self._memory_writes:
            await asyncio.gather(*tuple(self._memory_writes), return_exceptions=True)
        self.memory.close()


# Compatibility alias for tests and legacy callers
DesktopSkills = MemorySkills
