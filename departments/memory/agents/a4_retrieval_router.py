"""Agent 4: Retrieval Router Agent.
The Read Path: sub-25ms pre-response router executing FTS5 BM25 search
plus Recursive CTE graph traversal to inject clean, high-signal context into Gemini Live.
"""

import time
from typing import Any, Dict, List, Optional

from .base_memory_agent import BaseMemoryAgent


class RetrievalRouterAgent(BaseMemoryAgent):
    """The Read Path context retriever for sub-25ms prompt injection."""

    agent_id: str = "A4"
    agent_name: str = "RetrievalRouter"

    def route_and_retrieve(
        self,
        prompt: str,
        max_items: int = 4,
        max_words: int = 300,
    ) -> str:
        """Analyze intent, query FTS5 + graph edges, and assemble prompt context."""
        start_time = time.perf_counter()
        clean_prompt = self.mask_secrets(prompt.strip())

        if not clean_prompt or len(clean_prompt) < 3:
            return ""

        # 1. Target layer classification
        target_layer = self._detect_target_layer(clean_prompt)

        # 2. SQLite FTS5 BM25 full-text lookup
        max_items = min(max(max_items, 0), 20)
        if not max_items or max_words <= 0:
            return ""
        matches = self.db.search_fts(clean_prompt, limit=max_items, layer=target_layer)
        if target_layer and not matches:
            matches = self.db.search_fts(clean_prompt, limit=max_items)

        # 3. If top match exists, traverse graph edges for adjacent rules / context
        enriched_nodes: List[Dict[str, Any]] = list(matches)
        if matches:
            top_node_id = matches[0]["id"]
            graph_relatives = self.db.traverse_graph(
                top_node_id,
                relations=["fixed_by", "relates_to", "caused_by"],
                max_depth=2,
            )
            # Add unique graph relatives
            existing_ids = {m["id"] for m in enriched_nodes}
            for gr in graph_relatives:
                if gr["id"] not in existing_ids:
                    enriched_nodes.append(gr)
                    existing_ids.add(gr["id"])

        if not enriched_nodes:
            return ""

        # 4. Format into compact, high-signal context injection string
        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        self.logger.debug("Retrieval completed in %.2f ms (%d items)", elapsed_ms, len(enriched_nodes))

        return self._format_context_packet(enriched_nodes[:max_items], max_words)

    def _detect_target_layer(self, text: str) -> Optional[str]:
        """Optionally bias search toward a specific memory layer."""
        lower = text.lower()
        if any(w in lower for w in ["yesterday", "last week", "did we", "history", "previous"]):
            return "episodic"
        if any(w in lower for w in ["how to", "rule", "command", "fix", "troubleshoot"]):
            return "procedural"
        if any(w in lower for w in ["who is", "my favorite", "my preference", "do i like"]):
            return "semantic"
        return None  # Search all layers

    def _format_context_packet(self, nodes: List[Dict[str, Any]], max_words: int) -> str:
        """Format nodes into a concise system prompt injection."""
        lines = ["[JARVIS MEMORY CONTEXT]"]
        total_words = 0

        for n in nodes:
            line = f"• [{n.get('layer', 'semantic').upper()}] {n.get('title', '')}: {n.get('content', '')}"
            words_in_line = len(line.split())
            remaining = max_words - total_words
            lines.append(line if words_in_line <= remaining else " ".join(line.split()[:remaining]))
            total_words += min(words_in_line, remaining)
            if total_words >= max_words:
                break

        lines.append("[END CONTEXT]")
        return "\n".join(lines)
