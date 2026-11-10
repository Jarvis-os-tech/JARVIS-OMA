"""LinkedIn Department Unified Tool & API Agent Bridge.
Connects all live LinkedIn capabilities:
1. Composio LinkedIn Toolkit: Official authenticated posting, profile retrieval, image registration, and deletion.
2. API-Anything / Omarchy API Agent: Voyager API reverse-engineering for search, company scraping, and learning missing endpoints.
"""

import asyncio
from dataclasses import dataclass
import json
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("departments.linkedin.tools")


@dataclass
class ToolExecutionResult:
    success: bool
    data: Any = None
    error: Optional[str] = None
    provider: str = "composio"  # 'composio' or 'api_anything'


class LinkedInTools:
    """Unified bridge for all LinkedIn operations and the API Agent."""

    def __init__(self, user_id: str = "local-user"):
        self.user_id = user_id
        self._author_urn: Optional[str] = None

    # ── 1. Native / Composio Authenticated Tools ──────────────────────────

    def _execute_composio(self, action_query: str, arguments: Optional[Dict[str, Any]] = None) -> ToolExecutionResult:
        try:
            from connectors import composio
            res = composio.execute_platform_action("linkedin", action_query, arguments or {}, user_id=self.user_id)
            if res.get("success", False):
                return ToolExecutionResult(success=True, data=res.get("data"), provider="composio")
            return ToolExecutionResult(
                success=False,
                error=res.get("error") or res.get("message") or "Action failed",
                provider="composio",
            )
        except Exception as e:
            return ToolExecutionResult(success=False, error=str(e), provider="composio")

    def get_my_info(self) -> ToolExecutionResult:
        """Fetch the authenticated LinkedIn user's profile information."""
        res = self._execute_composio("get my profile info")
        if res.success and isinstance(res.data, dict):
            member_id = res.data.get("id")
            if member_id:
                self._author_urn = f"urn:li:person:{member_id}"
        return res

    def resolve_author_urn(self) -> Optional[str]:
        """Derive the person author URN (e.g. urn:li:person:4_jR4WANsE)."""
        if self._author_urn:
            return self._author_urn
        res = self.get_my_info()
        if res.success and isinstance(res.data, dict):
            member_id = res.data.get("id")
            if member_id:
                self._author_urn = f"urn:li:person:{member_id}"
                return self._author_urn
        return None

    def create_post(
        self,
        commentary: str,
        visibility: str = "PUBLIC",
        asset_urn: Optional[str] = None,
    ) -> ToolExecutionResult:
        """Create a new post on LinkedIn for the authenticated user."""
        author_urn = self.resolve_author_urn()
        if not author_urn:
            return ToolExecutionResult(
                success=False,
                error="Could not resolve authenticated author URN from LinkedIn.",
                provider="composio",
            )

        args: Dict[str, Any] = {
            "author": author_urn,
            "commentary": commentary,
            "visibility": visibility,
        }
        if asset_urn:
            args["media"] = {"id": asset_urn}

        return self._execute_composio("create post", args)

    def register_image_upload(self, recipe: str = "urn:li:digitalmediaRecipe:feedshare-image") -> ToolExecutionResult:
        """Register a native image upload for attaching visuals to a post."""
        author_urn = self.resolve_author_urn()
        if not author_urn:
            return ToolExecutionResult(success=False, error="Missing author URN", provider="composio")

        return self._execute_composio(
            "register image upload",
            {"owner_urn": author_urn, "recipe": recipe},
        )

    def get_post_content(self, post_urn: str) -> ToolExecutionResult:
        """Retrieve post content and metrics."""
        return self._execute_composio("get post content", {"post_urn": post_urn})

    def delete_post(self, post_urn: str) -> ToolExecutionResult:
        """Delete a post by URN."""
        return self._execute_composio("delete post", {"post_urn": post_urn})

    def get_company_info(self) -> ToolExecutionResult:
        """Fetch linked company/organization info."""
        return self._execute_composio("get company info", {})

    # ── 2. API Agent (API-Anything) for Discovery & Missing Operations ────

    async def call_api_agent(self, operation: str, args: Optional[Dict[str, Any]] = None) -> ToolExecutionResult:
        """Invoke a discovered Voyager operation via the API Agent (getMe, getProfile, searchPeople, searchCompanies)."""
        try:
            from connectors import api_anything
            res = await api_anything.call_operation("linkedin", operation, args or {})
            if res.get("ok", False):
                return ToolExecutionResult(success=True, data=res.get("data"), provider="api_anything")
            return ToolExecutionResult(
                success=False,
                error=res.get("error") or res.get("reason") or "API Agent call failed",
                provider="api_anything",
            )
        except Exception as e:
            return ToolExecutionResult(success=False, error=str(e), provider="api_anything")

    async def search_people(self, keywords: str) -> ToolExecutionResult:
        """Search people on LinkedIn via API Agent."""
        return await self.call_api_agent("searchPeople", {"keywords": keywords})

    async def search_companies(self, keywords: str) -> ToolExecutionResult:
        """Search companies on LinkedIn via API Agent."""
        return await self.call_api_agent("searchCompanies", {"keywords": keywords})

    async def get_member_profile(self, public_id: str) -> ToolExecutionResult:
        """Retrieve another member's profile via API Agent."""
        return await self.call_api_agent("getProfile", {"publicId": public_id})

    async def propose_missing_operation(self, problem_description: str) -> ToolExecutionResult:
        """API Agent Blueprint Proposer:
        When an agent needs an operation not currently available (e.g. comment thread scraping, follower analytics),
        propose a reverse-engineering blueprint using the Omarchy API Agent Daemon.
        """
        try:
            from connectors import api_anything
            res = await api_anything.propose_blueprint(f"LinkedIn: {problem_description}")
            if res.get("ok", False):
                return ToolExecutionResult(success=True, data=res.get("blueprint"), provider="api_anything")
            return ToolExecutionResult(
                success=False,
                error=res.get("error") or "Blueprint proposal failed",
                provider="api_anything",
            )
        except Exception as e:
            return ToolExecutionResult(success=False, error=str(e), provider="api_anything")

    async def learn_missing_operation(self, blueprint: Dict[str, Any]) -> ToolExecutionResult:
        """API Agent Learner:
        Execute browser learning and activation for an approved blueprint.
        """
        try:
            from connectors import api_anything
            res = await api_anything.learn_and_activate(blueprint)
            if res.get("ok", False):
                return ToolExecutionResult(success=True, data=res, provider="api_anything")
            return ToolExecutionResult(
                success=False,
                error=res.get("error") or "Blueprint learning failed",
                provider="api_anything",
            )
        except Exception as e:
            return ToolExecutionResult(success=False, error=str(e), provider="api_anything")


# Global tools instance
linkedin_tools = LinkedInTools()
