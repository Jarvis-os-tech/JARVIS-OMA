"""Agent 3: Reflection Agent.
The Self-Learning Loop: audits failure traces, synthesizes procedural rules,
packages replay test harnesses for evolution.py, and updates the user profile.
"""

from collections import defaultdict
from datetime import datetime
import json
from hashlib import sha256
from typing import Any, Dict, List

from .base_memory_agent import BaseMemoryAgent, write_private_text


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
        existing_rules = json.loads(rules_file.read_text(encoding="utf-8")) if rules_file.exists() else []
        known = {(item["tool"], item["rule"]) for item in existing_rules}
        for tool_name, tool_traces in by_tool.items():
            latest = self.redact_diagnostics(tool_traces[0])
            message = latest.get("error_message") or latest.get("stderr") or "non-zero exit"
            rule_text = f"When invoking tool '{tool_name}', avoid previous failure: '{message}'"
            if (tool_name, rule_text) in known:
                continue
            rule_id = "rule_" + sha256(rule_text.encode()).hexdigest()[:24]
            if self.db.get_node(rule_id) is None:
                self.db.upsert_node(
                    node_id=rule_id,
                    layer="procedural",
                    category="rule",
                    title=f"Fix for {tool_name}",
                    content=rule_text,
                    importance=0.90,
                    provenance="inferred_agent",
                )
            rules_created.append({
                "id": rule_id,
                "tool": tool_name,
                "rule": rule_text,
                "created_at": datetime.now().isoformat(),
                "sample_trigger": latest["trigger_prompt"],
            })
        if rules_created:
            write_private_text(rules_file, json.dumps(existing_rules + rules_created, indent=2, ensure_ascii=False))
        self.logger.info("Synthesized %d new procedural rules", len(rules_created))
        return rules_created

    def _package_evolution_replays(self, traces: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Export replay packets for orchestration/evolution.py bubblewrap tests."""
        replays_dir = self.cfg.state_dir / "evolution_replays"
        replays_dir.mkdir(parents=True, exist_ok=True)

        packets = []
        for trace in traces[:10]:
            t = self.redact_diagnostics(trace)
            try:
                inputs = self.redact_diagnostics(json.loads(t["tool_input"]))
            except (ValueError, TypeError):
                inputs = {}
            packet = {
                "trace_id": t["id"],
                "tool_name": t["tool_name"],
                "tool_input": json.dumps(inputs, ensure_ascii=False),
                "trigger_prompt": t["trigger_prompt"],
                "expected_failure_code": t["exit_code"],
                "recorded_stderr": t["stderr"],
                "status": "ready_for_evolution_test",
            }
            packet_id = sha256(t["id"].encode()).hexdigest()
            packet_path = replays_dir / f"{packet_id}.json"
            content = json.dumps(packet, indent=2)
            if not packet_path.exists() or packet_path.read_text(encoding="utf-8") != content:
                write_private_text(packet_path, content)
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

        write_private_text(profile_file, json.dumps(profile, indent=2, ensure_ascii=False))
        return profile
