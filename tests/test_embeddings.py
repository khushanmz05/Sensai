"""Tests for retrieval/embeddings.py using a fake local Ollama server."""
import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

import requests

from retrieval.embeddings import embed


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


class EmbeddingsTests(unittest.TestCase):
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

    def test_returns_embeddings_in_order(self):
        self.server.replies.append((200, {"embeddings": [[0.1, 0.2], [0.3, 0.4]]}))
        result = embed(["hello", "world"], model="test-model", base_url=self.url)
        self.assertEqual(result, [[0.1, 0.2], [0.3, 0.4]])
        self.assertEqual(self.server.payloads[0]["input"], ["hello", "world"])
        self.assertEqual(self.server.payloads[0]["model"], "test-model")

    def test_empty_input_returns_empty_list_no_request(self):
        result = embed([], model="test-model", base_url=self.url)
        self.assertEqual(result, [])
        self.assertEqual(self.server.payloads, [])

    def test_missing_model_raises_clear_error(self):
        self.server.replies.append((404, {"error": "model not found"}))
        with self.assertRaises(RuntimeError) as ctx:
            embed(["hi"], model="missing-model", base_url=self.url)
        self.assertIn("ollama pull missing-model", str(ctx.exception))

    def test_connection_error_raises_clear_error(self):
        with patch('retrieval.embeddings.requests.post', side_effect=requests.ConnectionError):
            with self.assertRaises(RuntimeError) as ctx:
                embed(["hi"], base_url=self.url)
            self.assertIn("ollama serve", str(ctx.exception))

    def test_timeout_raises_clear_error(self):
        with patch('retrieval.embeddings.requests.post', side_effect=requests.Timeout):
            with self.assertRaises(RuntimeError) as ctx:
                embed(["hi"], base_url=self.url)
            self.assertIn("timed out", str(ctx.exception))

    def test_unexpected_response_shape_raises(self):
        self.server.replies.append((200, {"unexpected": "shape"}))
        with self.assertRaises(RuntimeError):
            embed(["hi"], base_url=self.url)


if __name__ == '__main__':
    unittest.main()