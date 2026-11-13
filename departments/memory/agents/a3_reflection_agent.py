"""Agent 3: Reflection Agent.
The Self-Learning Loop: audits failure traces, synthesizes procedural rules,
packages replay test harnesses for evolution.py, and updates the user profile.
"""

from collections import defaultdict
from datetime import datetime
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from .base_memory_agent import BaseMemoryAgent


class ReflectionAgent(BaseMemoryAgent):
    """The Self-Learning Agent analyzing failures and building procedural rules."""

    agent_id: str = "A3"
    agent_name: str = "ReflectionAgent"

    def run_daily_reflection(self) -> Dict[str, Any]:
        """Perform overnight or idle reflection on failures and user patterns."""
        self.logger.info("Starting daily reflection loop...")

        # 1. Audit failed episodic execution traces
        failed_traces = self.db.get_recent_failed_traces(limit=25)
        new_rules = self._synthesize_procedural_rules(failed_traces)

        # 2. Package replay harnesses for evolution.py
        replay_packets = self._package_evolution_replays(failed_traces)

        # 3. Update living user profile from semantic memory
        profile = self._update_user_profile()

        return {
            "failed_traces_analyzed": len(failed_traces),
            "new_procedural_rules_count": len(new_rules),
            "replay_packets_prepared": len(replay_packets),
            "user_profile_updated": bool(profile),
        }

    def _synthesize_procedural_rules(self, traces: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Cluster tool failures and generate new procedural rules."""
        if not traces:
            return []

        # Group by tool name
        by_tool = defaultdict(list)
        for t in traces:
            by_tool[t["tool_name"]].append(t)

        rules_created = []
        rules_file = self.cfg.state_dir / "procedural_rules.json"
        existing_rules = []
        if rules_file.exists():
            try:
                existing_rules = json.loads(rules_file.read_text(encoding="utf-8"))
            except Exception:
                existing_rules = []

        now_str = datetime.now().isoformat()

        for tool_name, tool_traces in by_tool.items():
            if len(tool_traces) >= 1:
                latest = tool_traces[0]
                rule_text = (
                    f"When invoking tool '{tool_name}', avoid previous failure: "
                    f"'{latest.get('error_message') or latest.get('stderr') or 'non-zero exit'}'"
                )
                rule_id = f"rule_{tool_name}_{len(existing_rules) + 1}"

                # Store in database
                self.db.upsert_node(
                    node_id=rule_id,
                    layer="procedural",
                    category="rule",
                    title=f"Fix for {tool_name}",
                    content=rule_text,
                    importance=0.90,
                    provenance="inferred_agent",
                    obsidian_path="05 Procedural Memory/Rules.md",
                )

                rule_obj = {
                    "id": rule_id,
                    "tool": tool_name,
                    "rule": rule_text,
                    "created_at": now_str,
                    "sample_trigger": latest["trigger_prompt"],
                }
                existing_rules.append(rule_obj)
                rules_created.append(rule_obj)

        rules_file.write_text(json.dumps(existing_rules, indent=2, ensure_ascii=False), encoding="utf-8")
        self.logger.info("Synthesized %d new procedural rules", len(rules_created))
        return rules_created

    def _package_evolution_replays(self, traces: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Export replay packets for orchestration/evolution.py bubblewrap tests."""
        replays_dir = self.cfg.state_dir / "evolution_replays"
        replays_dir.mkdir(parents=True, exist_ok=True)

        packets = []
        for t in traces[:10]:
            packet = {
                "trace_id": t["id"],
                "tool_name": t["tool_name"],
                "tool_input": t["tool_input"],
                "trigger_prompt": t["trigger_prompt"],
                "expected_failure_code": t["exit_code"],
                "recorded_stderr": t["stderr"],
                "status": "ready_for_evolution_test",
            }
            packet_path = replays_dir / f"{t['id']}.json"
            packet_path.write_text(json.dumps(packet, indent=2), encoding="utf-8")
            packets.append(packet)

        return packets

    def _update_user_profile(self) -> Dict[str, Any]:
        """Aggregate high-confidence semantic preferences into a living profile."""
        profile_file = self.cfg.state_dir / "user_profile.json"

        # Query top semantic nodes
        semantic_nodes = self.db.search_fts("prefer favorite system python arch hyprland", limit=10, layer="semantic")

        profile = {
            "updated_at": datetime.now().isoformat(),
            "core_preferences": [n["content"] for n in semantic_nodes],
            "target_desktop": "Hyprland / Arch Linux",
            "active_mode": "Sovereign AI-Native Desktop",
        }

        profile_file.write_text(json.dumps(profile, indent=2, ensure_ascii=False), encoding="utf-8")
        return profile
