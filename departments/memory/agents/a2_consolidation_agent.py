"""Agent 2: Consolidation Agent.
The Update Path: executes the 4-way decision matrix (ADD, UPDATE, SUPERSEDE, NO-OP),
prevents duplicate facts, generates graph edges, and syncs to Obsidian notes.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from .base_memory_agent import BaseMemoryAgent, MemoryCandidate


class ConsolidationAgent(BaseMemoryAgent):
    """The Update Path consolidation and de-duplication agent."""

    agent_id: str = "A2"
    agent_name: str = "ConsolidationAgent"

    def consolidate(self, candidate: MemoryCandidate) -> Dict[str, Any]:
        """Process candidate memory through the 4-way decision matrix."""
        # 1. Search for existing similar nodes in the same category
        similar_nodes = self.db.search_fts(candidate.content, limit=3, layer=candidate.layer)

        decision = "ADD"
        target_node_id = candidate.id
        superseded_id: Optional[str] = None

        if similar_nodes:
            top_match = similar_nodes[0]
            # Exact or near-identical match -> NO-OP
            if top_match["content"].strip().lower() == candidate.content.strip().lower():
                decision = "NO-OP"
                target_node_id = top_match["id"]
                # Bump reinforcement count
                self.db.upsert_node(
                    node_id=top_match["id"],
                    layer=top_match["layer"],
                    category=top_match["category"],
                    content=top_match["content"],
                    title=top_match["title"],
                    importance=max(top_match["importance"], candidate.importance),
                    provenance=candidate.provenance,
                    ttl_expires_at=candidate.ttl_expires_at,
                )
                self.logger.info("Consolidation decision [NO-OP]: reinforced existing node %s", target_node_id)
                return {"decision": decision, "node_id": target_node_id, "status": "reinforced"}

            # Contradiction / Supersede detection
            if self._is_contradiction(top_match, candidate):
                decision = "SUPERSEDE"
                superseded_id = top_match["id"]
                self.logger.info("Consolidation decision [SUPERSEDE]: %s replaces %s", candidate.id, superseded_id)

            # Informational update (same subject, refined details)
            elif top_match["category"] == candidate.category and top_match["title"] == candidate.title:
                decision = "UPDATE"
                target_node_id = top_match["id"]
                self.logger.info("Consolidation decision [UPDATE]: updating %s with new data", target_node_id)

        # 2. Commit Node to SQLite
        self.db.upsert_node(
            node_id=target_node_id,
            layer=candidate.layer,
            category=candidate.category,
            content=candidate.content,
            title=candidate.title,
            importance=candidate.importance,
            provenance=candidate.provenance,
            ttl_expires_at=candidate.ttl_expires_at,
            obsidian_path=candidate.obsidian_path,
        )

        # 3. Create Graph Edges
        if superseded_id:
            self.db.add_edge(target_node_id, "supersedes", superseded_id, weight=1.0)

        for rel_id in candidate.related_to:
            self.db.add_edge(target_node_id, candidate.relation_type, rel_id, weight=0.8)

        # 4. Sync to Obsidian Vault
        self._sync_to_obsidian(candidate)

        return {
            "decision": decision,
            "node_id": target_node_id,
            "superseded_id": superseded_id,
            "layer": candidate.layer,
            "category": candidate.category,
        }

    def _is_contradiction(self, existing: Dict[str, Any], candidate: MemoryCandidate) -> bool:
        """Detect if candidate contradicts an existing preference or setting."""
        if existing["category"] != candidate.category:
            return False
        # If both are preferences in the same domain but content opposes
        ex_content = existing["content"].lower()
        cand_content = candidate.content.lower()
        contradiction_pairs = [
            ("wayland", "x11"),
            ("hyprland", "i3"),
            ("hyprland", "sway"),
            ("python", "bash"),
            ("light mode", "dark mode"),
        ]
        for a, b in contradiction_pairs:
            if (a in ex_content and b in cand_content) or (b in ex_content and a in cand_content):
                return True
        return False

    def _sync_to_obsidian(self, candidate: MemoryCandidate) -> None:
        """Append or update fact in the Obsidian Markdown vault."""
        rel_path = candidate.obsidian_path
        if not rel_path:
            if (self.cfg.obsidian_vault_path / "Personal").is_dir():
                if candidate.category == "preference":
                    rel_path = "Personal/Preferences.md"
                elif candidate.category == "rule":
                    rel_path = "Personal/Rules & Constraints.md"
                elif candidate.category in ("hardware", "system"):
                    rel_path = "Personal/System & Environment.md"
                else:
                    rel_path = "Personal/Instructions.md"
            else:
                rel_path = f"04 Semantic Memory/Facts/{candidate.category}.md"

        vault_file = self.cfg.obsidian_vault_path / rel_path
        vault_file.parent.mkdir(parents=True, exist_ok=True)

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = (
            f"\n- **{candidate.title}** ({now_str})\n"
            f"  - Content: {candidate.content}\n"
            f"  - Provenance: `[[{candidate.provenance}]]` | Importance: `{candidate.importance}`\n"
        )

        if not vault_file.exists():
            header = (
                f"---\n"
                f"category: {candidate.category}\n"
                f"layer: {candidate.layer}\n"
                f"updated_at: {now_str}\n"
                f"---\n\n"
                f"# {candidate.category.capitalize()} Knowledge\n\n"
                f"Managed automatically by [[JARVIS OS Memory Department]].\n\n"
                f"### Entries\n"
            )
            vault_file.write_text(header + entry, encoding="utf-8")
        else:
            try:
                with open(vault_file, "a", encoding="utf-8") as f:
                    f.write(entry)
            except Exception as e:
                self.logger.warning("Failed appending to Obsidian vault note %s: %s", vault_file, e)
