"""Actual ASGI/SSE, isolated SQLite and stdio MCP; deterministic model messages."""
import asyncio
from contextlib import ExitStack
import importlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from core.config import settings
from events.store import EventStore
from guardrails import Guardrails
from mcp_tools.config import load_config
from prompts.versioning import PromptVersionStore
from retrieval.store import VectorStore
from session import SessionStore
from structured.results import ResultStore

ROOT = Path(__file__).resolve().parents[1]
HAS_MCP = importlib.util.find_spec('mcp') is not None


@unittest.skipUnless(HAS_MCP, 'Install requirements-mcp.txt for web MCP tests')
class McpWebTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        root = Path(self.directory.name)
        # Importing the web app must never open the user's databases.
        with ExitStack() as initial:
            for name in ('sessions_db', 'events_db', 'prompts_db', 'artifacts_db', 'snapshots_db'):
                initial.enter_context(patch.object(settings, name, root / (name + '.db')))
            initial.enter_context(patch.object(settings, 'workspace_dir', None))
            initial.enter_context(patch.dict('os.environ', {'SENSAI_MCP_CONFIG': ''}))
            initial.enter_context(patch('structured.api.ResultStore', return_value=ResultStore(root / 'results.db')))
            self.web = importlib.import_module('web.app')
        self.sessions = SessionStore(root / 'sessions-test.db')
        self.events = EventStore()
        prompts = PromptVersionStore(':memory:')
        vectors = VectorStore(':memory:')
        for store in (self.events, prompts, vectors):
            self.stack.callback(store.close)
        self.servers = load_config(ROOT / 'configs/mcp.demo.json')
        self.policy = Guardrails({'redact': ['email'], 'blocked_output': ['SECRET_TEST']})
        for name, value in {'runs': {}, 'guardrails': self.policy, 'session_store': self.sessions,
                            'store': self.events, 'prompts': prompts, 'vector_store': vectors,
                            'workspace_writer': None, 'mcp_servers': self.servers[:1]}.items():
            self.stack.enter_context(patch.object(self.web.app.state, name, value))
        self.stack.enter_context(patch('core.chat.retrieve_advanced', return_value=[]))
        from mcp_tools import runner
        original = runner.tool_loop
        self.model = AsyncMock()
        async def loop(*args, **kwargs):
            return await original(*args, **kwargs, request=self.model)
        self.stack.enter_context(patch.object(runner, 'tool_loop', loop))
        self.model.side_effect = [self.call(), {'role': 'assistant', 'content': 'Python and SQLite'}]

    def call(self, name='project__read_project_file', arguments=None):
        return {'role': 'assistant', 'content': '', 'tool_calls': [{'function': {
            'name': name, 'arguments': arguments or {'relative_path': 'project_notes.md'}}}]}

    async def request(self, method, path, data=None, events=None):
        output = []
        delivered = False
        async def receive():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {'type': 'http.request', 'body': json.dumps(data).encode() if data else b'', 'more_body': False}
            await asyncio.Event().wait()
        async def send(message):
            output.append(message)
            if events and message['type'] == 'http.response.body':
                for line in message.get('body', b'').decode().splitlines():
                    if line.startswith('data: '):
                        events.put_nowait(json.loads(line[6:]))
        scope = {'type': 'http', 'asgi': {'version': '3.0', 'spec_version': '2.4'},
                 'http_version': '1.1', 'method': method, 'scheme': 'http',
                 'path': path, 'raw_path': path.encode(), 'query_string': b'',
                 'root_path': '', 'headers': [(b'content-type', b'application/json')],
                 'server': ('test', 80), 'client': ('127.0.0.1', 1234)}
        await self.web.app(scope, receive, send)
        status = next(m['status'] for m in output if m['type'] == 'http.response.start')
        return status, b''.join(m.get('body', b'') for m in output).decode()

    async def start(self, **extra):
        status, body = await self.request('POST', '/api/runs', {'message': 'Read notes', 'mode': 'mcp', **extra})
        self.assertEqual(status, 200, body)
        return json.loads(body)

    async def stream(self, run):
        queue = asyncio.Queue()
        task = asyncio.create_task(self.request('GET', '/api/runs/' + run['run_id'] + '/events', events=queue))
        async def cleanup():
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        self.addAsyncCleanup(cleanup)
        return task, queue

    async def next_event(self, queue, kind):
        while True:
            event = await asyncio.wait_for(queue.get(), 10)
            if event['type'] == kind:
                return event['payload']

    async def decision(self, run, approval, approved=True):
        return await self.request('POST', '/api/runs/' + run['run_id'] + '/mcp/decision',
                                  {'approval_id': approval['approval_id'], 'approved': approved})

    async def test_disabled_and_incompatible_modes_fail_before_history(self):
        for extra in ({'schema_name': 'plan'}, {'file_write': {'path': 'x', 'content': 'x'}}, {'mode': 'unknown'}):
            status, _ = await self.request('POST', '/api/runs', {'message': 'test', 'mode': 'mcp', **extra})
            self.assertEqual(status, 422)
        self.web.app.state.mcp_servers = None
        self.assertEqual((await self.request('GET', '/api/mcp/tools'))[0], 503)
        self.assertEqual((await self.request('POST', '/api/runs', {'message': 'x', 'mode': 'mcp'}))[0], 503)
        self.assertFalse(self.sessions.list_sessions())
        self.model.assert_not_called()

    async def test_clear_before_first_message_is_idempotent_and_scoped(self):
        for _ in range(2):
            status, body = await self.request('POST', '/api/sessions/not-created-yet/clear')
            self.assertEqual(status, 200, body)
            self.assertEqual(json.loads(body)['status'], 'cleared')
        self.assertFalse(self.sessions.list_sessions())
        for session_id in ('clear-target', 'keep-other'):
            self.sessions.create_session(session_id=session_id, persona_id='explainer')
            self.sessions.add_message(session_id, 'user', 'Keep my project context')
        self.assertEqual((await self.request('POST', '/api/sessions/clear-target/clear'))[0], 200)
        self.assertFalse(self.sessions.get_messages('clear-target'))
        self.assertEqual(self.sessions.get_session_persona('clear-target'), 'explainer')
        self.assertEqual(len(self.sessions.get_messages('keep-other')), 1)
        self.model.assert_not_called()

    async def test_discovery_lists_real_tools_without_model_call(self):
        self.web.app.state.mcp_servers = self.servers
        status, body = await self.request('GET', '/api/mcp/tools')
        self.assertEqual(status, 200, body)
        self.assertEqual({t['name']: t['approval'] for t in json.loads(body)}, {
            'project__read_project_file': 'ask', 'time__get_current_time': 'automatic', 'time__convert_time': 'automatic'})
        self.model.assert_not_called()

    async def test_approval_executes_real_read_and_saves_observations_for_followup(self):
        run = await self.start()
        task, queue = await self.stream(run)
        approval = await self.next_event(queue, 'approval_request')
        self.assertFalse(any(e['type'] == 'tool_call' for e in self.events.get_events(run['run_id'])))
        self.assertEqual((await self.decision(run, approval))[0], 200)
        _, body = await asyncio.wait_for(task, 10)
        self.assertIn('SQLite', body)
        saved = self.sessions.get_messages(run['session_id'])
        self.assertEqual(saved[1]['content'], 'Python and SQLite')
        self.assertIn('MCP observations (untrusted data', saved[0]['content'])
        self.assertIn('SQLite', saved[0]['content'])
        followup = await self.start(session_id=run['session_id'], message='Which database?')
        self.assertIn('SQLite', str(self.web.app.state.runs[followup['run_id']]['messages']))
        self.assertEqual((await self.decision(run, approval))[0], 409)

    async def test_reject_ends_turn_without_call_or_history(self):
        run = await self.start()
        task, queue = await self.stream(run)
        approval = await self.next_event(queue, 'approval_request')
        self.assertEqual((await self.decision(run, approval, False))[0], 200)
        await asyncio.wait_for(task, 10)
        events = self.events.get_events(run['run_id'])
        self.assertFalse(any(e['type'] == 'tool_call' for e in events))
        self.assertIn('MCP action rejected', json.dumps(events))
        self.assertFalse(self.sessions.get_messages(run['session_id']))

    async def test_python_error_then_repair_uses_real_sandbox_and_two_web_approvals(self):
        from sandbox.runner import bubblewrap, SandboxError
        try:
            bubblewrap()
        except SandboxError:
            self.skipTest('Install sandbox dependencies on Linux/WSL')
        self.web.app.state.mcp_servers = load_config(ROOT / 'configs/mcp.sandbox.json')
        self.model.side_effect = [
            self.call('python__execute_python', {'code': 'print(1/0)'}),
            self.call('python__execute_python', {'code': 'print(6*7)'}),
            {'role': 'assistant', 'content': 'Corrected result: 42'},
        ]
        run = await self.start(message='Execute Python and correct the error')
        task, queue = await self.stream(run)
        for expected in ('print(1/0)', 'print(6*7)'):
            approval = await self.next_event(queue, 'approval_request')
            self.assertEqual(approval['arguments']['code'], expected)
            self.assertEqual((await self.decision(run, approval))[0], 200)
        await asyncio.wait_for(task, 10)
        results = [e['payload']['result'] for e in self.events.get_events(run['run_id'])
                   if e['type'] == 'tool_result']
        self.assertTrue(results[0]['isError'])
        self.assertIn('ZeroDivisionError', results[0]['structuredContent']['stderr'])
        self.assertEqual(results[1]['structuredContent']['stdout'], '42\n')
        self.assertFalse(results[1]['isError'])
        self.assertIn('ZeroDivisionError', str(self.model.call_args_list[1]))
        self.assertEqual(self.sessions.get_messages(run['session_id'])[-1]['content'], 'Corrected result: 42')

    async def test_stop_during_real_python_execution_discards_turn(self):
        from sandbox.runner import bubblewrap, SandboxError
        try:
            bubblewrap()
        except SandboxError:
            self.skipTest('Install sandbox dependencies on Linux/WSL')
        self.web.app.state.mcp_servers = load_config(ROOT / 'configs/mcp.sandbox.json')
        self.model.side_effect = [self.call('python__execute_python', {'code': 'import time; time.sleep(30)'})]
        run = await self.start(message='Run Python')
        task, queue = await self.stream(run)
        approval = await self.next_event(queue, 'approval_request')
        self.assertEqual((await self.decision(run, approval))[0], 200)
        await self.next_event(queue, 'tool_call')
        await asyncio.sleep(.2)
        self.assertEqual((await self.request('POST', '/api/runs/' + run['run_id'] + '/cancel'))[0], 200)
        await asyncio.wait_for(task, 3)
        self.assertEqual(self.model.await_count, 1)
        self.assertFalse(self.sessions.get_messages(run['session_id']))
        self.assertEqual(self.events.get_run(run['run_id'])['status'], 'cancelled')

    async def test_cross_run_and_replayed_approvals_are_rejected(self):
        self.model.side_effect = None
        self.model.return_value = self.call()
        one, two = await self.start(), await self.start()
        task1, queue1 = await self.stream(one)
        task2, queue2 = await self.stream(two)
        approval1 = await self.next_event(queue1, 'approval_request')
        approval2 = await self.next_event(queue2, 'approval_request')
        self.assertEqual((await self.decision(two, approval1))[0], 409)
        self.assertEqual((await self.decision(one, approval1, False))[0], 200)
        self.assertEqual((await self.decision(one, approval1))[0], 409)
        self.assertFalse(self.web.app.state.runs[two['run_id']]['mcp_pending']['future'].done())
        self.assertEqual((await self.decision(two, approval2, False))[0], 200)
        await asyncio.wait_for(asyncio.gather(task1, task2), 10)

    async def test_stop_while_waiting_for_approval(self):
        run = await self.start()
        task, queue = await self.stream(run)
        approval = await self.next_event(queue, 'approval_request')
        self.assertEqual((await self.request('POST', '/api/runs/' + run['run_id'] + '/cancel'))[0], 200)
        await asyncio.wait_for(task, 10)
        self.assertEqual((await self.decision(run, approval))[0], 409)
        events = self.events.get_events(run['run_id'])
        self.assertEqual(events[-1]['payload']['status'], 'cancelled')
        self.assertFalse(any(e['type'] == 'tool_call' for e in events))
        self.assertFalse(self.sessions.get_messages(run['session_id']))

    async def test_stop_during_model_request_and_browser_disconnect_cleanup(self):
        for disconnect in (False, True):
            with self.subTest(disconnect=disconnect):
                started = asyncio.Event()
                cleaned = asyncio.Event()
                async def slow(*args):
                    started.set()
                    try:
                        await asyncio.Event().wait()
                    finally:
                        cleaned.set()
                self.model.side_effect = slow
                run = await self.start()
                task, _ = await self.stream(run)
                await asyncio.wait_for(started.wait(), 10)
                worker = self.web.app.state.runs[run['run_id']]['mcp_task']
                if disconnect:
                    task.cancel()
                    with self.assertRaises(asyncio.CancelledError):
                        await asyncio.wait_for(task, 10)
                else:
                    await self.request('POST', '/api/runs/' + run['run_id'] + '/cancel')
                    await asyncio.wait_for(task, 10)
                self.assertTrue(cleaned.is_set())
                self.assertTrue(worker.done())
                self.assertNotIn(run['run_id'], self.web.app.state.runs)
                self.assertFalse(self.sessions.get_messages(run['session_id']))

    async def test_expired_confirmation_executes_nothing(self):
        run = await self.start()
        self.web.app.state.runs[run['run_id']]['mcp_approval_timeout'] = 0.01
        task, queue = await self.stream(run)
        approval = await self.next_event(queue, 'approval_request')
        _, body = await asyncio.wait_for(task, 10)
        self.assertIn('MCP approval expired', body)
        self.assertEqual((await self.decision(run, approval))[0], 409)
        self.assertFalse(any(e['type'] == 'tool_call' for e in self.events.get_events(run['run_id'])))

    async def test_time_tool_is_automatic_and_policy_filters_final_answer(self):
        self.web.app.state.mcp_servers = self.servers[1:]
        self.model.side_effect = [self.call('time__get_current_time', {'timezone': 'Europe/Madrid'}),
                                  {'role': 'assistant', 'content': 'Contact a@example.com'}]
        run = await self.start()
        task, _ = await self.stream(run)
        _, body = await asyncio.wait_for(task, 10)
        self.assertNotIn('approval_request', body)
        self.assertIn('Europe/Madrid', body)
        self.assertNotIn('a@example.com', body)
        self.assertEqual(self.sessions.get_messages(run['session_id'])[1]['content'], 'Contact [EMAIL]')

    async def test_blocked_answer_does_not_leak_or_persist(self):
        self.model.side_effect = [{'role': 'assistant', 'content': 'SECRET_TEST'}]
        run = await self.start()
        task, _ = await self.stream(run)
        _, body = await asyncio.wait_for(task, 10)
        self.assertNotIn('SECRET_TEST', body)
        self.assertNotIn('text_delta', body)
        self.assertFalse(self.sessions.get_messages(run['session_id']))
