"""Hybrid search: combine BM25 keyword scores with vector similarity."""
from retrieval.bm25 import BM25
from retrieval.store import VectorStore, cosine_similarity


def _normalize(scores: list[float]) -> list[float]:
    """Min-max normalize scores to the [0, 1] range.

    BM25 scores are unbounded, unlike cosine similarity (roughly -1 to 1),
    so we normalize before combining them into one weighted score.
    """
    if not scores:
        return []
    lo, hi = min(scores), max(scores)
    if hi == lo:
        return [0.0 for _ in scores]
    return [(s - lo) / (hi - lo) for s in scores]


def hybrid_search(query: str, query_vector: list[float], store: VectorStore,
                   top_k: int = 5, alpha: float = 0.5,
                   filters: dict | None = None) -> list[dict]:
    """Rank chunks by a weighted combination of vector and BM25 scores.

    hybrid_score = alpha * vector_score + (1 - alpha) * bm25_score

    alpha=1.0 is pure vector search, alpha=0.0 is pure BM25.
    filters: optional metadata filters, applied before scoring.
    """
    if not (0.0 <= alpha <= 1.0):
        raise ValueError("alpha must be between 0 and 1")

    chunks = store.get_all()

    if filters:
        chunks = [
            c for c in chunks
            if all(c["metadata"].get(k) == v for k, v in filters.items())
        ]

    if not chunks:
        return []

    contents = [c["content"] for c in chunks]
    bm25 = BM25(contents)
    bm25_scores = bm25.score_all(query)
    bm25_scores_normalized = _normalize(bm25_scores)

    vector_scores = [cosine_similarity(query_vector, c["vector"]) for c in chunks]
    # Cosine similarity for normalized embeddings is typically in [-1, 1];
    # normalize it too so both components are on the same [0, 1] scale.
    vector_scores_normalized = _normalize(vector_scores)

    results = []
    for chunk, v_score, b_score in zip(chunks, vector_scores_normalized, bm25_scores_normalized):
        hybrid_score = alpha * v_score + (1 - alpha) * b_score
        results.append({
            "id": chunk["id"],
            "source_file": chunk["source_file"],
            "start_line": chunk["start_line"],
            "end_line": chunk["end_line"],
            "content": chunk["content"],
            "metadata": chunk["metadata"],
            "score": hybrid_score,
            "vector_score": v_score,
            "bm25_score": b_score,
        })

    results.sort(key=lambda r: r["score"], reverse=True)
    return results[:top_k]