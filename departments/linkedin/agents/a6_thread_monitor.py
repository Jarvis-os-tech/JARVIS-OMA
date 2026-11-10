"""Agent A6: LinkedIn Thread Monitor.
Monitors industry posts and identifies high-visibility discussion opportunities.
"""

from typing import Any
from .base_agent import BaseLinkedInAgent, AgentResult


class ThreadMonitorAgent(BaseLinkedInAgent):
    agent_id = "A6"
    agent_name = "ThreadMonitor"
    description = "Analyzes external posts to surface high-visibility early commenting opportunities."

    def execute(self, task_input: dict[str, Any]) -> AgentResult:
        external_post = task_input.get("external_post", "")
        author_name = task_input.get("author_name", "Industry Creator")
        relevance_niche = task_input.get("niche", "Autonomous Agents / AI Engineering")

        system_prompt = (
            "You are the LinkedIn Thread Monitor Agent (A6) in JARVIS OS. "
            "Evaluate external industry posts for high-impact comment hijacking (adding peer-level value). "
            "Never flatter blindly. Analyze the thesis, identify what is missing or nuance that needs expansion, "
            "and craft a top-voted comment that demonstrates authority."
        )

        prompt = f"""
EXTERNAL POST BY {author_name}:
"{external_post}"

TARGET NICHE: {relevance_niche}

Generate:
1. Thread Opportunity Assessment (High / Medium / Low score with 1-sentence rationale).
2. The Angle of Distinction (What unique engineering/practical perspective can we contribute?).
3. 2 Authority Comment Drafts:
   - Option A: Complementary framework / additive nuance.
   - Option B: Respectful contrarian counter-example based on production reality.
"""

        try:
            output = self.call_llm(
                prompt=prompt,
                system_prompt=system_prompt,
                model=self.cfg.model_primary,
                max_tokens=1200,
            )

            return AgentResult(
                success=True,
                agent_id=self.agent_id,
                agent_name=self.agent_name,
                output=output,
                artifacts=[],
                metadata={"author": author_name, "post_snippet": external_post[:100]},
            )
        except Exception as e:
            return AgentResult(
                success=False,
                agent_id=self.agent_id,
                agent_name=self.agent_name,
                output="",
                error=str(e),
            )
