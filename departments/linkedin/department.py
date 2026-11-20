"""LinkedIn Department Orchestrator & Department Lead for JARVIS OS.
Coordinates the 12 specialized agents into collaborative pipelines, maintains shared departmental state,
and generates structured Review Packages for Jarvis to deliver to the user.
"""

from dataclasses import dataclass, field
from datetime import datetime
import json
import logging
from pathlib import Path
from typing import Any, Optional

from .config import config, LinkedInConfig
from .tools import linkedin_tools, LinkedInTools, ToolExecutionResult
from .agents import (
    AGENT_REGISTRY,
    ProfileOptimizerAgent,
    ContentPlannerAgent,
    PostWriterAgent,
    ReplyHandlerAgent,
    RepurposerAgent,
    ThreadMonitorAgent,
    EngagerAnalyticsAgent,
    EmployeeAdvocacyAgent,
    HookExtractorAgent,
    HumanizerAgent,
    InterviewerAgent,
    ContentSchedulerAgent,
)

logger = logging.getLogger("departments.linkedin.department")


@dataclass
class ReviewPackage:
    post_id: str
    created_at: str
    target_slot: str
    pillar: str
    formula_code: str
    content: str
    char_count: int
    media_prompt: str
    humanizer_passed: bool
    review_card_path: str
    status: str = "AWAITING_USER_REVIEW"


