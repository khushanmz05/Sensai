"""Ties together ingestion, embedding, storage, and retrieval."""
import os

from retrieval.chunking import chunk_text
from retrieval.embeddings import embed
from retrieval.store import VectorStore


DEFAULT_MODEL = "nomic-embed-text"
SUPPORTED_EXTENSIONS = (".txt", ".md")


def ingest(directory: str, store: VectorStore, model: str = DEFAULT_MODEL,
           chunk_size: int = 20, chunk_overlap: int = 5) -> int:
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