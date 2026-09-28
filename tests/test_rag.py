"""Tests for retrieval/rag.py"""
import os
import shutil
import tempfile
import unittest
from unittest.mock import patch

from retrieval.rag import ingest, retrieve, format_context
from retrieval.store import VectorStore


def fake_embed(texts, model="nomic-embed-text"):
    """Deterministic fake embeddings based on text content, for testing."""
    vectors = []
    for text in texts:
        if "cat" in text.lower():
            vectors.append([1.0, 0.0, 0.0])
        elif "dog" in text.lower():
            vectors.append([0.0, 1.0, 0.0])
        else:
            vectors.append([0.0, 0.0, 1.0])
    return vectors


class RagTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.store = VectorStore(":memory:")

    def tearDown(self):
        self.store.close()
        shutil.rmtree(self.tmpdir)

    def _write_file(self, name, content):
        path = os.path.join(self.tmpdir, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return path

    @patch("retrieval.rag.embed", side_effect=fake_embed)
    def test_ingest_reads_txt_and_md_files(self, mock_embed):
        self._write_file("cats.md", "All about cats.\nThey are great.")
        self._write_file("dogs.txt", "All about dogs.\nThey are loyal.")
        self._write_file("ignore.json", '{"not": "text"}')

        count = ingest(self.tmpdir, self.store, chunk_size=10, chunk_overlap=2)

        self.assertEqual(count, 2)  # one chunk per file (short files)

    @patch("retrieval.rag.embed", side_effect=fake_embed)
    def test_retrieve_returns_most_relevant_chunk(self, mock_embed):
        self._write_file("cats.md", "All about cats.")
        self._write_file("dogs.txt", "All about dogs.")
        ingest(self.tmpdir, self.store, chunk_size=10, chunk_overlap=2)

        results = retrieve("tell me about cats", self.store, top_k=1)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["source_file"], "cats.md")

    @patch("retrieval.rag.embed", side_effect=fake_embed)
    def test_retrieve_empty_query_returns_empty(self, mock_embed):
        results = retrieve("   ", self.store)
        self.assertEqual(results, [])

    def test_ingest_raises_on_missing_directory(self):
        with self.assertRaises(ValueError):
            ingest("/no/such/path", self.store)

    def test_format_context_includes_source_and_lines(self):
        results = [{
            "source_file": "cats.md",
            "start_line": 1,
            "end_line": 2,
            "content": "All about cats.",
            "score": 0.9,
        }]
        text = format_context(results)
        self.assertIn("cats.md", text)
        self.assertIn("lines 1-2", text)
        self.assertIn("All about cats.", text)

    def test_format_context_empty_results_returns_empty_string(self):
        self.assertEqual(format_context([]), "")


if __name__ == '__main__':
    unittest.main()