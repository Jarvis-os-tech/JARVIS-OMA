"""Memory Department domain adapter for JARVIS OS.
Exposes the Sovereign Memory Department (6 specialized agents) to Jarvis orchestrator and Gemini Live.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


ADAPTERS = {
    "memory.sync": "_adapter_sync_memory_department",
    "memory.compact": "_adapter_compact_memory_history",
    "memory.prune": "_adapter_prune_memory_vault",
    "memory.reflect": "_adapter_memory_reflect",
}

ADAPTER_COMMANDS = {
    "memory.sync": (),
    "memory.compact": (),
    "memory.prune": (),
    "memory.reflect": (),
}


class MemoryDomain:
    """Domain adapter for Sovereign Memory Department in JARVIS OS."""

    async def _adapter_sync_memory_department(self) -> Dict[str, Any]:
        return await self._memory_operation("memory_department", operation="sync_sessions_to_vault")

    async def _adapter_compact_memory_history(self, target_date: Optional[str] = None) -> Dict[str, Any]:
        if target_date:
            return await self._memory_operation("memory_department", operation="compact_date",
                                                target_date=target_date)
        compacted = await self._memory_operation("memory_department", operation="compact_all_history")
        return {"status": "COMPACTED_ALL", "compacted_count": len(compacted),
                "files": [entry["filename"] for entry in compacted]}

    async def _adapter_prune_memory_vault(self, dry_run: bool = False) -> Dict[str, Any]:
        return await self._memory_operation("memory_department", operation="prune_empty_files",
                                            dry_run=dry_run)

    async def _adapter_memory_reflect(self) -> Dict[str, Any]:
        return await self._memory_operation("memory_department", operation="run_nightly_reflection")
