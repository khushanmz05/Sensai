"""SQLite-backed vector store with manual cosine similarity."""
import math
import sqlite3
import struct
import json


def _vector_to_blob(vector: list[float]) -> bytes:
    """Serialize a list of floats to bytes."""
    return struct.pack(f"{len(vector)}f", *vector)


def _blob_to_vector(blob: bytes) -> list[float]:
    """Deserialize bytes back into a list of floats."""
    n = len(blob) // 4
    return list(struct.unpack(f"{n}f", blob))


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two equal-length vectors."""
    if len(a) != len(b):
        raise ValueError("vectors must be the same length")

    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return dot / (norm_a * norm_b)


class VectorStore:
    """SQLite-backed store of text chunks and their embeddings."""

    def __init__(self, db_path: str = ":memory:"):
        self.conn = sqlite3.connect(db_path)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS chunks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_file TEXT NOT NULL,
                start_line INTEGER NOT NULL,
                end_line INTEGER NOT NULL,
                content TEXT NOT NULL,
                embedding BLOB NOT NULL,
                metadata TEXT NOT NULL DEFAULT '{}'
            )
        """)
        self.conn.commit()

    def add(self, source_file: str, start_line: int, end_line: int,
            content: str, embedding: list[float], metadata: dict | None = None) -> int:
        """Insert one chunk and its embedding. Returns the new row id."""
        metadata_json = json.dumps(metadata or {})
        cursor = self.conn.execute(
            "INSERT INTO chunks (source_file, start_line, end_line, content, embedding, metadata) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (source_file, start_line, end_line, content, _vector_to_blob(embedding), metadata_json),
        )
        self.conn.commit()
        return cursor.lastrowid

    def search(self, query_vector: list[float], top_k: int = 5,
            filters: dict | None = None) -> list[dict]:
        """Return the top_k most similar chunks, ranked by cosine similarity.

        filters: optional dict of metadata key-value pairs that must match
        exactly for a chunk to be included, e.g. {"version": "v2"}.
        """
        rows = self.conn.execute(
            "SELECT id, source_file, start_line, end_line, content, embedding, metadata FROM chunks"
        ).fetchall()

        scored = []
        for row_id, source_file, start_line, end_line, content, blob, metadata_json in rows:
            metadata = json.loads(metadata_json)

            if filters:
                if not all(metadata.get(key) == value for key, value in filters.items()):
                    continue

            vector = _blob_to_vector(blob)
            score = cosine_similarity(query_vector, vector)
            scored.append({
                "id": row_id,
                "source_file": source_file,
                "start_line": start_line,
                "end_line": end_line,
                "content": content,
                "metadata": metadata,
                "score": score,
            })

        scored.sort(key=lambda r: r["score"], reverse=True)
        return scored[:top_k]

    def close(self):
        self.conn.close()