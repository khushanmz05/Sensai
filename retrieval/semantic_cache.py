
"""SQLite-backed semantic cache for completed chat responses."""

import json
import math
import sqlite3
import time
from pathlib import Path

from retrieval.embeddings import embed


class SemanticCache:
    """Cache responses and retrieve them by embedding similarity."""

    def __init__(
        self,
        db_path="retrieval/semantic_cache.sqlite3",
        threshold=0.92,
        embedding_model="nomic-embed-text",
        base_url="http://localhost:11434",
    ):
        if not 0.0 <= threshold <= 1.0:
            raise ValueError("threshold must be between 0 and 1")

        self.db_path = str(db_path)
        self.threshold = threshold
        self.embedding_model = embedding_model
        self.base_url = base_url.rstrip("/")

        if self.db_path != ":memory:":
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS semantic_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cache_key TEXT NOT NULL,
                    query TEXT NOT NULL,
                    embedding TEXT NOT NULL,
                    response TEXT NOT NULL,
                    created_at REAL NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_semantic_cache_key
                ON semantic_cache(cache_key)
                """
            )

    def _connect(self):
        return sqlite3.connect(self.db_path, timeout=10)

    def _embed(self, text):
        vectors = embed(
            [text],
            model=self.embedding_model,
            base_url=self.base_url,
        )
        if not vectors or not vectors[0]:
            raise RuntimeError("Embedding model returned an empty vector")
        return vectors[0]

    @staticmethod
    def _cosine_similarity(left, right):
        if len(left) != len(right):
            return -1.0

        dot = sum(a * b for a, b in zip(left, right))
        left_norm = math.sqrt(sum(value * value for value in left))
        right_norm = math.sqrt(sum(value * value for value in right))

        if left_norm == 0 or right_norm == 0:
            return -1.0

        return dot / (left_norm * right_norm)

    def get(self, query, cache_key):
        """Return (response, similarity, query_embedding)."""
        if not isinstance(query, str) or not query.strip():
            return None, 0.0, None

        query_vector = self._embed(query)

        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT embedding, response
                FROM semantic_cache
                WHERE cache_key = ?
                """,
                (cache_key,),
            ).fetchall()

        best_response = None
        best_score = -1.0

        for stored_embedding, response in rows:
            try:
                vector = json.loads(stored_embedding)
                score = self._cosine_similarity(query_vector, vector)
            except (ValueError, TypeError):
                continue

            if score > best_score:
                best_score = score
                best_response = response

        if best_response is not None and best_score >= self.threshold:
            return best_response, best_score, query_vector

        return None, max(best_score, 0.0), query_vector

    def put(self, query, response, cache_key, embedding=None):
        """Store a response, reusing its query embedding when available."""
        if not isinstance(query, str) or not query.strip():
            return
        if not isinstance(response, str) or not response.strip():
            return

        vector = embedding if embedding is not None else self._embed(query)

        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO semantic_cache
                    (cache_key, query, embedding, response, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    cache_key,
                    query,
                    json.dumps(vector),
                    response,
                    time.time(),
                ),
            )

    def clear(self):
        """Remove all cached responses."""
        with self._connect() as connection:
            connection.execute("DELETE FROM semantic_cache")
