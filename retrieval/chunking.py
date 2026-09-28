"""Split text into overlapping line-based chunks for embedding."""


def chunk_text(text: str, chunk_size: int = 20, chunk_overlap: int = 5) -> list[dict]:
    """Split text into overlapping chunks, measured in lines.

    Args:
        text: the full document text.
        chunk_size: number of lines per chunk.
        chunk_overlap: number of lines shared between consecutive chunks.

    Returns:
        A list of dicts: {"content": str, "start_line": int, "end_line": int}.
        Line numbers are 1-based and inclusive.
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if chunk_overlap < 0:
        raise ValueError("chunk_overlap must not be negative")
    if chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be smaller than chunk_size")

    if not text.strip():
        return []

    lines = text.splitlines()
    step = chunk_size - chunk_overlap
    chunks = []

    start = 0
    while start < len(lines):
        end = min(start + chunk_size, len(lines))
        chunk_lines = lines[start:end]
        chunks.append({
            "content": "\n".join(chunk_lines),
            "start_line": start + 1,
            "end_line": end,
        })
        if end == len(lines):
            break
        start += step

    return chunks