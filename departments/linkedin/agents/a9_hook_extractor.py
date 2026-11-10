"""Agent A9: LinkedIn Hook Extractor.
Reverse-engineers viral LinkedIn posts into modular hook formulas and reusable skeletons.
"""

from typing import Any
from .base_agent import BaseLinkedInAgent, AgentResult


class HookExtractorAgent(BaseLinkedInAgent):
    agent_id = "A9"
    agent_name = "HookExtractor"
    description = "Deconstructs viral posts into structural hook formulas, psychological drivers, and fill-in-the-blank skeletons."

    def execute(self, task_input: dict[str, Any]) -> AgentResult:
        viral_post_text = task_input.get("post_text", "")
        target_domain = task_input.get("domain", "Autonomous AI Agents / Systems Engineering")

        system_prompt = (
            "You are the LinkedIn Hook Extractor Agent (A9) in JARVIS OS. "
            "Analyze viral LinkedIn posts with forensic precision. "
            "Identify the psychological levers: curiosity gaps, contrarian stakes, vulnerability, "
            "odd-precision ledgers, or status reversals. "
            "Extract the underlying reusable formula and adapt it for the user's engineering domain."
        )

        prompt = f"""
VIRAL POST TO ANALYZE:
"{viral_post_text}"

TARGET DOMAIN FOR ADAPTATION:
{target_domain}

Generate:
1. Architectural Deconstruction:
   - The Hook Line Mechanism (Word choice, line length, visual pause).
   - The Tension Setup (What assumption is broken in lines 2-4?).
   - The Proof Ledger (How credibility is established in the body).
   - The Payoff & CTA (How engagement is extracted).
2. The Abstract Formula Skeleton (Fill-in-the-blank template using [brackets]).
3. 3 Custom Hook Variations adapted for {target_domain}.
"""

        try:
            output = self.call_llm(
                prompt=prompt,
                system_prompt=system_prompt,
                model=self.cfg.model_primary,
                max_tokens=1800,
            )

            return AgentResult(
                success=True,
                agent_id=self.agent_id,
                agent_name=self.agent_name,
                output=output,
                artifacts=[],
                metadata={"domain": target_domain, "source_snippet": viral_post_text[:100]},
            )
        except Exception as e:
            return AgentResult(
                success=False,
                agent_id=self.agent_id,
                agent_name=self.agent_name,
                output="",
                error=str(e),
            )
