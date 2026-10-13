"""Tests for retrieval/hybrid.py"""
import unittest

from retrieval.hybrid import hybrid_search, _normalize
from retrieval.store import VectorStore


class NormalizeTests(unittest.TestCase):
    def test_normalizes_to_zero_one_range(self):
        result = _normalize([0, 5, 10])
        self.assertEqual(result, [0.0, 0.5, 1.0])

    def test_empty_list_returns_empty(self):
        self.assertEqual(_normalize([]), [])

    def test_all_equal_scores_returns_zeros(self):
        self.assertEqual(_normalize([3, 3, 3]), [0.0, 0.0, 0.0])


class HybridSearchTests(unittest.TestCase):
    def setUp(self):
        self.store = VectorStore(":memory:")
        # "cats" doc: strong keyword match AND strong vector match for a cat query
        self.store.add("cats.md", 1, 1, "all about cats and kittens", [1.0, 0.0])
        # "dogs" doc: no keyword match, weak vector match
        self.store.add("dogs.md", 1, 1, "all about dogs and puppies", [0.0, 1.0])
        # "mixed" doc: keyword match but weak vector match
        self.store.add("mixed.md", 1, 1, "cats mentioned once here", [0.1, 0.9])

    def tearDown(self):
        self.store.close()

    def test_pure_vector_search_alpha_one(self):
        results = hybrid_search("cats", [1.0, 0.0], self.store, top_k=3, alpha=1.0)
        self.assertEqual(results[0]["source_file"], "cats.md")

    def test_pure_bm25_search_alpha_zero(self):
        results = hybrid_search("cats", [0.0, 1.0], self.store, top_k=3, alpha=0.0)
        # even though vector points away from cats.md, BM25 should still favor
        # the doc(s) that actually contain "cats" as keyword matches
        top_sources = {results[0]["source_file"], results[1]["source_file"]}
        self.assertIn("cats.md", top_sources)

    def test_invalid_alpha_raises(self):
        with self.assertRaises(ValueError):
            hybrid_search("cats", [1.0, 0.0], self.store, alpha=1.5)

    def test_empty_store_returns_empty(self):
        empty_store = VectorStore(":memory:")
        results = hybrid_search("anything", [1.0, 0.0], empty_store)
        self.assertEqual(results, [])
        empty_store.close()

    def test_filters_apply_before_scoring(self):
        self.store.add("versioned.md", 1, 1, "cats content", [1.0, 0.0], metadata={"version": "v2"})
        results = hybrid_search("cats", [1.0, 0.0], self.store, top_k=5,
                                 filters={"version": "v2"})
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["source_file"], "versioned.md")

    def test_results_include_score_breakdown(self):
        results = hybrid_search("cats", [1.0, 0.0], self.store, top_k=1)
        self.assertIn("score", results[0])
        self.assertIn("vector_score", results[0])
        self.assertIn("bm25_score", results[0])


if __name__ == '__main__':
    unittest.main()