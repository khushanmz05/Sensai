"""Embeddings via Ollama's /api/embed endpoint."""
import requests


def embed(texts: list[str], model: str = "nomic-embed-text",
          base_url: str = "http://localhost:11434") -> list[list[float]]:
    """Get embeddings for a list of texts using Ollama.

    Args:
        texts: list of strings to embed.
        model: the Ollama embedding model to use.
        base_url: the Ollama server URL.

    Returns:
        A list of embedding vectors, one per input text, in the same order.

    Raises:
        RuntimeError: with an explicit message if Ollama is unreachable,
        the model is missing, or the request times out.
    """
    if not texts:
        return []

    try:
        response = requests.post(
            f"{base_url}/api/embed",
            json={"model": model, "input": texts},
            timeout=30,
        )
    except requests.ConnectionError:
        raise RuntimeError(
            f"Could not connect to Ollama at {base_url}. Is 'ollama serve' running?"
        )
    except requests.Timeout:
        raise RuntimeError("Embedding request to Ollama timed out.")

    if response.status_code == 404:
        raise RuntimeError(
            f"Model '{model}' not found. Try: ollama pull {model}"
        )
    if response.status_code != 200:
        raise RuntimeError(
            f"Ollama embedding request failed with status {response.status_code}: {response.text}"
        )

    data = response.json()
    embeddings = data.get("embeddings")
    if embeddings is None:
        raise RuntimeError(f"Unexpected Ollama response, no 'embeddings' field: {data}")

    return embeddings