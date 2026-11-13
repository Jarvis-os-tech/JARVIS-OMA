"""Database connection and query engine for the JARVIS OS Memory Graph.
Provides SQLite WAL connectivity, FTS5 full-text search, zero-RAM Recursive CTE graph traversal,
and TTL expiration purging.
"""

from contextlib import contextmanager
import json
import logging
from pathlib import Path
import sqlite3
import time
from typing import Any, Dict, Generator, List, Optional, Tuple

logger = logging.getLogger("departments.memory.db")


class MemoryDatabase:
    """Zero-RAM graph & FTS5 full-text search database engine."""

    def __init__(self, db_path: Path, schema_path: Optional[Path] = None):
        self.db_path = Path(db_path).resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.schema_path = schema_path or (Path(__file__).resolve().parent / "schema.sql")
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Create a connection with WAL mode and foreign keys enabled."""
        conn = sqlite3.connect(
            str(self.db_path),
            timeout=10.0,
            check_same_thread=False,
            isolation_level=None,  # Autocommit mode, use explicit transactions when needed
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        return conn

    @contextmanager
    def connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Context manager for thread-safe scoped connections."""
        conn = self._get_connection()
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self) -> None:
        """Execute schema.sql if database tables are not yet initialized."""
        if not self.schema_path.exists():
            raise FileNotFoundError(f"Schema file not found at {self.schema_path}")

        schema_sql = self.schema_path.read_text(encoding="utf-8")
        with self.connection() as conn:
            conn.executescript(schema_sql)
        logger.debug("Memory database initialized at %s", self.db_path)

    # -------------------------------------------------------------------------
    # Node Operations (Working, Semantic, Episodic, Procedural)
    # -------------------------------------------------------------------------
    def upsert_node(
        self,
        node_id: str,
        layer: str,
        category: str,
        content: str,
        title: Optional[str] = None,
        importance: float = 0.5,
        provenance: str = "inferred_agent",
        ttl_expires_at: Optional[int] = None,
        obsidian_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Insert or update a memory node."""
        now = int(time.time())
        title = title or content[:50]

        sql = """
        INSERT INTO memory_nodes (
            id, layer, category, title, content, importance,
            provenance, ttl_expires_at, obsidian_path, reinforcement_count,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            title = excluded.title,
            content = excluded.content,
            importance = excluded.importance,
            provenance = excluded.provenance,
            ttl_expires_at = excluded.ttl_expires_at,
            obsidian_path = COALESCE(excluded.obsidian_path, memory_nodes.obsidian_path),
            reinforcement_count = memory_nodes.reinforcement_count + 1,
            updated_at = excluded.updated_at;
        """
        with self.connection() as conn:
            conn.execute(
                sql,
                (
                    node_id,
                    layer,
                    category,
                    title,
                    content,
                    importance,
                    provenance,
                    ttl_expires_at,
                    obsidian_path,
                    now,
                    now,
                ),
            )
        return self.get_node(node_id) or {}

    def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a single node by ID."""
        with self.connection() as conn:
            row = conn.execute(
                "SELECT * FROM memory_nodes WHERE id = ?", (node_id,)
            ).fetchone()
            if row:
                return dict(row)
        return None

    def delete_node(self, node_id: str) -> bool:
        """Delete a node and cascade-delete its edges."""
        with self.connection() as conn:
            cursor = conn.execute("DELETE FROM memory_nodes WHERE id = ?", (node_id,))
            return cursor.rowcount > 0

    def purge_expired_ttl(self) -> int:
        """Delete all temporary memory nodes whose TTL has elapsed."""
        now = int(time.time())
        with self.connection() as conn:
            cursor = conn.execute(
                "DELETE FROM memory_nodes WHERE ttl_expires_at IS NOT NULL AND ttl_expires_at <= ?",
                (now,),
            )
            count = cursor.rowcount
            if count > 0:
                logger.info("Purged %d expired memory nodes", count)
            return count

    # -------------------------------------------------------------------------
    # Edge Operations (Graph Relationships)
    # -------------------------------------------------------------------------
    def add_edge(
        self,
        source_id: str,
        relation: str,
        target_id: str,
        weight: float = 1.0,
    ) -> bool:
        """Create a typed edge between two memory nodes."""
        now = int(time.time())
        sql = """
        INSERT INTO memory_edges (source_id, relation, target_id, weight, created_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(source_id, relation, target_id) DO UPDATE SET
            weight = excluded.weight;
        """
        with self.connection() as conn:
            try:
                conn.execute(sql, (source_id, relation, target_id, weight, now))
                return True
            except sqlite3.IntegrityError as e:
                logger.warning("Could not add edge (%s -[%s]-> %s): %s", source_id, relation, target_id, e)
                return False

    def get_edges(self, node_id: str) -> List[Dict[str, Any]]:
        """Get all outgoing and incoming edges for a node."""
        sql = """
        SELECT source_id, relation, target_id, weight, created_at
        FROM memory_edges
        WHERE source_id = ? OR target_id = ?;
        """
        with self.connection() as conn:
            rows = conn.execute(sql, (node_id, node_id)).fetchall()
            return [dict(r) for r in rows]

    def traverse_graph(
        self,
        start_node_id: str,
        relations: Optional[List[str]] = None,
        max_depth: int = 2,
    ) -> List[Dict[str, Any]]:
        """Perform a multi-hop graph traversal using an SQLite Recursive CTE.
        Zero memory footprint: runs natively in the SQLite engine.
        """
        rel_filter = ""
        params: List[Any] = [start_node_id]

        if relations:
            placeholders = ",".join("?" for _ in relations)
            rel_filter = f"AND e.relation IN ({placeholders})"
            params.extend(relations)

        params.append(max_depth)

        sql = f"""
        WITH RECURSIVE memory_graph AS (
            -- Base case: find adjacent nodes from start_node_id
            SELECT 
                e.source_id,
                e.relation,
                e.target_id,
                e.weight,
                1 AS depth
            FROM memory_edges e
            WHERE e.source_id = ? {rel_filter}

            UNION ALL

            -- Recursive step: traverse outward up to max_depth
            SELECT 
                e.source_id,
                e.relation,
                e.target_id,
                e.weight,
                mg.depth + 1
            FROM memory_edges e
            JOIN memory_graph mg ON e.source_id = mg.target_id
            WHERE mg.depth < ? {rel_filter}
        )
        SELECT DISTINCT
            n.id,
            n.layer,
            n.category,
            n.title,
            n.content,
            n.importance,
            mg.relation,
            mg.weight,
            mg.depth
        FROM memory_graph mg
        JOIN memory_nodes n ON mg.target_id = n.id
        ORDER BY mg.depth ASC, n.importance DESC;
        """

        with self.connection() as conn:
            # We must duplicate rel_filter params for the UNION ALL step
            expanded_params: List[Any] = [start_node_id]
            if relations:
                expanded_params.extend(relations)
            expanded_params.append(max_depth)
            if relations:
                expanded_params.extend(relations)

            rows = conn.execute(sql, expanded_params).fetchall()
            return [dict(r) for r in rows]

    # -------------------------------------------------------------------------
    # Search Operations (FTS5 BM25 Search)
    # -------------------------------------------------------------------------
    def search_fts(
        self,
        query: str,
        limit: int = 5,
        layer: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Search memory nodes using SQLite FTS5 with BM25 ranking."""
        clean_query = "".join(c for c in query if c.isalnum() or c in (" ", "-", "_", "*")).strip()
        if not clean_query:
            return []

        # Convert words into prefix match terms
        terms = [f'"{term}"*' for term in clean_query.split() if len(term) > 1]
        if not terms:
            return []
        fts_expr = " OR ".join(terms)

        params: List[Any] = [fts_expr]
        layer_clause = ""
        if layer:
            layer_clause = "AND n.layer = ?"
            params.append(layer)
        params.append(limit)

        sql = f"""
        SELECT 
            n.id,
            n.layer,
            n.category,
            n.title,
            n.content,
            n.importance,
            n.provenance,
            n.obsidian_path,
            n.updated_at,
            bm25(memory_fts) AS rank_score
        FROM memory_fts f
        JOIN memory_nodes n ON f.id = n.id
        WHERE memory_fts MATCH ? {layer_clause}
        ORDER BY rank_score ASC, n.importance DESC
        LIMIT ?;
        """

        with self.connection() as conn:
            try:
                rows = conn.execute(sql, params).fetchall()
                return [dict(r) for r in rows]
            except sqlite3.OperationalError as e:
                logger.warning("FTS search error for query '%s': %s", fts_expr, e)
                return []

    # -------------------------------------------------------------------------
    # Replayable Execution Traces (for evolution.py self-improvement)
    # -------------------------------------------------------------------------
    def record_trace(
        self,
        trace_id: str,
        session_id: str,
        trigger_prompt: str,
        tool_name: str,
        tool_input: Dict[str, Any],
        exit_code: int,
        stdout: Optional[str] = None,
        stderr: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> bool:
        """Record an immutable tool or subagent execution trace."""
        now = int(time.time())
        sql = """
        INSERT INTO episodic_traces (
            id, session_id, trigger_prompt, tool_name, tool_input,
            exit_code, stdout, stderr, error_message, replay_status, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?);
        """
        with self.connection() as conn:
            conn.execute(
                sql,
                (
                    trace_id,
                    session_id,
                    trigger_prompt,
                    tool_name,
                    json.dumps(tool_input, ensure_ascii=False),
                    exit_code,
                    stdout or "",
                    stderr or "",
                    error_message or "",
                    now,
                ),
            )
        return True

    def get_recent_failed_traces(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Retrieve recent failed traces for reflection and evolution test generation."""
        sql = """
        SELECT * FROM episodic_traces
        WHERE exit_code != 0
        ORDER BY created_at DESC
        LIMIT ?;
        """
        with self.connection() as conn:
            rows = conn.execute(sql, (limit,)).fetchall()
            return [dict(r) for r in rows]

    # -------------------------------------------------------------------------
    # Daily Rollover Logging
    # -------------------------------------------------------------------------
    def log_rollover(
        self,
        date_str: str,
        raw_char_count: int,
        compact_char_count: int,
        tasks_carried: int,
        summary_preview: str,
    ) -> bool:
        """Record a successful daily compaction event."""
        now = int(time.time())
        sql = """
        INSERT INTO daily_rollover_log (
            date, compacted_at, raw_char_count, compact_char_count,
            tasks_carried_forward, summary_preview
        ) VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(date) DO UPDATE SET
            compacted_at = excluded.compacted_at,
            raw_char_count = excluded.raw_char_count,
            compact_char_count = excluded.compact_char_count,
            tasks_carried_forward = excluded.tasks_carried_forward,
            summary_preview = excluded.summary_preview;
        """
        with self.connection() as conn:
            conn.execute(
                sql,
                (
                    date_str,
                    now,
                    raw_char_count,
                    compact_char_count,
                    tasks_carried,
                    summary_preview,
                ),
            )
        return True
