"""Tests for retrieval/rerank.py using a fake local Ollama server."""
import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from retrieval.rerank import rerank


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        data = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        self.server.payloads.append(data)
        status, body = self.server.replies.pop(0)
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(body).encode())


class RerankTests(unittest.TestCase):
    def setUp(self):
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.server.payloads = []
        self.server.replies = []
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f'http://127.0.0.1:{self.server.server_port}'

        self.results = [
            {"source_file": "a.md", "content": "very relevant passage", "score": 0.9},
            {"source_file": "b.md", "content": "irrelevant passage", "score": 0.85},
            {"source_file": "c.md", "content": "somewhat relevant passage", "score": 0.8},
        ]

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def test_empty_results_returns_empty(self):
        self.assertEqual(rerank("query", [], base_url=self.url), [])

    def test_low_relevance_results_are_dropped(self):
        self.server.replies = [(200, {"response": "9"}), (200, {"response": "1"}), (200, {"response": "6"})]
        result = rerank("query", self.results, base_url=self.url, rejection_threshold=3.0)
        source_files = [r["source_file"] for r in result]
        self.assertNotIn("b.md", source_files)  # scored 1, below threshold
        self.assertIn("a.md", source_files)
        self.assertIn("c.md", source_files)

    def test_results_reordered_by_rerank_score(self):
        self.server.replies = [(200, {"response": "2"}), (200, {"response": "9"}), (200, {"response": "5"})]
        result = rerank("query", self.results, base_url=self.url, rejection_threshold=0.0)
        self.assertEqual(result[0]["source_file"], "b.md")  # scored 9, now first
        self.assertEqual(result[1]["source_file"], "c.md")  # scored 5
        self.assertEqual(result[2]["source_file"], "a.md")  # scored 2, last

    def test_unreachable_judge_keeps_item_without_rejecting(self):
        result = rerank("query", self.results, base_url="http://127.0.0.1:1")
        self.assertEqual(len(result), 3)  # nothing dropped
        for r in result:
            self.assertIsNone(r["rerank_score"])

    def test_respects_top_n_limit(self):
        self.server.replies = [(200, {"response": "8"})]
        result = rerank("query", self.results, base_url=self.url, top_n=1, rejection_threshold=0.0)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["source_file"], "a.md")

    def test_prompt_includes_query_and_passage(self):
        self.server.replies = [(200, {"response": "5"})]
        rerank("query about cats", [self.results[0]], base_url=self.url, top_n=1)
        sent_prompt = self.server.payloads[0]["prompt"]
        self.assertIn("query about cats", sent_prompt)
        self.assertIn("very relevant passage", sent_prompt)


if __name__ == '__main__':
    unittest.main()