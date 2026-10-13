"""Unit tests for retrieval/bm25.py"""
import unittest

from retrieval.bm25 import BM25, _tokenize


class TokenizeTests(unittest.TestCase):
    def test_lowercases_and_splits(self):
        self.assertEqual(_tokenize("Hello, World!"), ["hello", "world"])

    def test_empty_string_returns_empty_list(self):
        self.assertEqual(_tokenize(""), [])


class BM25Tests(unittest.TestCase):
    def setUp(self):
        self.docs = [
            "the cat sat on the mat",
            "the dog played in the park",
            "cats and dogs are common pets",
        ]
        self.bm25 = BM25(self.docs)

    def test_document_matching_query_scores_higher(self):
        scores = self.bm25.score_all("cat")
        self.assertGreater(scores[0], scores[1])  # doc 0 mentions "cat"

    def test_no_matching_terms_scores_zero(self):
        scores = self.bm25.score_all("elephant")
        self.assertEqual(scores, [0.0, 0.0, 0.0])

    def test_empty_corpus_does_not_crash(self):
        bm25 = BM25([])
        self.assertEqual(bm25.score_all("anything"), [])

    def test_multi_term_query_combines_scores(self):
        scores = self.bm25.score_all("cats dogs")
        self.assertGreater(scores[2], scores[0])  # doc 2 mentions both


if __name__ == '__main__':
    unittest.main()