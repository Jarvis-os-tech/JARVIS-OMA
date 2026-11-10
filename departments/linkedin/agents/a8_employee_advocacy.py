"""Agent A8: LinkedIn Employee Advocacy Coordinator.
Creates tailored, natural variations of flagship company posts for team members and collaborators.
"""

from typing import Any
from .base_agent import BaseLinkedInAgent, AgentResult


class EmployeeAdvocacyAgent(BaseLinkedInAgent):
    agent_id = "A8"
    agent_name = "EmployeeAdvocacy"
    description = "Generates role-specific, authentic post variations for team amplification without robotic repetition."

    def execute(self, task_input: dict[str, Any]) -> AgentResult:
        master_post = task_input.get("master_post", "")
        roles = task_input.get("roles", ["Lead Engineer", "Product Manager", "Founding Designer"])

        system_prompt = (
            "You are the LinkedIn Employee Advocacy Agent (A8) in JARVIS OS. "
            "Never create copy-paste corporate shill posts. "
            "When team members reshare or post about an announcement, each post must come from that person's "
            "unique day-to-day vantage point: the engineer talks about technical hurdles solved, "
            "the designer talks about user feedback iterations, the product manager talks about the vision."
        )

        prompt = f"""
FLAGSHIP MASTER POST:
{master_post}

ROLES TO ADAPT FOR:
{', '.join(roles)}

Generate:
For each role:
1. Perspective Angle (Why this matters to their craft).
2. Complete Post Draft (150-250 words, completely different opening hook and voice from the master post).
3. Recommended Tagging & Link strategy (How to credit the core launch without triggering algorithmic reach penalties).
"""

        try:
            output = self.call_llm(
                prompt=prompt,
                system_prompt=system_prompt,
                model=self.cfg.model_primary,
                max_tokens=2200,
            )

            return AgentResult(
                success=True,
                agent_id=self.agent_id,
                agent_name=self.agent_name,
                output=output,
                artifacts=[],
                metadata={"roles": roles},
            )
        except Exception as e:
            return AgentResult(
                success=False,
                agent_id=self.agent_id,
                agent_name=self.agent_name,
                output="",
                error=str(e),
            )
