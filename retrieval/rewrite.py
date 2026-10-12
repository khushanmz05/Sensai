"""Query rewriting via Ollama, to expand/rephrase queries before retrieval."""
from pathlib import Path

import requests

PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "query_rewrite.txt"


def _load_prompt_template() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def rewrite_query(query: str, model: str = "qwen3",
                   base_url: str = "http://localhost:11434",
                   timeout: float = 30) -> list[str]:
    """Ask Ollama to generate alternative phrasings of a query.

    Returns a list of rewritten queries. Falls back to [query] (the original,
    unmodified) if Ollama is unreachable or returns something unusable, since
    query rewriting is an enhancement, not a hard requirement for retrieval.
    """
    if not query.strip():
        return []

    template = _load_prompt_template()
    prompt = template.replace("{query}", query)

    try:
        response = requests.post(
            f"{base_url.rstrip('/')}/api/generate",
            json={"model": model, "prompt": prompt, "stream": False},
            timeout=timeout,
        )
    except (requests.ConnectionError, requests.Timeout):
        return [query]

    if response.status_code != 200:
        return [query]

    data = response.json()
    text = data.get("response", "").strip()
    if not text:
        return [query]

    rewrites = [line.strip() for line in text.splitlines() if line.strip()]
    if not rewrites:
        return [query]

    # Always include the original query alongside rewrites, so a bad
    # rewrite never fully replaces the user's actual question.
    if query not in rewrites:
        rewrites.insert(0, query)

    return rewrites