"""Agent A5: LinkedIn Content Repurposer.
Transforms long-form technical documents, meeting notes, or blog posts into carousel slides and post variations.
"""

from typing import Any
from .base_agent import BaseLinkedInAgent, AgentResult


class RepurposerAgent(BaseLinkedInAgent):
    agent_id = "A5"
    agent_name = "Repurposer"
    description = "Repurposes long-form technical docs, code notes, and blogs into high-retention carousels and posts."

    def execute(self, task_input: dict[str, Any]) -> AgentResult:
        source_text = task_input.get("source_text", "")
        target_format = task_input.get("target_format", "carousel")  # 'carousel' or 'bite-sized'
        goal = task_input.get("goal", "saves and reposts")

        system_prompt = (
            "You are the LinkedIn Repurposer Agent (A5) in JARVIS OS. "
            "You convert dense, long-form technical material into highly visual, digestible LinkedIn content. "
            "For carousels: craft 6-10 concise slides with maximum 30 words per slide, clean hierarchy, and visual direction. "
            "For text posts: extract the core counter-intuitive insight and package it with hook-body-ledger structure."
        )

        prompt = f"""
SOURCE MATERIAL:
{source_text[:4000]}

TARGET FORMAT: {target_format}
PRIMARY GOAL: {goal}

Generate:
1. Carousel Blueprint (Slide 1: Hook & Promise, Slides 2-7: One core insight per slide with visual cue, Slide 8: Summary Ledger, Slide 9: Save & Follow CTA).
2. Companion Intro Post (The caption that goes alongside the carousel with a bold hook line).
3. 3 Key Quotes / Soundbites that can be tweeted or shared as standalone micro-posts.
"""

        try:
            output = self.call_llm(
                prompt=prompt,
                system_prompt=system_prompt,
                model=self.cfg.model_primary,
                max_tokens=2500,
            )

            return AgentResult(
                success=True,
                agent_id=self.agent_id,
                agent_name=self.agent_name,
                output=output,
                artifacts=[],
                metadata={"target_format": target_format, "source_length": len(source_text)},
            )
        except Exception as e:
            return AgentResult(
                success=False,
                agent_id=self.agent_id,
                agent_name=self.agent_name,
                output="",
                error=str(e),
            )
