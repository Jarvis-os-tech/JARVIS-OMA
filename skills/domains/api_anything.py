"""API-Anything domain adapters for JARVIS OS.

Enables JARVIS OS to discover, execute, and harvest web APIs using api-anything
and the dual-model Omarchy API Agent Daemon.
"""
from __future__ import annotations

from typing import Any, Dict, Optional
from connectors import api_anything
from skills.errors import SkillError


ADAPTERS = {
    "api_anything.search": "_adapter_api_anything_search",
    "api_anything.list_operations": "_adapter_api_anything_list_operations",
    "api_anything.call": "_adapter_api_anything_call",
    "api_anything.propose": "_adapter_api_anything_propose",
    "api_anything.learn": "_adapter_api_anything_learn",
}

ADAPTER_COMMANDS = {
    "api_anything.search": (),
    "api_anything.list_operations": (),
    "api_anything.call": (),
    "api_anything.propose": (),
    "api_anything.learn": (),
}


class ApiAnythingDomain:
    async def _adapter_api_anything_search(self, query: str) -> Dict[str, Any]:
        """Search available API operations across local ledger and shared catalog."""
        if not query or not query.strip():
            raise SkillError("Query must be a non-empty string.")
        res = await api_anything.search(query.strip())
        if not res.get("ok", True):
            raise SkillError(res.get("error", "Search failed"))
        return res

    async def _adapter_api_anything_list_operations(self, site: str) -> Dict[str, Any]:
        """List operations, parameters, and caveats for an installed or shared site."""
        if not site or not site.strip():
            raise SkillError("Site name must be specified.")
        res = await api_anything.list_operations(site.strip())
        if not res.get("ok", True):
            raise SkillError(res.get("error", "Failed to retrieve site operations"))
        return res

    async def _adapter_api_anything_call(
        self, site: str, op: str, args: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Call a verified web API operation directly with arguments."""
        if not site or not op:
            raise SkillError("Both 'site' and 'op' are required.")
        res = await api_anything.call_operation(site, op, args)
        if not res.get("ok", True):
            raise SkillError(res.get("error") or res.get("reason") or "API call execution failed")
        return res

    async def _adapter_api_anything_propose(self, problem: str) -> Dict[str, Any]:
        """Propose an API Blueprint layout, test arguments, and fields for review."""
        if not problem or not problem.strip():
            raise SkillError("Problem description cannot be empty.")
        res = await api_anything.propose_blueprint(problem.strip())
        if not res.get("ok", True):
            raise SkillError(res.get("error", "Failed to propose API blueprint"))
        return res

    async def _adapter_api_anything_learn(self, blueprint: Dict[str, Any]) -> Dict[str, Any]:
        """Execute browser learning and validation for an approved blueprint."""
        if not blueprint or not isinstance(blueprint, dict):
            raise SkillError("A valid blueprint object is required to learn an API.")
        res = await api_anything.learn_and_activate(blueprint)
        if not res.get("ok", True):
            raise SkillError(res.get("error", "Failed to learn and activate API"))
        return res
