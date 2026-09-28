"""Unit tests for retrieval/store.py"""
import unittest

from retrieval.store import VectorStore, cosine_similarity


class CosineSimilarityTests(unittest.TestCase):
    def test_identical_vectors_score_one(self):
        self.assertAlmostEqual(cosine_similarity([1, 2, 3], [1, 2, 3]), 1.0)

    def test_orthogonal_vectors_score_zero(self):
        self.assertAlmostEqual(cosine_similarity([1, 0], [0, 1]), 0.0)

    def test_opposite_vectors_score_negative_one(self):
        self.assertAlmostEqual(cosine_similarity([1, 0], [-1, 0]), -1.0)

    def test_zero_vector_returns_zero(self):
        self.assertEqual(cosine_similarity([0, 0], [1, 2]), 0.0)

    def test_mismatched_lengths_raise(self):
        with self.assertRaises(ValueError):
            cosine_similarity([1, 2], [1, 2, 3])


class VectorStoreTests(unittest.TestCase):
    def setUp(self):
        self.store = VectorStore(":memory:")

    def tearDown(self):
        self.store.close()

    def test_add_and_search_returns_closest_first(self):
        self.store.add("a.md", 1, 5, "about cats", [1, 0, 0])
        self.store.add("b.md", 1, 5, "about dogs", [0, 1, 0])
        self.store.add("c.md", 1, 5, "about cats too", [0.9, 0.1, 0])

        results = self.store.search([1, 0, 0], top_k=2)

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["source_file"], "a.md")
        self.assertEqual(results[1]["source_file"], "c.md")

    def test_search_respects_top_k(self):
        for i in range(5):
            self.store.add(f"f{i}.md", 1, 1, f"chunk {i}", [1, 0, 0])
        results = self.store.search([1, 0, 0], top_k=3)
        self.assertEqual(len(results), 3)

    def test_search_on_empty_store_returns_empty(self):
        self.assertEqual(self.store.search([1, 0, 0]), [])

    def test_round_trip_preserves_embedding_values(self):
        original = [0.1, 0.2, 0.3, -0.5]
        self.store.add("x.md", 1, 1, "content", original)
        results = self.store.search(original, top_k=1)
        self.assertAlmostEqual(results[0]["score"], 1.0, places=5)


if __name__ == '__main__':
    unittest.main()