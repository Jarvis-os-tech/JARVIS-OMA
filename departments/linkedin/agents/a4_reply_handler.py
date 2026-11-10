"""Agent A4: LinkedIn Reply Handler.
Drafts value-first, relationship-building comment replies that deepen dialogue.
"""

from typing import Any
from .base_agent import BaseLinkedInAgent, AgentResult


class ReplyHandlerAgent(BaseLinkedInAgent):
    agent_id = "A4"
    agent_name = "ReplyHandler"
    description = "Drafts authentic, value-first comment replies that build engagement and relationships."

    def execute(self, task_input: dict[str, Any]) -> AgentResult:
        original_post = task_input.get("original_post", "")
        commenter_name = task_input.get("commenter_name", "Connection")
        comment_text = task_input.get("comment_text", "")
        reply_intent = task_input.get("reply_intent", "deepen discussion")

        voice_profile = self.read_state("voice-profile.md")

        system_prompt = (
            "You are the LinkedIn Reply Handler Agent (A4) in JARVIS OS. "
            "Draft thoughtful, authentic responses to comments on user posts. "
            "Never say generic replies like 'Thanks for sharing!' or 'Great point!'. "
            "Acknowledge the specific point made, add a 1-sentence insight or follow-up question, "
            "and keep the comment thread active."
        )

        prompt = f"""
ORIGINAL POST SNIPPET:
{original_post[:600]}

COMMENT RECEIVED FROM {commenter_name}:
"{comment_text}"

INTENT: {reply_intent}
VOICE PROFILE:
{voice_profile[:600] if voice_profile else 'Warm, technical, peer-to-peer, direct.'}

Generate:
1. Recommended Reply (1-3 sentences, natural and engaging).
2. Alternative Short Reply (Quick, witty, or punchy).
3. Follow-up Question to keep the conversation flowing.
"""

        try:
            output = self.call_llm(
                prompt=prompt,
                system_prompt=system_prompt,
                model=self.cfg.model_primary,
                max_tokens=800,
            )

            return AgentResult(
                success=True,
                agent_id=self.agent_id,
                agent_name=self.agent_name,
                output=output,
                artifacts=[],
                metadata={"commenter": commenter_name, "comment": comment_text},
            )
        except Exception as e:
            return AgentResult(
                success=False,
                agent_id=self.agent_id,
                agent_name=self.agent_name,
                output="",
                error=str(e),
            )
