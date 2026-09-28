"""Unit tests for retrieval/chunking.py"""
import unittest

from retrieval.chunking import chunk_text


class ChunkingTests(unittest.TestCase):
    def test_empty_text_returns_no_chunks(self):
        self.assertEqual(chunk_text(""), [])
        self.assertEqual(chunk_text("   \n  "), [])

    def test_short_text_returns_one_chunk(self):
        text = "line1\nline2\nline3"
        chunks = chunk_text(text, chunk_size=10, chunk_overlap=2)
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0]["start_line"], 1)
        self.assertEqual(chunks[0]["end_line"], 3)

    def test_overlap_between_consecutive_chunks(self):
        lines = [f"line{i}" for i in range(1, 11)]
        text = "\n".join(lines)
        chunks = chunk_text(text, chunk_size=4, chunk_overlap=1)
        last_of_first = chunks[0]["content"].splitlines()[-1]
        first_of_second = chunks[1]["content"].splitlines()[0]
        self.assertEqual(last_of_first, first_of_second)

    def test_line_numbers_are_correct(self):
        lines = [f"line{i}" for i in range(1, 11)]
        text = "\n".join(lines)
        chunks = chunk_text(text, chunk_size=4, chunk_overlap=1)
        self.assertEqual(chunks[0]["start_line"], 1)
        self.assertEqual(chunks[0]["end_line"], 4)
        self.assertEqual(chunks[1]["start_line"], 4)

    def test_invalid_chunk_size_raises(self):
        with self.assertRaises(ValueError):
            chunk_text("a\nb", chunk_size=0)

    def test_invalid_overlap_raises(self):
        with self.assertRaises(ValueError):
            chunk_text("a\nb\nc", chunk_size=2, chunk_overlap=2)

    def test_negative_overlap_raises(self):
        with self.assertRaises(ValueError):
            chunk_text("a\nb", chunk_size=2, chunk_overlap=-1)


if __name__ == '__main__':
    unittest.main()