"""Agent A2: LinkedIn Content Planner.
Generates structured content calendars balancing content pillars, hook formulas, and audience goals.
"""

from datetime import datetime, timedelta
import json
from typing import Any
from .base_agent import BaseLinkedInAgent, AgentResult


class ContentPlannerAgent(BaseLinkedInAgent):
    agent_id = "A2"
    agent_name = "ContentPlanner"
    description = "Plans weekly/monthly content calendars mapping pillars and hook formulas to days."

    def execute(self, task_input: dict[str, Any]) -> AgentResult:
        days_count = task_input.get("days", 7)
        start_date_str = task_input.get("start_date")
        if start_date_str:
            start_date = datetime.fromisoformat(start_date_str)
        else:
            start_date = datetime.now() + timedelta(days=1)

        focus_topic = task_input.get("focus_topic", "AI engineering and system autonomy")
        thesis = self.read_state("profile-thesis.txt")
        pillar_mix = self.read_json_state("pillar-mix.json")
        hook_reference = self.read_reference("hook-formulas.md")

        system_prompt = (
            "You are the LinkedIn Content Planner Agent (A2) in JARVIS OS. "
            "Your job is to generate a tactical, high-converting content calendar. "
            "Balance pillars (Authority, Actionable, Story, Contrarian) and assign tested hook formulas (F1 to F20). "
            "Ensure posts build cumulative momentum and support the user's primary positioning thesis."
        )

        prompt = f"""
PLANNING BRIEF:
Horizon: {days_count} days starting {start_date.strftime('%Y-%m-%d')}
Primary Focus: {focus_topic}
Positioning Thesis: {thesis or 'Building intelligent autonomous operating systems and agentic workflows.'}

PILLAR MIX CONFIGURATION:
{json.dumps(pillar_mix, indent=2) if pillar_mix else 'Authority (40%), Actionable (30%), Story (20%), Contrarian (10%)'}

HOOK FORMULA SUMMARY (Pick from F1-F20):
{hook_reference[:1200] if hook_reference else 'F1 to F20 including Odd-Precision Ledger, R.I.P. Obituary, Contrarian receipts, Controlled A/B.'}

Please generate:
1. High-level Sprint Strategy & Narrative Arc.
2. Structured Schedule Table for the {days_count} days:
   - Day & Date
   - Content Pillar
   - Assigned Hook Formula (e.g. F7, F1, F10)
   - Working Title & One-Sentence Concept Angle
   - Engagement Objective (Comments, Reposts, Saves, DMs)
   - Visual / Media Recommendation (Text only, Carousel, Code snippet, Architecture diagram)
3. Return a clean JSON array code-fence at the bottom with schema:
```json
[
  {{
    "day_index": 1,
    "date": "YYYY-MM-DD",
    "pillar": "...",
    "formula_code": "F...",
    "topic": "...",
    "angle": "...",
    "cta_type": "...",
    "media_type": "..."
  }}
]
```
"""

        try:
            output = self.call_llm(
                prompt=prompt,
                system_prompt=system_prompt,
                model=self.cfg.model_primary,
                max_tokens=3000,
            )

            # Try to extract structured JSON calendar
            parsed_calendar = []
            if "```json" in output:
                json_str = output.split("```json", 1)[1].split("```", 1)[0].strip()
                try:
                    parsed_calendar = json.loads(json_str)
                    existing_state = self.read_json_state("content-calendar.json")
                    existing_state["active_sprint"] = {
                        "focus_topic": focus_topic,
                        "generated_at": datetime.now().isoformat(),
                        "calendar": parsed_calendar,
                    }
                    self.write_json_state("content-calendar.json", existing_state)
                except Exception:
                    pass

            return AgentResult(
                success=True,
                agent_id=self.agent_id,
                agent_name=self.agent_name,
                output=output,
                artifacts=["content-calendar.json"] if parsed_calendar else [],
                metadata={"days": days_count, "items_count": len(parsed_calendar)},
            )
        except Exception as e:
            return AgentResult(
                success=False,
                agent_id=self.agent_id,
                agent_name=self.agent_name,
                output="",
                error=str(e),
            )
