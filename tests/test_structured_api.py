"""API handlers use the real workflow; only model transport is replaced."""
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from fastapi import FastAPI, HTTPException
from pydantic import ValidationError
from core.chat import ChatError
from structured.api import CompletionRequest, GenerateRequest, install_routes
from structured.results import ResultStore


class StructuredApiTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.store = ResultStore(Path(directory.name) / 'test.db')
        self.app = FastAPI()
        settings = SimpleNamespace(default_model='test', clean_ollama_host='http://localhost:11434')
        with patch('structured.api.ResultStore', return_value=self.store), patch.dict('os.environ', {'SENSAI_GUARDRAILS': ''}):
            install_routes(self.app, settings)
        self.routes = {r.path: r.endpoint for r in self.app.routes}
        self.request = GenerateRequest(text='Read the docs', kind='tasks')

    def test_generate_complete_retrieve_and_download(self):
        raw = '{"tasks":[{"title":"Read docs","priority":"medium"}]}'
        with patch('core.chat.stream_reply', return_value=iter([raw])) as stream:
            result = self.routes['/api/structured/generate'](self.request)
        self.assertEqual(stream.call_args.args[:2], ('http://localhost:11434', 'test'))
        result_id = result['id']
        self.routes['/api/structured/results/{result_id}/completion'](
            result_id, CompletionRequest(index=0, completed=True))
        saved = self.routes['/api/structured/results/{result_id}'](result_id)
        self.assertEqual(saved['completed'], [True])
        response = self.routes['/api/structured/results/{result_id}/export'](result_id)
        self.assertEqual(json.loads(response.body), json.loads(raw))
        self.assertEqual(response.media_type, 'application/json')

    def test_offline_model_returns_error_without_stub_or_record(self):
        with patch('core.chat.stream_reply', side_effect=ChatError('offline')) as stream:
            with self.assertRaises(HTTPException) as caught:
                self.routes['/api/structured/generate'](self.request)
        self.assertEqual(caught.exception.status_code, 502)
        stream.assert_called_once()
        self.assertEqual(self.store.list(), [])

    def test_bad_output_returns_422_without_record(self):
        with patch('core.chat.stream_reply', side_effect=lambda *a, **k: iter(['{}'])):
            with self.assertRaises(HTTPException) as caught:
                self.routes['/api/structured/generate'](self.request)
        self.assertEqual(caught.exception.status_code, 422)
        self.assertEqual(self.store.list(), [])

    def test_client_cannot_select_stub_or_outbound_host(self):
        for extra in [{'mode': 'stub'}, {'host': 'http://example.com'}, {'kind': 'unknown'}, {'attempts': 6}]:
            with self.subTest(extra=extra), self.assertRaises(ValidationError):
                GenerateRequest(**({'text': 'Read', 'kind': 'tasks'} | extra))

    def test_missing_result_is_404(self):
        with self.assertRaises(HTTPException) as caught:
            self.routes['/api/structured/results/{result_id}']('missing')
        self.assertEqual(caught.exception.status_code, 404)


if __name__ == '__main__':
    unittest.main()
