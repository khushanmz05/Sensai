"""Tests for retrieval/rewrite.py using a fake local Ollama server."""
import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from retrieval.rewrite import rewrite_query


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


class RewriteQueryTests(unittest.TestCase):
    def setUp(self):
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.server.payloads = []
        self.server.replies = []
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f'http://127.0.0.1:{self.server.server_port}'

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def test_empty_query_returns_empty_list(self):
        self.assertEqual(rewrite_query("   ", base_url=self.url), [])
        self.assertEqual(self.server.payloads, [])

    def test_returns_original_plus_rewrites(self):
        self.server.replies.append((200, {
            "response": "how do cats behave\nfeline behavior patterns"
        }))
        result = rewrite_query("why do cats act weird", base_url=self.url)
        self.assertEqual(result, [
            "why do cats act weird",
            "how do cats behave",
            "feline behavior patterns",
        ])

    def test_prompt_includes_the_query(self):
        self.server.replies.append((200, {"response": "rewritten query"}))
        rewrite_query("test question", base_url=self.url)
        self.assertIn("test question", self.server.payloads[0]["prompt"])

    def test_connection_failure_falls_back_to_original(self):
        # Point at a port nothing is listening on.
        result = rewrite_query("original query", base_url="http://127.0.0.1:1")
        self.assertEqual(result, ["original query"])

    def test_empty_model_response_falls_back_to_original(self):
        self.server.replies.append((200, {"response": ""}))
        result = rewrite_query("original query", base_url=self.url)
        self.assertEqual(result, ["original query"])

    def test_non_200_status_falls_back_to_original(self):
        self.server.replies.append((500, {"error": "server error"}))
        result = rewrite_query("original query", base_url=self.url)
        self.assertEqual(result, ["original query"])


if __name__ == '__main__':
    unittest.main()