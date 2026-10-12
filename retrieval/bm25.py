"""Manual BM25 keyword search, no external dependencies."""
import math
import re
from collections import Counter


def _tokenize(text: str) -> list[str]:
    """Lowercase and split on non-alphanumeric characters."""
    return re.findall(r"[a-z0-9]+", text.lower())


class BM25:
    """BM25 ranking over a fixed collection of documents.

    Standard parameters: k1 controls term-frequency saturation,
    b controls length normalization.
    """

    def __init__(self, documents: list[str], k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.doc_tokens = [_tokenize(doc) for doc in documents]
        self.doc_lengths = [len(tokens) for tokens in self.doc_tokens]
        self.avg_doc_length = (
            sum(self.doc_lengths) / len(self.doc_lengths) if self.doc_lengths else 0
        )
        self.doc_freqs = [Counter(tokens) for tokens in self.doc_tokens]
        self.n_docs = len(documents)
        self.idf = self._compute_idf()

    def _compute_idf(self) -> dict[str, float]:
        """Standard BM25 IDF: log((N - df + 0.5) / (df + 0.5) + 1)."""
        df = Counter()
        for tokens in self.doc_tokens:
            for term in set(tokens):
                df[term] += 1

        idf = {}
        for term, freq in df.items():
            idf[term] = math.log((self.n_docs - freq + 0.5) / (freq + 0.5) + 1)
        return idf

    def score(self, query: str, doc_index: int) -> float:
        """BM25 score of one document against a query."""
        query_terms = _tokenize(query)
        freqs = self.doc_freqs[doc_index]
        doc_len = self.doc_lengths[doc_index]

        score = 0.0
        for term in query_terms:
            if term not in freqs:
                continue
            idf = self.idf.get(term, 0.0)
            tf = freqs[term]
            numerator = tf * (self.k1 + 1)
            denominator = tf + self.k1 * (
                1 - self.b + self.b * (doc_len / self.avg_doc_length)
            ) if self.avg_doc_length > 0 else tf
            score += idf * (numerator / denominator)

        return score

    def score_all(self, query: str) -> list[float]:
        """BM25 scores for every document, in original order."""
        return [self.score(query, i) for i in range(self.n_docs)]