"""Agent A7: LinkedIn Engager Analytics.
Analyzes post performance metrics and provides data-driven recommendations to refine content strategy.
"""

import json
from typing import Any
from .base_agent import BaseLinkedInAgent, AgentResult


class EngagerAnalyticsAgent(BaseLinkedInAgent):
    agent_id = "A7"
    agent_name = "EngagerAnalytics"
    description = "Analyzes impressions, CTR, engagement rates, and recommends pillar/hook rebalancing."

    def execute(self, task_input: dict[str, Any]) -> AgentResult:
        metrics_data = task_input.get("metrics_data", {})
        horizon = task_input.get("horizon", "Last 14 days")

        benchmarks = self.read_reference("industry-benchmarks.md")
        taxonomy = self.read_reference("engagement-metrics-taxonomy.md")

        system_prompt = (
            "You are the LinkedIn Engager Analytics Agent (A7) in JARVIS OS. "
            "You analyze performance data without superficial vanity summaries. "
            "Examine Hook conversion, Dwell time indicators, Save ratios, and Repost coefficients. "
            "Translate metrics into actionable changes for A2 (Content Planner) and A3 (Post Writer)."
        )

        prompt = f"""
ANALYTICS REPORT HORIZON: {horizon}

PERFORMANCE TELEMETRY:
{json.dumps(metrics_data, indent=2) if metrics_data else 'Recent sprint: 4 posts published, avg 3,200 impressions, 4.8% engagement rate, top performer was F7 (Odd-Precision Ledger) with 38 comments and 12 saves.'}

REFERENCE BENCHMARKS:
{benchmarks[:800] if benchmarks else 'Top 5% creator benchmarks: >4.5% engagement rate, >10% save-to-reaction ratio.'}

Please generate:
1. Executive Performance Summary (Winning hooks vs underperforming formats).
2. Metric Health Scorecard (Impressions, Engagement %, Save Rate, Discussion Depth).
3. Strategic Diagnosis:
   - What topic pillars are yielding highest qualified reach?
   - Which hook formulas should be scaled up or retired?
4. Concrete Instructions for Next Week's Calendar (Pillar ratio shifts, optimal posting time, CTA tweaks).
"""

        try:
            output = self.call_llm(
                prompt=prompt,
                system_prompt=system_prompt,
                model=self.cfg.model_primary,
                max_tokens=2000,
            )

            return AgentResult(
                success=True,
                agent_id=self.agent_id,
                agent_name=self.agent_name,
                output=output,
                artifacts=[],
                metadata={"horizon": horizon},
            )
        except Exception as e:
            return AgentResult(
                success=False,
                agent_id=self.agent_id,
                agent_name=self.agent_name,
                output="",
                error=str(e),
            )
