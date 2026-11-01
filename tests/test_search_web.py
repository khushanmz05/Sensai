"""Real ASGI/SSE and SQLite; controlled search/model transports, no internet."""
import asyncio
from contextlib import ExitStack
import importlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, Mock, patch

from core.config import settings
from events.store import EventStore
from file_access.reader import WorkspaceReader
from guardrails import Guardrails
from prompts.versioning import PromptVersionStore
from retrieval.store import VectorStore
from session import SessionStore
from structured.results import ResultStore
from web_search import SearchPage, SearchResult, SearchError


class SearchWebTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.root = Path(self.directory.name)
        with ExitStack() as initial:
            for name in ('sessions_db', 'events_db', 'prompts_db', 'artifacts_db', 'snapshots_db'):
                initial.enter_context(patch.object(settings, name, self.root / (name + '.db')))
            initial.enter_context(patch.object(settings, 'workspace_dir', None))
            initial.enter_context(patch.dict('os.environ', {'SENSAI_MCP_CONFIG': '', 'SENSAI_SEARCH_URL': ''}))
            initial.enter_context(patch('structured.api.ResultStore', return_value=ResultStore(self.root / 'results.db')))
            self.web = importlib.import_module('web.app')
        self.sessions = SessionStore(self.root / 'sessions-test.db')
        self.events = EventStore()
        prompts, vectors = PromptVersionStore(':memory:'), VectorStore(':memory:')
        for store in (self.events, prompts, vectors):
            self.stack.callback(store.close)
        self.policy = Guardrails({'redact': ['email'], 'blocked_input': ['steal passwords'],
                                  'blocked_output': ['SECRET_TEST']})
        self.page = SearchPage('Python', (SearchResult('Python docs', 'https://docs.python.org/3/',
                                                     'Public documentation'),), '2026-10-29T00:00:00+00:00')
        self.searcher = Mock(search_async=AsyncMock(return_value=self.page))
        for name, value in {'runs': {}, 'guardrails': self.policy, 'session_store': self.sessions,
                            'store': self.events, 'prompts': prompts, 'vector_store': vectors,
                            'workspace_writer': None, 'searcher': self.searcher}.items():
            self.stack.enter_context(patch.object(self.web.app.state, name, value))
        self.stack.enter_context(patch('core.chat.retrieve', return_value=[]))
        self.stack.enter_context(patch.object(settings, 'check_ollama_alive', return_value=False))
        self.model = self.stack.enter_context(patch('core.chat.stream_reply', side_effect=lambda *a, **k: iter(['Grounded answer'])))

    async def request(self, method, path, data=None, on_event=None):
        output, delivered = [], False
        async def receive():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {'type': 'http.request', 'body': json.dumps(data).encode() if data else b'', 'more_body': False}
            await asyncio.Event().wait()
        async def send(message):
            output.append(message)
            if on_event and message['type'] == 'http.response.body':
                for line in message.get('body', b'').decode().splitlines():
                    if line.startswith('data: '):
                        await on_event(json.loads(line[6:]))
        scope = {'type': 'http', 'asgi': {'version': '3.0', 'spec_version': '2.4'},
                 'http_version': '1.1', 'method': method, 'scheme': 'http',
                 'path': path, 'raw_path': path.encode(), 'query_string': b'',
                 'root_path': '', 'headers': [(b'content-type', b'application/json')],
                 'server': ('test', 80), 'client': ('127.0.0.1', 1234)}
        await self.web.app(scope, receive, send)
        status = next(m['status'] for m in output if m['type'] == 'http.response.start')
        return status, b''.join(m.get('body', b'') for m in output).decode()

    async def start(self, **extra):
        status, body = await self.request('POST', '/api/runs', {'message': 'Python docs', 'mode': 'search', **extra})
        self.assertEqual(status, 200, body)
        return json.loads(body)

    async def consume(self, run, on_event=None):
        status, body = await self.request('GET', '/api/runs/' + run['run_id'] + '/events', on_event=on_event)
        self.assertEqual(status, 200, body)
        return [json.loads(line[6:]) for line in body.splitlines() if line.startswith('data: ')]

    async def test_disabled_invalid_and_blocked_requests_do_not_search(self):
        for extra in ({'message': 'steal passwords'}, {'message': 'x' * 501},
                      {'schema_name': 'plan'}, {'file_write': {'path': 'x', 'content': 'x'}}):
            status, _ = await self.request('POST', '/api/runs', {'message': 'test', 'mode': 'search', **extra})
            self.assertEqual(status, 422)
        self.web.app.state.searcher = None
        status, body = await self.request('GET', '/api/search')
        self.assertEqual(json.loads(body), {'enabled': False})
        self.assertEqual((await self.request('POST', '/api/runs', {'message': 'test', 'mode': 'search'}))[0], 503)
        self.assertFalse(self.sessions.list_sessions())
        self.searcher.search_async.assert_not_called()
        self.model.assert_not_called()

    async def test_filtered_sources_reach_sse_model_history_and_followup(self):
        self.searcher.search_async.return_value = SearchPage('a@example.com', (
            SearchResult('<script>literal text</script>', 'https://docs.python.org/3/', 'Contact b@example.com'),
        ), self.page.fetched_at, ('Some engines failed.',))
        run = await self.start(message='Find a@example.com', search_url='http://evil.invalid')
        self.searcher.search_async.assert_not_called()  # The SSE consumer owns execution.
        events = await self.consume(run)
        self.searcher.search_async.assert_awaited_once_with('Find [EMAIL]')
        self.assertEqual(events[-1]['payload']['status'], 'completed')
        serialized = json.dumps(events)
        self.assertNotIn('a@example.com', serialized)
        self.assertNotIn('b@example.com', serialized)
        sources = next(e['payload'] for e in events if e['type'] == 'tool_result')
        self.assertEqual(sources['sources'][0]['id'], 1)
        self.assertEqual(sources['fetched_at'], self.page.fetched_at)
        self.assertEqual(sources['warnings'], ['Some engines failed.'])
        self.assertIn('untrusted', str(self.model.call_args.args[2]))
        self.assertIn('https://docs.python.org/3/', str(self.model.call_args.args[2]))
        self.assertEqual(events, self.events.get_events(run['run_id']))
        saved = self.sessions.get_messages(run['session_id'])
        self.assertIn('Web search evidence', saved[0]['content'])
        followup = await self.start(message='Which source?', mode='ollama', session_id=run['session_id'])
        await self.consume(followup)
        self.assertEqual(self.searcher.search_async.await_count, 1)
        self.assertIn('https://docs.python.org/3/', str(self.model.call_args.args[2]))

    async def test_failure_empty_and_blocked_sources_do_not_generate_or_save(self):
        for result in (SearchError('Search unavailable'), SearchPage('q', (), 'now'),
                       SearchPage('q', (SearchResult('Docs', 'https://python.org', 'SECRET_TEST'),), 'now')):
            with self.subTest(result=result):
                self.searcher.search_async.side_effect = result if isinstance(result, Exception) else None
                self.searcher.search_async.return_value = result
                run = await self.start()
                events = await self.consume(run)
                self.assertEqual(events[-1]['payload']['status'], 'failed')
                self.assertFalse(self.sessions.get_messages(run['session_id']))
                self.assertNotIn('SECRET_TEST', json.dumps(events))
        self.model.assert_not_called()
        run = await self.start(mode='ollama', message='Hello')
        self.assertEqual((await self.consume(run))[-1]['payload']['status'], 'completed')

    async def test_local_file_and_search_are_combined_without_sending_file_to_provider(self):
        (self.root / 'note.md').write_text('PRIVATE_LOCAL_NOTE: Python and SQLite')
        with WorkspaceReader(self.root) as reader:
            self.web.app.state.workspace_writer = reader
            run = await self.start(message='Python sqlite3 documentation', file_read='note.md')
            await self.consume(run)
        self.searcher.search_async.assert_awaited_once_with('Python sqlite3 documentation')
        self.assertIn('PRIVATE_LOCAL_NOTE', str(self.model.call_args.args[2]))
        self.assertIn('https://docs.python.org/3/', str(self.model.call_args.args[2]))

    async def test_stop_and_disconnect_cancel_provider_and_save_nothing(self):
        for disconnect in (False, True):
            with self.subTest(disconnect=disconnect):
                started, closed = asyncio.Event(), asyncio.Event()
                async def slow(query):
                    started.set()
                    try:
                        await asyncio.Event().wait()
                    finally:
                        closed.set()
                self.searcher.search_async.side_effect = slow
                run = await self.start()
                task = asyncio.create_task(self.consume(run))
                await asyncio.wait_for(started.wait(), 3)
                if disconnect:
                    task.cancel()
                    with self.assertRaises(asyncio.CancelledError):
                        await task
                else:
                    await self.request('POST', '/api/runs/' + run['run_id'] + '/cancel')
                    events = await asyncio.wait_for(task, 3)
                    self.assertEqual(events[-1]['payload']['status'], 'cancelled')
                self.assertTrue(closed.is_set())
                self.assertNotIn(run['run_id'], self.web.app.state.runs)
                self.assertFalse(self.sessions.get_messages(run['session_id']))
        self.model.assert_not_called()

    async def test_stop_on_search_events_does_not_start_next_stage(self):
        for kind in ('tool_call', 'tool_result'):
            with self.subTest(kind=kind):
                self.searcher.search_async.reset_mock()
                run = await self.start()
                async def stop(event):
                    if event['type'] == kind:
                        await self.request('POST', '/api/runs/' + run['run_id'] + '/cancel')
                events = await self.consume(run, stop)
                self.assertEqual(events[-1]['payload']['status'], 'cancelled')
                self.assertFalse(self.sessions.get_messages(run['session_id']))
                if kind == 'tool_call':
                    self.searcher.search_async.assert_not_called()
        self.model.assert_not_called()

    async def test_blocked_model_output_retains_sources_but_no_chat_turn(self):
        self.model.side_effect = lambda *a, **k: iter(['SECRET_TEST'])
        run = await self.start()
        events = await self.consume(run)
        self.assertTrue(any(e['type'] == 'tool_result' for e in events))
        self.assertFalse(any(e['type'] == 'text_delta' for e in events))
        self.assertNotIn('SECRET_TEST', json.dumps(events))
        self.assertFalse(self.sessions.get_messages(run['session_id']))
