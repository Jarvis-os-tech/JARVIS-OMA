"""Agent A12: LinkedIn Content Stager & Scheduler.
Packages approved and verified content into review cards for Jarvis and coordinates queueing.
"""

from datetime import datetime
import json
from pathlib import Path
from typing import Any
from .base_agent import BaseLinkedInAgent, AgentResult


class ContentSchedulerAgent(BaseLinkedInAgent):
    agent_id = "A12"
    agent_name = "ContentScheduler"
    description = "Packages validated posts into structured review cards for Jarvis and manages the staging queue."

    def publish_approved(self, commentary: str, image_path: str | None = None):
        if image_path is None:
            return self.tools.create_post(commentary=commentary)
        return self.tools.create_post(commentary=commentary, image_path=image_path)

    def execute(self, task_input: dict[str, Any]) -> AgentResult:
        post_draft = task_input.get("post_draft", "")
        scheduled_date = task_input.get("scheduled_date", datetime.now().strftime("%Y-%m-%d 08:30"))
        pillar = task_input.get("pillar", "Authority & Build Logs")
        formula_code = task_input.get("formula_code", "F7")
        humanizer_metadata = task_input.get("humanizer_metadata", {})
        media_prompt = task_input.get("media_prompt", "High-fidelity architecture diagram / screenshot")

        # Create a unique post ID
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        post_id = f"post_{timestamp_str}_{formula_code.lower()}"

        review_package = {
            "post_id": post_id,
            "created_at": datetime.now().isoformat(),
            "target_schedule": scheduled_date,
            "pillar": pillar,
            "formula_code": formula_code,
            "char_count": len(post_draft),
            "media_prompt": media_prompt,
            "humanizer_audit": humanizer_metadata,
            "status": "PENDING_JARVIS_USER_REVIEW",
            "content": post_draft,
        }

        # Render clean Markdown approval card
        approval_card_md = f"""# LinkedIn Post Review Card — {post_id}

* **Target Slot:** `{scheduled_date}`
* **Content Pillar:** `{pillar}`
* **Formula Used:** `{formula_code}`
* **Character Count:** {len(post_draft)} chars
* **Status:** ⏳ **Awaiting User Review via Jarvis**
* **Media Prompt:** *{media_prompt}*

---

### Post Content Draft:
```text
{post_draft}
```

---

### Quality Gate Summary:
* **A10 Humanizer Check:** {'✅ PASS' if humanizer_metadata.get('authenticity_pass', True) else '⚠️ REVIEW NEEDED'}
* **Flagged AI Words:** {', '.join(humanizer_metadata.get('flagged_markers', [])) or 'None (Clean)'}

---
*To publish, confirm with Jarvis: "Jarvis, approve post {post_id}"*
"""

        # Write review card to state/review_queue/
        json_file = self.cfg.review_queue_dir / f"{post_id}.json"
        md_file = self.cfg.review_queue_dir / f"{post_id}.md"

        json_file.write_text(json.dumps(review_package, indent=2, ensure_ascii=False), encoding="utf-8")
        md_file.write_text(approval_card_md, encoding="utf-8")

        return AgentResult(
            success=True,
            agent_id=self.agent_id,
            agent_name=self.agent_name,
            output=review_package,
            artifacts=[str(json_file), str(md_file)],
            metadata={"post_id": post_id, "status": "PENDING_JARVIS_USER_REVIEW"},
        )
