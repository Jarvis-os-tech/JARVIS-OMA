"""Agent A10: LinkedIn Humanizer & Voice Authenticator.
MANDATORY QUALITY GATE: Scans posts for AI-tells, corporate clichés, and voice uniformity,
producing natural, bursty, human copy.
"""

from typing import Any
from .base_agent import BaseLinkedInAgent, AgentResult

BANNED_AI_MARKERS = [
    "delve", "delving", "game-changer", "testament", "beacon",
    "in today's fast-paced world", "tapestry", "revolutionize", "revolutionizing",
    "plethora", "paramount", "furthermore", "moreover", "cutting-edge",
    "transformative", "seamless", "seamlessly", "harnessing", "unleash", "unleashing",
    "foster", "fostering", "elevate", "elevating", "beacon of", "testament to"
]


class HumanizerAgent(BaseLinkedInAgent):
    agent_id = "A10"
    agent_name = "Humanizer"
    description = "Enforces zero-AI-tell standards, audits voice rhythm, and eliminates generic marketing fluff."

    def execute(self, task_input: dict[str, Any]) -> AgentResult:
        draft_text = task_input.get("draft", "")
        context = task_input.get("context", "")

        voice_profile = self.read_state("voice-profile.md")
        voice_rules = self.read_reference("voice-rules.md")

        # Static rule check
        lower_draft = draft_text.lower()
        found_markers = [marker for marker in BANNED_AI_MARKERS if marker in lower_draft]

        system_prompt = (
            "You are the LinkedIn Humanizer Agent (A10) in JARVIS OS. "
            "You are the unyielding quality airlock before any post can be scheduled or approved. "
            "Your job is to strip out all robotic, sanitized AI phrasing, corporate boilerplate, and monotonic rhythm. "
            "Real humans write with uneven sentence lengths: short punchy fragments mixed with descriptive sentences. "
            "Real humans speak directly, share specific numbers, admit awkward failures, and avoid pseudo-academic transitions."
        )

        prompt = f"""
POST DRAFT TO AUDIT & HUMANIZE:
{draft_text}

USER VOICE PROFILE:
{voice_profile[:1000] if voice_profile else 'Direct, conversational, high technical fidelity, pragmatic, zero corporate speak.'}

VOICE RULES:
{voice_rules[:800] if voice_rules else 'Keep sentences varied. Eliminate buzzwords. Ensure authentic engineer tone.'}

KNOWN DETECTED AI MARKERS:
{', '.join(found_markers) if found_markers else 'None detected by basic regex.'}

OUTPUT INSTRUCTIONS:
Inside <final_output>, output ONLY the final humanized post draft with AI tells removed, natural line spacing, and varied sentence rhythm.
Do not put audit commentary or scores inside <final_output>.
Preserve the supplied facts. Do not add metrics, achievements, or personal experiences.
"""

        try:
            output = self.call_llm(
                prompt=prompt,
                system_prompt=system_prompt,
                model=self.cfg.model_primary,
                max_tokens=2200,
            )

            humanized_text = output.strip() or draft_text
            passed = len(found_markers) == 0 or "Pass" in output

            return AgentResult(
                success=True,
                agent_id=self.agent_id,
                agent_name=self.agent_name,
                output=humanized_text,
                artifacts=[],
                metadata={
                    "authenticity_pass": passed,
                    "flagged_markers": found_markers,
                    "char_count": len(humanized_text),
                    "full_audit_report": output,
                },
            )
        except Exception as e:
            return AgentResult(
                success=False,
                agent_id=self.agent_id,
                agent_name=self.agent_name,
                output=draft_text,
                error=str(e),
            )
