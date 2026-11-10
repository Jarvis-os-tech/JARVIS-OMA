"""LinkedIn Department domain adapter for JARVIS OS.
Exposes the 12-agent LinkedIn Department to Jarvis orchestrator and handles review gates.
"""

from typing import Any, Dict, Optional
from departments.linkedin import linkedin_dept

ADAPTERS = {
    "linkedin.draft_post": "_adapter_linkedin_draft_post",
    "linkedin.plan_sprint": "_adapter_linkedin_plan_sprint",
    "linkedin.audit_profile": "_adapter_linkedin_audit_profile",
    "linkedin.pending_reviews": "_adapter_linkedin_pending_reviews",
    "linkedin.approve_post": "_adapter_linkedin_approve_post",
    "linkedin.sync_profile": "_adapter_linkedin_sync_profile",
    "linkedin.propose_tool": "_adapter_linkedin_propose_tool",
}

ADAPTER_COMMANDS = {
    "linkedin.draft_post": (),
    "linkedin.plan_sprint": (),
    "linkedin.audit_profile": (),
    "linkedin.pending_reviews": (),
    "linkedin.approve_post": (),
    "linkedin.sync_profile": (),
    "linkedin.propose_tool": (),
}


class LinkedInDomain:
    """Domain adapter for LinkedIn operations in JARVIS OS."""

    async def _adapter_linkedin_draft_post(
        self,
        topic: str,
        angle: str = "",
        formula_code: str = "F7",
        pillar: str = "Authority & Build Logs",
        scheduled_slot: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Draft a post, pass through humanizer, and stage in review queue."""
        pkg = linkedin_dept.draft_and_stage_post(
            topic=topic,
            angle=angle,
            formula_code=formula_code,
            pillar=pillar,
            scheduled_slot=scheduled_slot,
        )
        return {
            "status": "AWAITING_USER_REVIEW",
            "post_id": pkg.post_id,
            "target_slot": pkg.target_slot,
            "pillar": pkg.pillar,
            "formula_code": pkg.formula_code,
            "char_count": pkg.char_count,
            "humanizer_passed": pkg.humanizer_passed,
            "review_card_path": pkg.review_card_path,
            "preview_snippet": pkg.content[:250] + ("..." if len(pkg.content) > 250 else ""),
            "action_required": f"Review staged card at {pkg.review_card_path} or confirm with 'Jarvis, approve post {pkg.post_id}'.",
        }

    async def _adapter_linkedin_plan_sprint(
        self, days: int = 7, focus_topic: str = "Autonomous AI Systems"
    ) -> Dict[str, Any]:
        """Generate a strategic sprint calendar via A2 Content Planner."""
        return linkedin_dept.plan_sprint(days=days, focus_topic=focus_topic)

    async def _adapter_linkedin_audit_profile(
        self, current_profile: str, goal: str = "Client acquisition & technical authority"
    ) -> Dict[str, Any]:
        """Audit 9 profile elements via A1 Profile Optimizer."""
        return linkedin_dept.audit_profile(current_profile=current_profile, goal=goal)

    async def _adapter_linkedin_pending_reviews(self) -> Dict[str, Any]:
        """List all staged posts awaiting user sign-off."""
        pending = linkedin_dept.get_pending_reviews()
        return {
            "pending_count": len(pending),
            "posts": pending,
        }

    async def _adapter_linkedin_approve_post(self, post_id: str, publish_now: bool = False) -> Dict[str, Any]:
        """Approve a post for publishing, optionally publishing live immediately."""
        res = linkedin_dept.approve_post(post_id, publish_now=publish_now)
        if res.get("success", False):
            return {
                "ok": True,
                "post_id": post_id,
                "status": res.get("status"),
                "message": f"Post {post_id} successfully processed: {res.get('status')}.",
                "receipt": res.get("receipt"),
            }
        return {
            "ok": False,
            "post_id": post_id,
            "error": res.get("error") or f"Post {post_id} approval failed.",
        }

    async def _adapter_linkedin_sync_profile(self) -> Dict[str, Any]:
        """Synchronize live profile from LinkedIn into department state."""
        return linkedin_dept.sync_live_profile()

    async def _adapter_linkedin_propose_tool(self, problem: str) -> Dict[str, Any]:
        """Use the API Agent to reverse-engineer and propose an endpoint for missing LinkedIn operations."""
        return await linkedin_dept.propose_missing_tool(problem)
