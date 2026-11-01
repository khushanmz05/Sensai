"""Real FastAPI/ASGI requests and SQLite stores, deterministic model transport.

No HTTP test-client dependency is needed. Tests never contact Ollama.
"""
import asyncio
from contextlib import ExitStack
import importlib
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

from core.config import settings
from core.chat import ChatError
from guardrails import Guardrails
from events.store import EventStore
from session import SessionStore
from retrieval.store import VectorStore
from export.service import SnapshotStore
from structured.results import ResultStore


class WebGuardrailTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bootstrap = tempfile.TemporaryDirectory()
        cls.saved_settings = ExitStack()
        for field in ('sessions_db', 'events_db', 'prompts_db', 'artifacts_db', 'snapshots_db'):
            cls.saved_settings.enter_context(patch.object(settings, field, Path(cls.bootstrap.name) / (field + '.db')))
        cls.saved_settings.enter_context(patch.object(settings, 'workspace_dir', None))
        with patch('structured.api.ResultStore', return_value=ResultStore(Path(cls.bootstrap.name) / 'structured.db')):
            cls.web = importlib.import_module('web.app')

    @classmethod
    def tearDownClass(cls):
        # Release import-time stores before removing their temporary directory.
        for name in ('store', 'prompts', 'artifacts', 'snapshots', 'vector_store'):
            store = getattr(cls.web.app.state, name)
            if hasattr(store, 'close'):
                store.close()
        cls.saved_settings.close()
        cls.bootstrap.cleanup()

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        state = self.web.app.state
        self.policy = Guardrails({'blocked_input': ['steal passwords'],
                                  'blocked_output': ['CONFIDENTIAL_INTERNAL_ONLY'],
                                  'redact': ['email', 'phone'], 'max_output_chars': 10000})
        self.sessions = SessionStore(Path(self.directory.name) / 'sessions.db')
        self.events = EventStore()
        self.vectors = VectorStore(':memory:')
        self.snapshots = SnapshotStore()
        for store in (self.events, self.vectors, self.snapshots):
            self.stack.callback(store.close)
        for name, value in {'guardrails': self.policy, 'session_store': self.sessions,
                            'store': self.events, 'vector_store': self.vectors,
                            'snapshots': self.snapshots, 'runs': {}, 'delay': 0,
                            'workspace_writer': None,
                            'structured_store': ResultStore(Path(self.directory.name) / 'results.db')}.items():
            self.stack.enter_context(patch.object(state, name, value))
        self.retrieve = self.stack.enter_context(patch('core.chat.retrieve_advanced', return_value=[]))
        self.stack.enter_context(patch.object(settings, 'check_ollama_alive', return_value=True))

    async def async_request(self, method, path, payload=None):
        raw = json.dumps(payload).encode() if payload is not None else b''
        output = []
        delivered = False
        async def receive():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {'type': 'http.request', 'body': raw, 'more_body': False}
            await asyncio.Event().wait()
        async def send(message):
            output.append(message)
        scope = {'type': 'http', 'asgi': {'version': '3.0', 'spec_version': '2.4'},
                 'http_version': '1.1', 'method': method, 'scheme': 'http',
                 'path': path, 'raw_path': path.encode(), 'query_string': b'',
                 'root_path': '', 'headers': [(b'content-type', b'application/json')],
                 'server': ('test', 80), 'client': ('127.0.0.1', 1234)}
        await self.web.app(scope, receive, send)
        status = next(item['status'] for item in output if item['type'] == 'http.response.start')
        body = b''.join(item.get('body', b'') for item in output if item['type'] == 'http.response.body').decode()
        return status, body

    def request(self, method, path, payload=None):
        return asyncio.run(self.async_request(method, path, payload))

    def start(self, message='Hello', **extra):
        status, body = self.request('POST', '/api/runs', {'message': message, 'mode': 'ollama', **extra})
        self.assertEqual(status, 200, body)
        return json.loads(body)

    def consume(self, run):
        status, body = self.request('GET', '/api/runs/' + run['run_id'] + '/events')
        self.assertEqual(status, 200, body)
        return [json.loads(line[6:]) for line in body.splitlines() if line.startswith('data: ')]

    def test_blocked_input_stops_before_retrieval_session_or_run(self):
        with patch('core.chat.stream_reply') as model:
            status, body = self.request('POST', '/api/runs', {'message': 'Please STEAL passwords'})
        self.assertEqual(status, 422)
        self.assertNotIn('STEAL passwords', body)
        self.retrieve.assert_not_called()
        model.assert_not_called()
        self.assertEqual(self.sessions.list_sessions(), [])
        self.assertEqual(self.events.get_runs(), [])

    def test_input_and_split_output_are_filtered_in_model_sse_history_logs(self):
        run = self.start('Contact a@example.com +34 612 345 678')
        self.assertEqual(run['message'], 'Contact [EMAIL] [PHONE]')
        self.assertEqual(self.retrieve.call_args.args[0], 'Contact [EMAIL] [PHONE]')
        with patch('core.chat.stream_reply', return_value=iter(['Reply b@', 'example.com +34 612', ' 345 678'])) as model:
            events = self.consume(run)
        self.assertIn('[EMAIL]', str(model.call_args.args[2]))
        self.assertNotIn('a@example.com', str(model.call_args))
        text = ''.join(e['payload']['text'] for e in events if e['type'] == 'text_delta')
        self.assertEqual(text, 'Reply [EMAIL] [PHONE]')
        saved = self.sessions.get_messages(run['session_id'])
        self.assertEqual([m['content'] for m in saved], ['Contact [EMAIL] [PHONE]', text])
        self.assertEqual(events, self.events.get_events(run['run_id']))

    def test_blocked_output_releases_no_prefix_and_saves_no_turn(self):
        run = self.start()
        with patch('core.chat.stream_reply', return_value=iter(['Safe prefix ', 'CONFIDENTIAL_', 'INTERNAL_ONLY'])):
            events = self.consume(run)
        self.assertFalse(any(e['type'] == 'text_delta' for e in events))
        self.assertEqual(events[-1]['payload']['status'], 'failed')
        self.assertEqual(self.sessions.get_messages(run['session_id']), [])
        self.assertNotIn('CONFIDENTIAL_INTERNAL_ONLY', json.dumps(self.events.get_events(run['run_id'])))

    def test_remote_error_does_not_leak_and_next_request_recovers(self):
        run = self.start()
        with patch('core.chat.stream_reply', side_effect=ChatError('server echo a@example.com')):
            events = self.consume(run)
        self.assertNotIn('a@example.com', json.dumps(events))
        run = self.start(session_id=run['session_id'])
        with patch('core.chat.stream_reply', return_value=iter(['OK'])):
            self.assertEqual(self.consume(run)[-1]['payload']['status'], 'completed')

    def test_retrieved_context_and_source_metadata_are_filtered(self):
        self.retrieve.return_value = [{'source_file': 'a@example.com.txt', 'start_line': 1,
                                      'end_line': 1, 'score': 1.0, 'content': 'b@example.com'}]
        run = self.start()
        with patch('core.chat.stream_reply', return_value=iter(['OK'])) as model:
            events = self.consume(run)
        self.assertNotIn('@example.com', str(model.call_args))
        self.assertNotIn('@example.com', json.dumps(events))

    def test_blocked_retrieved_context_creates_no_run(self):
        self.retrieve.return_value = [{'source_file': 'notes.txt', 'content': 'steal passwords'}]
        status, _ = self.request('POST', '/api/runs', {'message': 'Hello'})
        self.assertEqual(status, 422)
        self.assertEqual(self.events.get_runs(), [])

    def test_attachment_is_checked_before_retrieval(self):
        from types import SimpleNamespace
        writer = Mock()
        writer.read_text.return_value = SimpleNamespace(path='note.txt', content='steal passwords')
        with patch.object(self.web.app.state, 'workspace_writer', writer):
            status, _ = self.request('POST', '/api/runs', {'message': 'Read', 'file_read': 'note.txt'})
        self.assertEqual(status, 422)
        self.retrieve.assert_not_called()

    def test_guarded_schema_and_structured_output(self):
        schema = {'type': 'object', 'properties': {'contact': {'type': 'string'}}, 'required': ['contact']}
        with patch('core.chat.stream_reply', return_value=iter(['{"contact":"b\\u0040example.com"}'])):
            status, body = self.request('POST', '/api/structured/generate',
                                        {'kind': 'custom', 'text': 'Extract contact', 'schema': schema})
        self.assertEqual(status, 200, body)
        record = json.loads(body)
        self.assertEqual(record['data']['contact'], '[EMAIL]')
        status, exported = self.request('GET', '/api/structured/results/' + record['id'] + '/export')
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(exported), {'contact': '[EMAIL]'})

    def test_pii_schema_is_refused_before_model(self):
        schema = {'type': 'object', 'description': 'a@example.com'}
        with patch('core.chat.stream_reply') as model:
            status, body = self.request('POST', '/api/structured/generate',
                                        {'kind': 'custom', 'text': 'Extract', 'schema': schema})
        self.assertEqual(status, 422)
        model.assert_not_called()
        self.assertNotIn('a@example.com', body)

    def test_pii_schema_conflict_refuses_instead_of_breaking_contract(self):
        schema = {'type': 'object', 'properties': {'contact': {'type': 'string', 'format': 'email'}}, 'required': ['contact']}
        with patch('core.chat.stream_reply', return_value=iter(['{"contact":"b@example.com"}'])):
            status, _ = self.request('POST', '/api/structured/generate',
                                     {'kind': 'custom', 'text': 'Extract', 'schema': schema})
        self.assertEqual(status, 422)
        self.assertEqual(self.web.app.state.structured_store.list(), [])

    def test_snapshots_filter_new_data_and_refuse_old_unfiltered_exports(self):
        status, body = self.request('POST', '/api/snapshots', {'title': 'Demo', 'type': 'conversation',
                                                             'data': {'messages': [{'role': 'assistant', 'content': 'a@example.com'}]}})
        self.assertEqual(status, 200, body)
        self.assertNotIn('a@example.com', body)
        self.snapshots.publish_snapshot('Old', 'conversation', {'messages': [{'role': 'assistant', 'content': 'a@example.com'}]}, custom_id='legacy')
        for path in ('/p/legacy', '/p/legacy/export'):
            status, body = self.request('GET', path)
            self.assertEqual(status, 422)
            self.assertNotIn('a@example.com', body)

    def test_ingestion_filters_before_embeddings_and_storage(self):
        with patch('web.app.embed', return_value=[[1.0]]) as embed:
            status, body = self.request('POST', '/api/retrieval/ingest', {'content': 'a@example.com'})
        self.assertEqual(status, 200, body)
        self.assertEqual(embed.call_args.args[0], ['[EMAIL]'])
        self.assertEqual(self.vectors.get_all()[0]['content'], '[EMAIL]')

    def test_invalid_http_fields_do_not_echo_input(self):
        status, body = self.request('POST', '/api/runs', {'message': {'bad': 'a@example.com'}})
        self.assertEqual(status, 422)
        self.assertNotIn('a@example.com', body)

    def test_disabled_policy_preserves_streaming(self):
        self.web.app.state.guardrails = None
        run = self.start('a@example.com')
        cache = Mock()
        cache.get.return_value = (None, 0.0, [1.0, 0.0])
        with patch('core.chat.get_semantic_cache', return_value=cache), patch(
            'core.chat.stream_reply', return_value=iter(['a@', 'example.com'])
        ):
            events = self.consume(run)
        self.assertEqual([e['payload']['text'] for e in events if e['type'] == 'text_delta'], ['a@', 'example.com'])

    def test_output_limit_fails_without_releasing_buffer(self):
        self.policy.max_output_chars = 10
        run = self.start()
        with patch('core.chat.stream_reply', return_value=iter(['123456', '789012'])):
            events = self.consume(run)
        self.assertFalse(any(e['type'] == 'text_delta' for e in events))
        self.assertEqual(events[-1]['payload']['status'], 'failed')
        self.assertEqual(self.sessions.get_messages(run['session_id']), [])

    def test_stub_mode_does_not_bypass_output_policy(self):
        run = self.start('CONFIDENTIAL_INTERNAL_ONLY', mode='stub')
        events = self.consume(run)
        self.assertFalse(any(e['type'] == 'text_delta' for e in events))
        self.assertEqual(events[-1]['payload']['status'], 'failed')

    def test_policy_status_reports_configuration_without_rule_text(self):
        status, body = self.request('GET', '/api/guardrails')
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(body)['enabled'])
        self.assertNotIn('steal passwords', body)

    def test_cancel_during_buffered_generation_releases_nothing(self):
        started = threading.Event()
        finished = threading.Event()
        def model(*args, stop_event=None, **kwargs):
            try:
                yield 'a@'
                started.set()
                stop_event.wait(3)
                yield 'example.com'
            finally:
                finished.set()
        async def scenario():
            run = self.start_result
            task = asyncio.create_task(self.async_request('GET', '/api/runs/' + run['run_id'] + '/events'))
            await asyncio.to_thread(started.wait, 2)
            self.assertTrue(started.is_set())
            await self.async_request('POST', '/api/runs/' + run['run_id'] + '/cancel')
            return await asyncio.wait_for(task, timeout=3)
        self.start_result = self.start()
        with patch('core.chat.stream_reply', side_effect=model):
            status, body = asyncio.run(scenario())
            self.assertTrue(finished.wait(2))
        self.assertEqual(status, 200)
        self.assertNotIn('text_delta', body)
        self.assertIn('cancelled', body)
        self.assertEqual(self.sessions.get_messages(self.start_result['session_id']), [])

if __name__ == '__main__':
    unittest.main()
