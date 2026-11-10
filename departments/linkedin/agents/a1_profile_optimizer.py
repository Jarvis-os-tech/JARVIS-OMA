"""Agent A1: LinkedIn Profile Optimizer.
Audits the 9 core profile elements and produces an optimized rewrite and positioning thesis.
"""

from typing import Any
from .base_agent import BaseLinkedInAgent, AgentResult


class ProfileOptimizerAgent(BaseLinkedInAgent):
    agent_id = "A1"
    agent_name = "ProfileOptimizer"
    description = "Audits and rewrites 9 core profile elements into an authority conversion engine."

    def execute(self, task_input: dict[str, Any]) -> AgentResult:
        current_profile = task_input.get("current_profile", "")
        if not current_profile:
            live_summary = self.read_state("live-profile-summary.txt")
            if live_summary:
                current_profile = live_summary

        goal = task_input.get("goal", "client acquisition and authority positioning")
        target_audience = task_input.get("target_audience", "Engineers, founders, tech leaders")

        voice_profile = self.read_state("voice-profile.md")

        system_prompt = (
            "You are the LinkedIn Profile Optimizer Agent (A1) in JARVIS OS. "
            "Your objective is to audit and transform LinkedIn profiles into high-conversion authority assets. "
            "Evaluate across 9 components: Headline, About, Featured, Experience, Skills, Banner Brief, "
            "Creator Topics, Recommendations brief, and CTA button. "
            "Ground your feedback in concrete positioning without fluffy clichés."
        )

        prompt = f"""
AUDIT AND REWRITE REQUEST:
Goal: {goal}
Target Audience: {target_audience}

CURRENT PROFILE CONTENT:
{current_profile}

VOICE RULES & PERSONA:
{voice_profile[:1000] if voice_profile else 'Professional, direct, evidence-led, zero fluff.'}

Please generate:
1. Executive Audit Scorecard (Ratings 1-10 on Hook, Clarity, Authority, Proof, CTA).
2. The Positioning Thesis (1 sentence defining the user's unfair advantage and who they serve).
3. 3 High-Impact Headline Options (Hook + Mechanism + Social Proof).
4. Full 'About' Section Rewrite (Hook, Story spine, Credibility Ledger, Clear CTA).
5. Featured Section Recommendations (Top 3 priority links/artifacts to pin).
6. Experience Bullet Formulas (Action verb + Metric + System built).
7. Top 3 Skills to pin.
"""

        try:
            output = self.call_llm(
                prompt=prompt,
                system_prompt=system_prompt,
                model=self.cfg.model_deep_reasoning,  # Deep audit reasoning
                max_tokens=3000,
            )

            # Store the generated profile thesis in state for other agents
            thesis = ""
            for line in output.splitlines():
                if "Positioning Thesis:" in line or "Thesis:" in line:
                    thesis = line.split(":", 1)[1].strip()
                    break

            if thesis:
                self.write_state("profile-thesis.txt", thesis)

            return AgentResult(
                success=True,
                agent_id=self.agent_id,
                agent_name=self.agent_name,
                output=output,
                artifacts=["profile-thesis.txt"] if thesis else [],
                metadata={"goal": goal, "audience": target_audience, "thesis": thesis},
            )
        except Exception as e:
            return AgentResult(
                success=False,
                agent_id=self.agent_id,
                agent_name=self.agent_name,
                output="",
                error=str(e),
            )
