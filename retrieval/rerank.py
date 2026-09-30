"""Reranking via Ollama: re-score top-N results and reject irrelevant ones."""
import re
from pathlib import Path

import requests

PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "rerank.txt"


def _load_prompt_template() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def _score_relevance(query: str, passage: str, model: str,
                      base_url: str, timeout: float) -> float | None:
    """Ask Ollama to score one passage's relevance to a query, 0-10.

    Returns None if the model is unreachable or its response can't be
    parsed as a number, so the caller can decide how to handle that
    (e.g. keep the passage's existing score rather than reject it blindly).
    """
    template = _load_prompt_template()
    prompt = template.replace("{query}", query).replace("{passage}", passage)

    try:
        response = requests.post(
            f"{base_url.rstrip('/')}/api/generate",
            json={"model": model, "prompt": prompt, "stream": False},
            timeout=timeout,
        )
    except (requests.ConnectionError, requests.Timeout):
        return None

    if response.status_code != 200:
        return None

    text = response.json().get("response", "").strip()
    match = re.search(r"\d+(\.\d+)?", text)
    if not match:
        return None

    score = float(match.group())
    return max(0.0, min(10.0, score))  # clamp to [0, 10]


def rerank(query: str, results: list[dict], model: str = "qwen3",
           base_url: str = "http://localhost:11434", timeout: float = 30,
           top_n: int = 10, rejection_threshold: float = 3.0) -> list[dict]:
    """Re-score the top_n results using an LLM judge, then drop low-relevance ones.

    - Only the top_n candidates (by their existing score) are re-scored, to
      limit the number of Ollama calls.
    - Results scoring below rejection_threshold (0-10 scale) are excluded
      from the returned list entirely, not just reordered.
    - If the LLM judge is unreachable for a given passage, that passage
      keeps its original position and is not rejected, since a missing
      judgment shouldn't be treated as "irrelevant."
    """
    if not results:
        return []

    candidates = results[:top_n]
    reranked = []

    for item in candidates:
        relevance = _score_relevance(query, item["content"], model, base_url, timeout)
        new_item = dict(item)
        if relevance is None:
            # Judge unavailable: keep the item, unscored by rerank.
            new_item["rerank_score"] = None
            reranked.append(new_item)
        else:
            new_item["rerank_score"] = relevance
            if relevance >= rejection_threshold:
                reranked.append(new_item)
            # else: dropped, relevance too low

    # Sort by rerank_score where available (None sorts last, keeping original order for those)
    reranked.sort(key=lambda r: (r["rerank_score"] is None, -(r["rerank_score"] or 0)))

    return reranked