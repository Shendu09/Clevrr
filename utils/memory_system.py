"""
MemorySystem — Local Episodic, Semantic & Procedural Memory

Three-tier memory backed by a local SQLite database.
Semantic search powered by sentence-transformers (runs locally).
ZERO cloud dependencies.
"""

import json
import logging
import sqlite3
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


class MemorySystem:
    """Three-tier memory system: episodic, semantic, and procedural.

    - **Episodic**: Records of past tasks (what happened).
    - **Semantic**: Learned facts and knowledge.
    - **Procedural**: Reusable step-by-step procedures.

    All data stored in a local SQLite database.
    Similarity search uses a local sentence-transformers model.
    """

    def __init__(self, config: dict) -> None:
        """Initialize the memory system.

        Args:
            config: Dictionary containing memory settings from settings.yaml.
        """
        mem_config = config.get("memory", {})
        self.db_path: str = mem_config.get("db_path", "data/memory.db")
        self.max_episodes: int = mem_config.get("max_episodes", 1000)
        self.similarity_threshold: float = mem_config.get(
            "similarity_threshold", 0.75
        )
        self.cleanup_days: int = mem_config.get("cleanup_days", 30)

        # Create data directory
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        # Initialize database
        self.initialize_db()

        # Lazy-load sentence-transformers model for semantic search on first use
        # (avoids torch import issues during startup)
        self._embedder = None
        self._embedder_loaded = False

    # ------------------------------------------------------------------
    # Database Setup
    # ------------------------------------------------------------------

    def initialize_db(self) -> None:
        """Create the three memory tables if they do not exist."""
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS episodes (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_text   TEXT NOT NULL,
                    steps_json  TEXT,
                    outcome_text TEXT,
                    success     INTEGER DEFAULT 0,
                    duration_seconds REAL DEFAULT 0.0,
                    embedding   BLOB,
                    timestamp   TEXT DEFAULT (datetime('now'))
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS knowledge (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    fact_text   TEXT NOT NULL,
                    context     TEXT,
                    confidence  REAL DEFAULT 1.0,
                    source      TEXT,
                    embedding   BLOB,
                    timestamp   TEXT DEFAULT (datetime('now'))
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS procedures (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    goal_text    TEXT NOT NULL,
                    steps_json   TEXT,
                    success_rate REAL DEFAULT 0.0,
                    use_count    INTEGER DEFAULT 0,
                    last_used    TEXT,
                    embedding    BLOB,
                    timestamp    TEXT DEFAULT (datetime('now'))
                )
                """
            )
            conn.commit()
        logger.info("Memory database initialized at %s", self.db_path)

    # ------------------------------------------------------------------
    # Episodic Memory
    # ------------------------------------------------------------------

    def save_episode(
        self,
        task: str,
        steps: list,
        outcome: str,
        success: bool,
        duration: float,
    ) -> int:
        """Save a completed task episode.

        Args:
            task: Description of the task.
            steps: List of step dictionaries.
            outcome: Final outcome description.
            success: Whether the task succeeded.
            duration: Duration in seconds.

        Returns:
            Row ID of the saved episode.
        """
        embedding = self._encode(task)
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO episodes
                    (task_text, steps_json, outcome_text, success,
                     duration_seconds, embedding)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    task,
                    json.dumps(steps),
                    outcome,
                    1 if success else 0,
                    duration,
                    self._blob(embedding),
                ),
            )
            conn.commit()
            self._enforce_episode_limit(conn)
            logger.info("Saved episode #%d: %s", cur.lastrowid, task[:80])
            return cur.lastrowid

    def get_recent_episodes(self, limit: int = 10) -> List[dict]:
        """Return the most recent episodes.

        Args:
            limit: Maximum number of episodes to return.

        Returns:
            List of episode dictionaries, most recent first.
        """
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, task_text, steps_json, outcome_text,
                       success, duration_seconds, timestamp
                FROM episodes ORDER BY id DESC LIMIT ?
                """,
                (limit,),
            ).fetchall()

        return [self._row_to_episode(r) for r in rows]

    def find_similar_episodes(
        self, task_text: str, limit: int = 3
    ) -> List[dict]:
        """Find past episodes similar to the given task.

        Uses sentence-transformers for semantic similarity.

        Args:
            task_text: Description of the current task.
            limit: Maximum number of results.

        Returns:
            List of similar episodes sorted by similarity (descending).
        """
        query_emb = self._encode(task_text)
        if query_emb is None:
            return self._keyword_search("episodes", "task_text", task_text, limit)

        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, task_text, steps_json, outcome_text,
                       success, duration_seconds, embedding, timestamp
                FROM episodes WHERE embedding IS NOT NULL
                """
            ).fetchall()

        scored: List[Tuple[float, dict]] = []
        for r in rows:
            emb = self._from_blob(r[6])
            if emb is not None:
                sim = self._cosine_similarity(query_emb, emb)
                if sim >= self.similarity_threshold:
                    ep = self._row_to_episode(r[:6] + (r[7],))
                    ep["similarity"] = round(sim, 3)
                    scored.append((sim, ep))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [ep for _, ep in scored[:limit]]

    # ------------------------------------------------------------------
    # Semantic Memory (Knowledge)
    # ------------------------------------------------------------------

    def save_knowledge(
        self,
        fact: str,
        context: str,
        confidence: float = 1.0,
        source: str = "agent",
    ) -> int:
        """Save a learned fact.

        Args:
            fact: The fact text.
            context: Context in which the fact was learned.
            confidence: Confidence score (0.0–1.0).
            source: Source of the knowledge.

        Returns:
            Row ID.
        """
        embedding = self._encode(fact)
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO knowledge
                    (fact_text, context, confidence, source, embedding)
                VALUES (?, ?, ?, ?, ?)
                """,
                (fact, context, confidence, source, self._blob(embedding)),
            )
            conn.commit()
            logger.info("Saved knowledge #%d: %s", cur.lastrowid, fact[:80])
            return cur.lastrowid

    def search_knowledge(self, query: str, limit: int = 5) -> List[dict]:
        """Search knowledge base semantically.

        Args:
            query: Search query.
            limit: Maximum results.

        Returns:
            List of matching knowledge facts.
        """
        query_emb = self._encode(query)
        if query_emb is None:
            return self._keyword_search("knowledge", "fact_text", query, limit)

        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, fact_text, context, confidence,
                       source, embedding, timestamp
                FROM knowledge WHERE embedding IS NOT NULL
                """
            ).fetchall()

        scored: List[Tuple[float, dict]] = []
        for r in rows:
            emb = self._from_blob(r[5])
            if emb is not None:
                sim = self._cosine_similarity(query_emb, emb)
                if sim >= self.similarity_threshold:
                    item = {
                        "id": r[0],
                        "fact": r[1],
                        "context": r[2],
                        "confidence": r[3],
                        "source": r[4],
                        "timestamp": r[6],
                        "similarity": round(sim, 3),
                    }
                    scored.append((sim, item))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [item for _, item in scored[:limit]]

    # ------------------------------------------------------------------
    # Procedural Memory
    # ------------------------------------------------------------------

    def save_procedure(self, goal: str, steps: list) -> int:
        """Save a working procedure for a goal.

        Args:
            goal: Description of the goal.
            steps: List of step dictionaries.

        Returns:
            Row ID.
        """
        embedding = self._encode(goal)
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO procedures
                    (goal_text, steps_json, success_rate,
                     use_count, last_used, embedding)
                VALUES (?, ?, 1.0, 1, datetime('now'), ?)
                """,
                (goal, json.dumps(steps), self._blob(embedding)),
            )
            conn.commit()
            logger.info("Saved procedure #%d: %s", cur.lastrowid, goal[:80])
            return cur.lastrowid

    def find_procedure(self, goal: str) -> Optional[dict]:
        """Find an existing procedure for a similar goal.

        Args:
            goal: Description of the goal.

        Returns:
            Procedure dictionary or None if nothing similar enough.
        """
        goal_emb = self._encode(goal)
        if goal_emb is None:
            results = self._keyword_search(
                "procedures", "goal_text", goal, 1
            )
            return results[0] if results else None

        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, goal_text, steps_json, success_rate,
                       use_count, last_used, embedding, timestamp
                FROM procedures WHERE embedding IS NOT NULL
                """
            ).fetchall()

        best: Optional[Tuple[float, dict]] = None
        for r in rows:
            emb = self._from_blob(r[6])
            if emb is not None:
                sim = self._cosine_similarity(goal_emb, emb)
                if sim >= self.similarity_threshold:
                    proc = {
                        "id": r[0],
                        "goal": r[1],
                        "steps": json.loads(r[2]) if r[2] else [],
                        "success_rate": r[3],
                        "use_count": r[4],
                        "last_used": r[5],
                        "timestamp": r[7],
                        "similarity": round(sim, 3),
                    }
                    if best is None or sim > best[0]:
                        best = (sim, proc)

        return best[1] if best else None

    def update_procedure_success(
        self, procedure_id: int, success: bool
    ) -> None:
        """Update the success rate and usage count of a procedure.

        Args:
            procedure_id: ID of the procedure to update.
            success: Whether the latest usage succeeded.
        """
        with self._connect() as conn:
            row = conn.execute(
                "SELECT success_rate, use_count FROM procedures WHERE id = ?",
                (procedure_id,),
            ).fetchone()
            if row is None:
                return

            old_rate, old_count = row
            new_count = old_count + 1
            # Running average
            new_rate = (
                (old_rate * old_count) + (1.0 if success else 0.0)
            ) / new_count

            conn.execute(
                """
                UPDATE procedures
                SET success_rate = ?, use_count = ?, last_used = datetime('now')
                WHERE id = ?
                """,
                (round(new_rate, 4), new_count, procedure_id),
            )
            conn.commit()
            logger.info(
                "Updated procedure #%d: rate=%.2f, uses=%d",
                procedure_id,
                new_rate,
                new_count,
            )

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        """Return aggregate memory statistics.

        Returns:
            Dictionary with counts, success rate, and common tasks.
        """
        with self._connect() as conn:
            total_eps = conn.execute(
                "SELECT COUNT(*) FROM episodes"
            ).fetchone()[0]

            success_count = conn.execute(
                "SELECT COUNT(*) FROM episodes WHERE success = 1"
            ).fetchone()[0]

            total_knowledge = conn.execute(
                "SELECT COUNT(*) FROM knowledge"
            ).fetchone()[0]

            total_procedures = conn.execute(
                "SELECT COUNT(*) FROM procedures"
            ).fetchone()[0]

            common_tasks = conn.execute(
                """
                SELECT task_text, COUNT(*) as cnt
                FROM episodes
                GROUP BY task_text
                ORDER BY cnt DESC
                LIMIT 5
                """
            ).fetchall()

        success_rate = (
            round(success_count / total_eps * 100, 1) if total_eps > 0 else 0.0
        )

        return {
            "total_episodes": total_eps,
            "success_rate": success_rate,
            "total_knowledge": total_knowledge,
            "total_procedures": total_procedures,
            "most_common_tasks": [
                {"task": t[0], "count": t[1]} for t in common_tasks
            ],
        }

    def clear_old_episodes(self, days: int = 7) -> int:
        """Delete episodes older than the given number of days.

        Args:
            days: Age threshold in days.

        Returns:
            Number of deleted episodes.
        """
        with self._connect() as conn:
            before = conn.execute("SELECT COUNT(*) FROM episodes").fetchone()[0]
            conn.execute(
                """
                DELETE FROM episodes
                WHERE datetime(timestamp) < datetime('now', ?)
                """,
                (f"-{int(days)} days",),
            )
            conn.commit()
            after = conn.execute("SELECT COUNT(*) FROM episodes").fetchone()[0]

        removed = max(0, before - after)
        logger.info("Removed %d old episodes (>%d days).", removed, days)
        return removed

    # ------------------------------------------------------------------
    # Private Helpers
    # ------------------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        """Open a connection to the SQLite database."""
        return sqlite3.connect(self.db_path)

    def _encode(self, text: str) -> Optional[np.ndarray]:
        """Encode text to an embedding vector.

        Args:
            text: Text to encode.

        Returns:
            Numpy array embedding or None if embedder unavailable.
        """
        if not text:
            return None
        
        # Lazy-load embedder on first use
        if not self._embedder_loaded:
            self._embedder_loaded = True
            try:
                from sentence_transformers import SentenceTransformer
                self._embedder = SentenceTransformer("all-MiniLM-L6-v2")
                logger.info("Sentence-transformers model loaded (local).")
            except Exception as exc:
                logger.warning(
                    "Sentence-transformers not available: %s. "
                    "Semantic search will fall back to keyword matching.",
                    exc,
                )
                self._embedder = None
        
        if self._embedder is None:
            return None
        
        try:
            return self._embedder.encode(text, convert_to_numpy=True)
        except Exception as exc:
            logger.warning("Embedding failed: %s", exc)
            return None

    @staticmethod
    def _blob(arr: Optional[np.ndarray]) -> Optional[bytes]:
        """Convert numpy array to bytes for SQLite storage."""
        if arr is None:
            return None
        return arr.astype(np.float32).tobytes()

    @staticmethod
    def _from_blob(blob: Optional[bytes]) -> Optional[np.ndarray]:
        """Reconstruct numpy array from SQLite blob."""
        if blob is None:
            return None
        try:
            return np.frombuffer(blob, dtype=np.float32)
        except Exception:
            return None

    @staticmethod
    def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
        """Compute cosine similarity between two vectors."""
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(np.dot(a, b) / (norm_a * norm_b))

    def _keyword_search(
        self, table: str, column: str, query: str, limit: int
    ) -> List[dict]:
        """Fallback keyword search when embedder is unavailable."""
        words = query.lower().split()
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM {table} ORDER BY id DESC LIMIT 100"
            ).fetchall()

        results = []
        for row in rows:
            text_val = str(row[1]).lower()  # column index 1 is the text field
            if any(w in text_val for w in words):
                results.append(row)
            if len(results) >= limit:
                break

        return [{"id": r[0], "text": r[1]} for r in results]

    @staticmethod
    def _row_to_episode(row: tuple) -> dict:
        """Convert a database row to an episode dictionary."""
        return {
            "id": row[0],
            "task": row[1],
            "steps": json.loads(row[2]) if row[2] else [],
            "outcome": row[3],
            "success": bool(row[4]),
            "duration": row[5],
            "timestamp": row[6] if len(row) > 6 else None,
        }

    def _enforce_episode_limit(self, conn: sqlite3.Connection) -> None:
        """Delete oldest episodes if over the maximum limit."""
        count = conn.execute("SELECT COUNT(*) FROM episodes").fetchone()[0]
        if count > self.max_episodes:
            excess = count - self.max_episodes
            conn.execute(
                """
                DELETE FROM episodes WHERE id IN (
                    SELECT id FROM episodes ORDER BY id ASC LIMIT ?
                )
                """,
                (excess,),
            )
            conn.commit()
            logger.info("Cleaned up %d old episodes.", excess)
