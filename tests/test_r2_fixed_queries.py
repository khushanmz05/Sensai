"""Fixed query set verification for R2 (per plan section 4: 'verify these
on a fixed query set'). Uses deterministic fake embeddings and a fake
rewriter/reranker so this test is reproducible without live Ollama calls.
"""
import os
import unittest
from unittest.mock import patch

from retrieval.rag import ingest, retrieve_advanced
from retrieval.store import VectorStore

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures", "r2_corpus")


def fake_embed(texts, model=None):
    """Deterministic: 'cat'-related text points one way, 'dog'-related another."""
    vectors = []
    for text in texts:
        lowered = text.lower()
        if "cat" in lowered or "meow" in lowered or "purr" in lowered:
            vectors.append([1.0, 0.0])
        elif "dog" in lowered or "bark" in lowered or "wolves" in lowered:
            vectors.append([0.0, 1.0])
        else:
            vectors.append([0.5, 0.5])
    return vectors


def fake_rewrite(query, **kwargs):
    """No-op rewriter: just returns the original query."""
    return [query]


def fake_rerank(query, results, **kwargs):
    """No-op reranker: passes results through unchanged."""
    return results


# The fixed query set: (query, expected_top_source, forbidden_source)
FIXED_QUERIES = [
    ("how do cats sleep", "cats.md", "dogs.md"),
    ("how do dogs communicate with people", "dogs.md", "cats.md"),
    ("what animal do dogs descend from", "dogs.md", "cats.md"),
    ("what animal do cats descend from", "cats.md", "dogs.md"),
]


@patch("retrieval.rag.rerank", side_effect=fake_rerank)
@patch("retrieval.rag.rewrite_query", side_effect=fake_rewrite)
@patch("retrieval.rag.embed", side_effect=fake_embed)
class FixedQuerySetTests(unittest.TestCase):
    """Verifies R2 retrieval against a small, known, reproducible query set."""

    def setUp(self):
        self.store = VectorStore(":memory:")

    def tearDown(self):
        self.store.close()

    def test_ingestion_reads_the_fixture_corpus(self, mock_embed, mock_rewrite, mock_rerank):
        count = ingest(FIXTURES_DIR, self.store, chunk_size=10, chunk_overlap=2)
        self.assertGreater(count, 0)

    def test_each_query_retrieves_its_expected_document_first(
            self, mock_embed, mock_rewrite, mock_rerank):
        ingest(FIXTURES_DIR, self.store, chunk_size=10, chunk_overlap=2)

        for query, expected_source, _ in FIXED_QUERIES:
            with self.subTest(query=query):
                results = retrieve_advanced(query, self.store, top_k=3,
                                             use_rewriting=True, use_reranking=True)
                self.assertGreater(len(results), 0, f"No results for: {query}")
                self.assertEqual(
                    results[0]["source_file"], expected_source,
                    f"Query {query!r} expected {expected_source} first, "
                    f"got {results[0]['source_file']}"
                )

    def test_queries_do_not_surface_the_wrong_document_as_top_result(
            self, mock_embed, mock_rewrite, mock_rerank):
        ingest(FIXTURES_DIR, self.store, chunk_size=10, chunk_overlap=2)

        for query, _, forbidden_source in FIXED_QUERIES:
            with self.subTest(query=query):
                results = retrieve_advanced(query, self.store, top_k=1,
                                             use_rewriting=True, use_reranking=True)
                self.assertNotEqual(
                    results[0]["source_file"], forbidden_source,
                    f"Query {query!r} should not rank {forbidden_source} first"
                )


if __name__ == '__main__':
    unittest.main()