class LinkedInDepartment:
    """Department Lead orchestrating all 12 LinkedIn specialist agents."""

    def __init__(self, cfg: Optional[LinkedInConfig] = None, tools: Optional[LinkedInTools] = None):
        self.cfg = cfg or config
        self.tools = tools or linkedin_tools

        # Instantiate all 12 agents
        self.a1_profile = ProfileOptimizerAgent(self.cfg)
        self.a2_planner = ContentPlannerAgent(self.cfg)
        self.a3_writer = PostWriterAgent(self.cfg)
        self.a4_reply = ReplyHandlerAgent(self.cfg)
        self.a5_repurposer = RepurposerAgent(self.cfg)
        self.a6_monitor = ThreadMonitorAgent(self.cfg)
        self.a7_analytics = EngagerAnalyticsAgent(self.cfg)
        self.a8_advocacy = EmployeeAdvocacyAgent(self.cfg)
        self.a9_hooks = HookExtractorAgent(self.cfg)
        self.a10_humanizer = HumanizerAgent(self.cfg)
        self.a11_interviewer = InterviewerAgent(self.cfg)
        self.a12_scheduler = ContentSchedulerAgent(self.cfg, tools=self.tools)

    def draft_and_stage_post(
        self,
        topic: str,
        angle: str = "",
        formula_code: str = "F7",
        pillar: str = "Authority & Build Logs",
        cta_type: str = "Specific question",
        scheduled_slot: Optional[str] = None,
    ) -> ReviewPackage:
        """Core Pipeline: A3 (Draft) -> A10 (Humanize) -> A12 (Stage Review Card).
        Returns a ReviewPackage for Jarvis to present to the user.
        """
        logger.info("Executing post pipeline for topic: %s (Formula: %s)", topic, formula_code)

        # 1. Post Writer drafts the post
        writer_res = self.a3_writer.execute({
            "topic": topic,
            "angle": angle,
            "formula_code": formula_code,
            "pillar": pillar,
            "cta_type": cta_type,
        })
        if not writer_res.success:
            raise RuntimeError(f"A3 PostWriter failed: {writer_res.error}")

        raw_draft = writer_res.output

        # 2. Mandatory Humanizer & Voice Authenticator pass
        humanizer_res = self.a10_humanizer.execute({
            "draft": raw_draft,
            "context": f"Topic: {topic}, Pillar: {pillar}",
        })
        if not humanizer_res.success:
            logger.warning("A10 Humanizer warning: %s", humanizer_res.error)

        humanized_post = humanizer_res.output or raw_draft

        # 3. Stage in Review Queue via A12
        slot = scheduled_slot or datetime.now().strftime("%Y-%m-%d 08:30")
        media_prompt = f"Technical illustration / visual diagram illustrating: {topic}"

        scheduler_res = self.a12_scheduler.execute({
            "post_draft": humanized_post,
            "scheduled_date": slot,
            "pillar": pillar,
            "formula_code": formula_code,
            "humanizer_metadata": humanizer_res.metadata,
            "media_prompt": media_prompt,
        })
        if not scheduler_res.success:
            raise RuntimeError(f"A12 Scheduler staging failed: {scheduler_res.error}")

        pkg_data = scheduler_res.output
        review_card_path = str(scheduler_res.artifacts[1]) if len(scheduler_res.artifacts) > 1 else ""

        return ReviewPackage(
            post_id=pkg_data["post_id"],
            created_at=pkg_data["created_at"],
            target_slot=pkg_data["target_schedule"],
            pillar=pkg_data["pillar"],
            formula_code=pkg_data["formula_code"],
            content=humanized_post,
            char_count=len(humanized_post),
            media_prompt=media_prompt,
            humanizer_passed=humanizer_res.metadata.get("authenticity_pass", True),
            review_card_path=review_card_path,
        )

    def plan_sprint(self, days: int = 7, focus_topic: str = "AI Autonomous Systems") -> dict[str, Any]:
        """Plans a content sprint using A2 Content Planner."""
        res = self.a2_planner.execute({
            "days": days,
            "focus_topic": focus_topic,
        })
        return {
            "success": res.success,
            "report": res.output,
            "artifacts": res.artifacts,
            "metadata": res.metadata,
        }

    def audit_profile(self, current_profile: str, goal: str = "Client acquisition & technical authority") -> dict[str, Any]:
        """Audits and optimizes the 9 profile elements using A1 Profile Optimizer."""
        res = self.a1_profile.execute({
            "current_profile": current_profile,
            "goal": goal,
        })
        return {
            "success": res.success,
            "report": res.output,
            "artifacts": res.artifacts,
            "metadata": res.metadata,
        }

    def reverse_engineer_hook(self, viral_post_text: str, domain: str = "AI Engineering") -> dict[str, Any]:
        """Reverse-engineers a viral post using A9 Hook Extractor."""
        res = self.a9_hooks.execute({
            "post_text": viral_post_text,
            "domain": domain,
        })
        return {
            "success": res.success,
            "report": res.output,
            "metadata": res.metadata,
        }

    def get_pending_reviews(self) -> list[dict[str, Any]]:
        """List all posts in state/review_queue/ waiting for user approval."""
        pending = []
        for file in sorted(self.cfg.review_queue_dir.glob("*.json")):
            try:
                data = json.loads(file.read_text(encoding="utf-8"))
                if data.get("status") == "PENDING_JARVIS_USER_REVIEW":
                    pending.append(data)
            except Exception:
                pass
        return pending

    def sync_live_profile(self) -> dict[str, Any]:
        """Fetch live authenticated profile via Composio and update state/my-profile.json."""
        res = self.tools.get_my_info()
        if not res.success:
            return {"success": False, "error": res.error}

        profile_data = res.data or {}
        profile_path = self.cfg.state_dir / "my-profile.json"
        profile_path.write_text(json.dumps(profile_data, indent=2, ensure_ascii=False), encoding="utf-8")

        # Extract name & headline for state thesis
        name = f"{profile_data.get('localizedFirstName', '')} {profile_data.get('localizedLastName', '')}".strip()
        headline = profile_data.get('localizedHeadline', '')
        summary_text = f"User: {name}\nHeadline: {headline}\nProfile URL: {profile_data.get('profileUrl', '')}"
        (self.cfg.state_dir / "live-profile-summary.txt").write_text(summary_text, encoding="utf-8")

        return {"success": True, "data": profile_data, "summary": summary_text}

    def approve_post(self, post_id: str, publish_now: bool = False, image_path: str | None = None) -> dict[str, Any]:
        """User has approved the post via Jarvis. If publish_now is True, publishes directly to LinkedIn."""
        if not post_id or Path(post_id).name != post_id:
            return {"success": False, "error": "Invalid post ID."}
        if image_path is not None and not publish_now:
            return {"success": False, "error": "Supply the approved image path when publishing."}
        json_file = self.cfg.review_queue_dir / f"{post_id}.json"
        md_file = self.cfg.review_queue_dir / f"{post_id}.md"

        if not json_file.exists():
            return {"success": False, "error": f"Post {post_id} not found."}

        data = json.loads(json_file.read_text(encoding="utf-8"))
        if data.get("status") == "PUBLISHED_LIVE":
            return {"success": False, "error": "This draft has already been published."}
        data["approved_at"] = datetime.now().isoformat()

        if publish_now:
            # Publish live to LinkedIn via Composio
            content_to_post = data.get("content", "")
            pub_res = self.a12_scheduler.publish_approved(content_to_post, image_path)
            if pub_res.success:
                data["status"] = "PUBLISHED_LIVE"
                data["published_at"] = datetime.now().isoformat()
                data["published_receipt"] = pub_res.data
                json_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

                if md_file.exists():
                    text = md_file.read_text(encoding="utf-8")
                    text = text.replace("⏳ **Awaiting User Review via Jarvis**", "🚀 **PUBLISHED LIVE on LinkedIn**")
                    md_file.write_text(text, encoding="utf-8")

                return {
                    "success": True,
                    "status": "PUBLISHED_LIVE",
                    "post_id": post_id,
                    "receipt": pub_res.data,
                }
            else:
                data["publish_error"] = pub_res.error
                json_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
                return {
                    "success": False,
                    "status": "PUBLISH_FAILED",
                    "error": pub_res.error,
                }

        # Staged approval without immediate publishing
        data["status"] = "APPROVED_READY_TO_PUBLISH"
        json_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

        if md_file.exists():
            text = md_file.read_text(encoding="utf-8")
            text = text.replace("⏳ **Awaiting User Review via Jarvis**", "✅ **APPROVED by User (Ready to Publish)**")
            md_file.write_text(text, encoding="utf-8")

        return {"success": True, "status": "APPROVED_READY_TO_PUBLISH", "post_id": post_id}

    def publish_post(self, post_id: str, image_path: str | None = None) -> dict[str, Any]:
        """Publish an approved post to LinkedIn live."""
        return self.approve_post(post_id, publish_now=True, image_path=image_path)

    async def propose_missing_tool(self, problem_description: str) -> dict[str, Any]:
        """API Agent integration: Propose an API blueprint for missing LinkedIn operations."""
        res = await self.tools.propose_missing_operation(problem_description)
        return {
            "success": res.success,
            "blueprint": res.data,
            "error": res.error,
            "provider": res.provider,
        }

    def revise_post_with_feedback(self, post_id: str, feedback: str) -> ReviewPackage:
        """User requested edits. Re-runs writer with feedback, humanizes, and updates card."""
        json_file = self.cfg.review_queue_dir / f"{post_id}.json"
        if not json_file.exists():
            raise FileNotFoundError(f"Post {post_id} not found in review queue.")

        current = json.loads(json_file.read_text(encoding="utf-8"))
        revised_topic = f"{current['pillar']} (Revision: {feedback})"

        return self.draft_and_stage_post(
            topic=revised_topic,
            angle=feedback,
            formula_code=current["formula_code"],
            pillar=current["pillar"],
            scheduled_slot=current.get("target_schedule"),
        )


# Global department lead instance
linkedin_dept = LinkedInDepartment()
