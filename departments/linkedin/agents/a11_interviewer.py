"""Agent A11: LinkedIn Interviewer & Story Miner.
Interviews the user asynchronously to mine raw engineering stories and append them to story-bank.md.
"""

from typing import Any
from .base_agent import BaseLinkedInAgent, AgentResult


class InterviewerAgent(BaseLinkedInAgent):
    agent_id = "A11"
    agent_name = "Interviewer"
    description = "Asks targeted probing questions to mine authentic stories, breakthroughs, and metrics for the story bank."

    def execute(self, task_input: dict[str, Any]) -> AgentResult:
        mode = task_input.get("mode", "ask_questions")  # 'ask_questions' or 'synthesize_story'
        seed_topic = task_input.get("seed_topic", "A recent technical obstacle or architecture milestone")
        user_responses = task_input.get("user_responses", "")

        system_prompt = (
            "You are the LinkedIn Interviewer Agent (A11) in JARVIS OS. "
            "You extract high-signal narrative gold from engineering leaders and founders. "
            "Don't ask soft generic questions. Probe for: "
            "1. The exact moment things broke or failed. "
            "2. The counter-intuitive realization that unlocked the fix. "
            "3. The specific numbers/metrics before and after. "
            "4. The unwritten rule or sacred cow that was questioned."
        )

        if mode == "ask_questions":
            prompt = f"""
SEED TOPIC: {seed_topic}

Generate:
1. Context Framing (Why this topic makes for an extraordinary LinkedIn post).
2. 4 Sharp, Probing Interview Questions:
   - Question 1: The Inciting Incident & Friction (What broke, who complained, or what looked impossible?).
   - Question 2: The False Solution (What was tried first that failed?).
   - Question 3: The Technical / Strategic Breakthrough (What was the exact realization?).
   - Question 4: The Quantified Ledger (What are the real numbers: latency, cost, time, headcount, or revenue?).
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
                    metadata={"mode": "ask_questions", "seed_topic": seed_topic},
                )
            except Exception as e:
                return AgentResult(
                    success=False,
                    agent_id=self.agent_id,
                    agent_name=self.agent_name,
                    output="",
                    error=str(e),
                )
        else:
            # Mode: synthesize_story into story-bank.md
            prompt = f"""
SEED TOPIC: {seed_topic}
USER'S RAW INTERVIEW ANSWERS:
{user_responses}

Synthesize these raw answers into a structured Story Bank Entry:
- Title / Story Code
- Core Tension / Catalyst
- Chronological Spine (Beginning, Climax, Resolution)
- Numerical & Hard Evidence Ledger
- Key Moral / Takeaway
- Suggested Hook Formulas (e.g. F3, F7, F11)
"""
            try:
                output = self.call_llm(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    model=self.cfg.model_primary,
                    max_tokens=1800,
                )

                # Append to state/story-bank.md
                story_bank_current = self.read_state("story-bank.md")
                updated_bank = f"{story_bank_current}\n\n---\n\n## {seed_topic}\n\n{output}\n"
                self.write_state("story-bank.md", updated_bank)

                return AgentResult(
                    success=True,
                    agent_id=self.agent_id,
                    agent_name=self.agent_name,
                    output=output,
                    artifacts=["story-bank.md"],
                    metadata={"mode": "synthesize_story", "seed_topic": seed_topic},
                )
            except Exception as e:
                return AgentResult(
                    success=False,
                    agent_id=self.agent_id,
                    agent_name=self.agent_name,
                    output="",
                    error=str(e),
                )
