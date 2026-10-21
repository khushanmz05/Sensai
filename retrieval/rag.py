"""Ties together ingestion, embedding, storage, and retrieval."""
import os

from retrieval.chunking import chunk_text
from retrieval.embeddings import embed
from retrieval.store import VectorStore
from retrieval.rewrite import rewrite_query
from retrieval.hybrid import hybrid_search
from retrieval.rerank import rerank

DEFAULT_MODEL = "nomic-embed-text"
SUPPORTED_EXTENSIONS = (".txt", ".md")

def retrieve_advanced(query: str, store: VectorStore, top_k: int = 5,
                       model: str = DEFAULT_MODEL,
                       rewrite_model: str = "qwen3",
                       rerank_model: str = "qwen3",
                       base_url: str = "http://localhost:11434",
                       alpha: float = 0.5,
                       rerank_top_n: int = 10,
                       rejection_threshold: float = 3.0,
                       filters: dict | None = None,
                       use_rewriting: bool = True,
                       use_reranking: bool = True) -> list[dict]:
    """R2 advanced retrieval: query rewriting + hybrid search + reranking.

    Falls back gracefully: rewriting and reranking failures never crash
    retrieval, they just reduce to plain hybrid search results.
    """
    if not query.strip():
        return []

    queries = [query]
    if use_rewriting:
        queries = rewrite_query(query, model=rewrite_model, base_url=base_url)
        if not queries:
            queries = [query]

    # Run hybrid search for each query variant, then merge results by id,
    # keeping the highest score seen for any chunk across all variants.
    merged: dict[int, dict] = {}
    for q in queries:
        query_vector = embed([q], model=model)[0]
        results = hybrid_search(q, query_vector, store, top_k=rerank_top_n,
                                 alpha=alpha, filters=filters)
        for r in results:
            existing = merged.get(r["id"])
            if existing is None or r["score"] > existing["score"]:
                merged[r["id"]] = r

    combined = sorted(merged.values(), key=lambda r: r["score"], reverse=True)

    if use_reranking and combined:
        combined = rerank(query, combined, model=rerank_model, base_url=base_url,
                           top_n=rerank_top_n, rejection_threshold=rejection_threshold)

    return combined[:top_k]


def ingest(directory: str, store: VectorStore, model: str = DEFAULT_MODEL,
           chunk_size: int = 20, chunk_overlap: int = 5, guardrails=None) -> int:
    """Read supported files from a directory, chunk them, embed them, and store them.

    Returns the number of chunks ingested.
    """
    if not os.path.isdir(directory):
        raise ValueError(f"Not a directory: {directory}")

    total_chunks = 0

    for filename in sorted(os.listdir(directory)):
        if not filename.endswith(SUPPORTED_EXTENSIONS):
            continue

        path = os.path.join(directory, filename)
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()

        if guardrails is not None:
            text = guardrails.check_input(text)
            filename = guardrails.check_input(filename)

        chunks = chunk_text(text, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        if not chunks:
            continue

        contents = [c["content"] for c in chunks]
        vectors = embed(contents, model=model)

        for chunk, vector in zip(chunks, vectors):
            store.add(
                source_file=filename,
                start_line=chunk["start_line"],
                end_line=chunk["end_line"],
                content=chunk["content"],
                embedding=vector,
            )
            total_chunks += 1

    return total_chunks


def retrieve(query: str, store: VectorStore, top_k: int = 5,
             model: str = DEFAULT_MODEL) -> list[dict]:
    """Embed a query and return the top_k most relevant chunks."""
    if not query.strip():
        return []

    query_vector = embed([query], model=model)[0]
    return store.search(query_vector, top_k=top_k)


def format_context(results: list[dict]) -> str:
    """Format retrieved chunks into a text block for the system prompt."""
    if not results:
        return ""

    parts = ["Relevant context from project documents:\n"]
    for r in results:
        parts.append(
            f"[Source: {r['source_file']}, lines {r['start_line']}-{r['end_line']}]\n"
            f"{r['content']}\n"
        )
    return "\n".join(parts)
