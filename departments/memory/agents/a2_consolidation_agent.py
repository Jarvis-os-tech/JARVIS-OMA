"""Agent 2: Consolidation Agent.
The Update Path: executes the 4-way decision matrix (ADD, UPDATE, SUPERSEDE, NO-OP),
prevents duplicate facts, generates graph edges, and syncs to Obsidian notes.
"""

from pathlib import Path
import re
from typing import Any, Dict

from .base_memory_agent import BaseMemoryAgent, MemoryCandidate, write_private_text


class ConsolidationAgent(BaseMemoryAgent):
    """The Update Path consolidation and de-duplication agent."""

    agent_id: str = "A2"
    agent_name: str = "ConsolidationAgent"

    def consolidate(self, candidate: MemoryCandidate) -> Dict[str, Any]:
        """Process candidate memory through the 4-way decision matrix."""
        if not re.fullmatch(r"[a-zA-Z0-9_-]+", candidate.category):
            raise ValueError("Invalid memory category")
        relative_path = Path("Memory Department") / "Facts" / f"{candidate.category}.md"
        vault = self.cfg.obsidian_vault_path.resolve()
        note = vault / relative_path
        if note.resolve() != note:
            raise ValueError("Memory Department fact note must not be a symlink")

        with self.db.write_transaction() as conn:
            matches = self.db.search_fts(candidate.content, limit=10, layer=candidate.layer,
                                         category=candidate.category)
            exact = next((item for item in matches
                          if item["content"].strip().casefold() == candidate.content.strip().casefold()), None)
            top_match = exact or next((item for item in matches if item["title"] == candidate.title), None)
            decision = "ADD"
            target_id = candidate.id
            superseded_id = None
            if exact:
                decision, target_id = "NO-OP", exact["id"]
            elif top_match and self._is_contradiction(top_match, candidate):
                decision, superseded_id = "SUPERSEDE", top_match["id"]
            elif top_match:
                decision, target_id = "UPDATE", top_match["id"]

            if top_match and top_match["provenance"] == "explicit_user" and candidate.provenance != "explicit_user":
                return {"decision": "NO-OP", "node_id": top_match["id"], "status": "preserved_explicit"}

            if superseded_id:
                conn.execute("DELETE FROM memory_edges WHERE relation = 'supersedes' AND target_id = ?",
                             (target_id,))
            self.db.upsert_node(
                node_id=target_id, layer=candidate.layer, category=candidate.category,
                content=exact["content"] if exact else candidate.content,
                title=exact["title"] if exact else candidate.title,
                importance=max(exact["importance"], candidate.importance) if exact else candidate.importance,
                provenance=candidate.provenance,
                ttl_expires_at=exact["ttl_expires_at"] if exact else candidate.ttl_expires_at,
                obsidian_path=str(relative_path),
            )
            if superseded_id and superseded_id != target_id:
                self.db.add_edge(target_id, "supersedes", superseded_id)
            for related_id in candidate.related_to:
                self.db.add_edge(target_id, candidate.relation_type, related_id)

        # Rebuild from committed rows so a retry also repairs a failed projection.
        with self.db.write_transaction():
            if note.resolve() != note:
                raise ValueError("Memory Department fact note must not be a symlink")
            nodes = self.db.nodes_for_note(str(relative_path))
            note.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            lines = [f"# {candidate.category.capitalize()} Knowledge", ""]
            for node in nodes:
                lines.append(f"- **{node['title']}**: {node['content']}")
            write_private_text(note, "\n".join(lines) + "\n")

        return {"decision": decision, "node_id": target_id, "superseded_id": superseded_id,
                "layer": candidate.layer, "category": candidate.category}

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
