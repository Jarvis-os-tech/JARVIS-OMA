"""Agent A3: LinkedIn Post Writer.
Drafts high-converting long-form LinkedIn posts using 20 proven hook formulas.
"""

from typing import Any
from .base_agent import BaseLinkedInAgent, AgentResult


class PostWriterAgent(BaseLinkedInAgent):
    agent_id = "A3"
    agent_name = "PostWriter"
    description = "Drafts authentic, high-converting posts using 20 tested hook formulas and clear readability."

    def execute(self, task_input: dict[str, Any]) -> AgentResult:
        topic = task_input.get("topic", "")
        angle = task_input.get("angle", "")
        formula_code = task_input.get("formula_code", "F7")
        pillar = task_input.get("pillar", "Authority & Build Logs")
        cta_type = task_input.get("cta_type", "Specific question")

        voice_profile = self.read_state("voice-profile.md")
        story_bank = self.read_state("story-bank.md")
        hook_references = self.read_reference("hook-formulas.md")

        # Find specific formula section if possible
        formula_text = ""
        if formula_code in hook_references:
            idx = hook_references.find(f"### {formula_code}")
            if idx != -1:
                end_idx = hook_references.find("### F", idx + 5)
                formula_text = hook_references[idx:end_idx] if end_idx != -1 else hook_references[idx:idx+2000]

        system_prompt = (
            "You are the LinkedIn Post Writer Agent (A3) in JARVIS OS. "
            "Write authentic, gripping, long-form LinkedIn posts. "
            "Follow LinkedIn formatting rules: short punchy lines, line breaks between thoughts, "
            "no dense walls of text, no cheesy motivational fluff, no banned AI words ('delve', 'beacon', 'testament'). "
            "Lead with a visceral or data-driven hook, deliver real technical/strategic value in the body, "
            "and close with an open-ended question or clear CTA."
        )

        prompt = f"""
WRITING BRIEF:
Topic: {topic}
Angle: {angle}
Pillar: {pillar}
Formula Code: {formula_code}
CTA Type: {cta_type}

SELECTED FORMULA SPECIFICATION:
{formula_text if formula_text else f'Use formula {formula_code} (punchy 1-2 line hook, setup, tension, resolution, ledger of facts).'}

VOICE PROFILE:
{voice_profile[:1000] if voice_profile else 'Conversational, engineer-to-engineer, transparent about failures and numbers.'}

RELEVANT STORY BANK SEED:
{story_bank[:800] if story_bank else 'Building complex agentic systems and multi-agent coordination.'}

OUTPUT INSTRUCTIONS:
Inside <final_output>, output ONLY the final ready-to-publish LinkedIn post draft with its hook, body lines, spacing, and ending CTA.
Do not put explanations, notes, or character counts inside <final_output>.
"""

        try:
            output = self.call_llm(
                prompt=prompt,
                system_prompt=system_prompt,
                model=self.cfg.model_primary,
                max_tokens=2500,
            )

            draft = output.strip()

            return AgentResult(
                success=True,
                agent_id=self.agent_id,
                agent_name=self.agent_name,
                output=draft,
                artifacts=[],
                metadata={
                    "topic": topic,
                    "formula_code": formula_code,
                    "pillar": pillar,
                    "char_count": len(draft),
                    "full_report": output,
                },
            )
        except Exception as e:
            return AgentResult(
                success=False,
                agent_id=self.agent_id,
                agent_name=self.agent_name,
                output="",
                error=str(e),
            )
