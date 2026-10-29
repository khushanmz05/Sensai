"""MCP protocol, policy and native tool-loop checks. No live model required."""
import asyncio
from copy import deepcopy
from dataclasses import replace
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from mcp_tools.config import McpError, load_config
from guardrails import Guardrails, GuardrailError

HAS_MCP = importlib.util.find_spec('mcp') is not None
ROOT = Path(__file__).resolve().parents[1]
if HAS_MCP:
    from mcp.types import CallToolResult, TextContent
    from mcp_tools.gateway import Gateway, Tool, connect
    from mcp_tools.runner import tool_loop, run_turn, TurnResult, request_message, confirm_tool
    from structured.output import JsonOutput
    import httpx


class ConfigTests(unittest.TestCase):
    def test_demo_uses_explicit_allowlist_and_same_python(self):
        import sys
        servers = load_config(ROOT / 'configs/mcp.demo.json')
        self.assertEqual(servers[0].command, sys.executable)
        self.assertEqual(servers[0].auto_approve, ())
        self.assertEqual(servers[0].cwd, str(ROOT))

    def test_rejects_unknown_fields_duplicates_nonfinite_and_unsafe_allowlists(self):
        row = {'name': 'demo', 'command': '$PYTHON', 'args': [], 'allow_tools': ['read']}
        cases = [
            {'servers': [dict(row, auto_approve=['write'])]},
            {'servers': [dict(row, env={'SECRET': 'value'})]},
            {'servers': [dict(row, timeout=True)]},
            {'servers': [dict(row, timeout=0)]},
            {'servers': [dict(row, name='bad/name')]},
            {'servers': [dict(row, allow_tools=[])]},
            {'servers': [dict(row, args='shell command')]},
            {'servers': [row, row]},
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'config.json'
            for case in cases:
                with self.subTest(case=case):
                    path.write_text(json.dumps(case))
                    with self.assertRaises(McpError):
                        load_config(path)
            for raw in ['{"servers":[],"servers":[]}', '{"servers":NaN}', 'x' * 65537]:
                path.write_text(raw)
                with self.assertRaises(McpError):
                    load_config(path)


@unittest.skipUnless(HAS_MCP, 'Install requirements-mcp.txt for MCP tests')
class ProtocolTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_custom_server_discovery_read_and_traversal_refusal(self):
        servers = load_config(ROOT / 'configs/mcp.demo.json')[:1]
        async with connect(servers) as gateway:
            self.assertEqual(list(gateway.tools), ['project__read_project_file'])
            result = await gateway.call('project__read_project_file', {'relative_path': 'project_notes.md'})
            self.assertFalse(result['isError'])
            self.assertIn('SQLite', json.dumps(result))
            refused = await gateway.call('project__read_project_file', {'relative_path': '../README.md'})
            self.assertTrue(refused['isError'])

    @unittest.skipUnless(importlib.util.find_spec('mcp_server_time'), 'Install the external Time server')
    async def test_real_third_party_time_server(self):
        servers = load_config(ROOT / 'configs/mcp.demo.json')[1:]
        async with connect(servers) as gateway:
            result = await gateway.call('time__get_current_time', {'timezone': 'Europe/Madrid'})
            self.assertFalse(result['isError'])
            self.assertIn('Europe/Madrid', json.dumps(result))

    async def test_missing_server_and_missing_allowed_tool_fail_closed(self):
        server = load_config(ROOT / 'configs/mcp.demo.json')[0]
        for broken in [replace(server, command='/sensai-nonexistent-executable'),
                       replace(server, allow_tools=('not_a_tool',))]:
            with self.subTest(broken=broken), self.assertRaises(McpError):
                async with connect([broken]):
                    self.fail('Broken server should not be usable')

    async def test_safe_body_error_survives_sdk_task_group_cleanup(self):
        servers = load_config(ROOT / 'configs/mcp.demo.json')[:1]
        for error in (McpError('MCP action rejected'), GuardrailError('Policy refusal')):
            with self.subTest(error=error), self.assertRaisesRegex(type(error), str(error)):
                async with connect(servers):
                    raise error

    async def test_initialization_timeout_terminates_child(self):
        server = load_config(ROOT / 'configs/mcp.demo.json')[0]
        with tempfile.TemporaryDirectory() as directory:
            pid_path = Path(directory) / 'pid'
            code = 'import os,time,pathlib; pathlib.Path(' + repr(str(pid_path)) + ').write_text(str(os.getpid())); time.sleep(60)'
            server = replace(server, args=('-c', code), timeout=0.3)
            with self.assertRaises(McpError):
                async with connect([server]):
                    self.fail('Unresponsive server should time out')
            import os
            if pid_path.exists():
                with self.assertRaises(ProcessLookupError):
                    os.kill(int(pid_path.read_text()), 0)

    async def test_cancelled_live_call_closes_server_process(self):
        import os
        server = load_config(ROOT / 'configs/mcp.demo.json')[0]
        with tempfile.TemporaryDirectory() as directory:
            pid_path = Path(directory) / 'pid'
            code = (
                'import asyncio,os,pathlib\nfrom mcp.server.fastmcp import FastMCP\n'
                f'pathlib.Path({str(pid_path)!r}).write_text(str(os.getpid()))\n'
                'server=FastMCP("slow")\n@server.tool()\n'
                'async def slow() -> str:\n    await asyncio.sleep(60)\n    return "done"\n'
                'server.run(transport="stdio")\n')
            server = replace(server, args=('-c', code), allow_tools=('slow',))
            started = asyncio.Event()
            async def run():
                async with connect([server]) as gateway:
                    started.set()
                    await gateway.call('project__slow', {})
            task = asyncio.create_task(run())
            await asyncio.wait_for(started.wait(), 10)
            await asyncio.sleep(0.05)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await asyncio.wait_for(task, 10)
            with self.assertRaises(ProcessLookupError):
                os.kill(int(pid_path.read_text()), 0)


@unittest.skipUnless(HAS_MCP, 'Install requirements-mcp.txt for MCP tests')
class LoopTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.gateway = Gateway()
        self.session = AsyncMock()
        self.session.call_tool.return_value = CallToolResult(content=[TextContent(type='text', text='result')])
        server = load_config(ROOT / 'configs/mcp.demo.json')[0]
        self.gateway.tools['project__read'] = Tool('project__read', 'read', server, self.session,
            JsonOutput({'type': 'object', 'properties': {'path': {'type': 'string'}},
                        'required': ['path'], 'additionalProperties': False}), 'read data')
        self.messages = [{'role': 'user', 'content': 'Read a file'}]

    def call(self, args=None, name='project__read'):
        return {'role': 'assistant', 'content': '', 'tool_calls': [
            {'function': {'name': name, 'arguments': {'path': 'notes.md'} if args is None else args}}]}

    async def run_loop(self, replies, **kwargs):
        request = AsyncMock(side_effect=replies)
        result = await tool_loop(self.gateway, self.messages, 'http://localhost:11434', 'model', 5,
                                 request=request, **kwargs)
        return result, request

    async def test_model_tool_model_order_and_immutable_history_and_approval(self):
        original = deepcopy(self.messages)
        def approve(name, args):
            args['path'] = 'changed.md'
            return True
        result, request = await self.run_loop([self.call(), {'role': 'assistant', 'content': 'Final'}], approve=approve)
        self.assertEqual(result.answer, 'Final')
        self.session.call_tool.assert_awaited_once_with('read', arguments={'path': 'notes.md'})
        second = request.call_args_list[1].args[2]
        self.assertEqual(second[-1]['role'], 'tool')
        self.assertEqual(second[-1]['tool_name'], 'project__read')
        self.assertIn('result', second[-1]['content'])
        self.assertEqual(self.messages, original)

    async def test_rejection_stops_entire_batch_and_no_server_call(self):
        calls = self.call()
        calls['tool_calls'] *= 2
        with self.assertRaisesRegex(McpError, 'rejected'):
            await self.run_loop([calls], approve=lambda *_: False)
        self.session.call_tool.assert_not_called()

    async def test_unknown_tool_and_invalid_args_never_reach_server(self):
        for message in [self.call(name='not_allowed'), self.call({'path': 7}),
                        self.call({'path': 'x', 'extra': 1}), self.call('string')]:
            with self.subTest(message=message), self.assertRaises(McpError):
                await self.run_loop([message], approve=lambda *_: True)
        self.session.call_tool.assert_not_called()

    async def test_step_limit_prevents_repeated_calls(self):
        with self.assertRaisesRegex(McpError, 'limit'):
            await self.run_loop([self.call(), self.call()], max_calls=1, approve=lambda *_: True)
        self.assertEqual(self.session.call_tool.await_count, 1)

    async def test_tool_business_error_returns_to_model(self):
        self.session.call_tool.return_value = CallToolResult(isError=True, content=[TextContent(type='text', text='denied')])
        result, request = await self.run_loop([self.call(), {'role': 'assistant', 'content': 'Could not read.'}],
                                            approve=lambda *_: True)
        self.assertTrue(result.evidence[0]['result']['isError'])
        self.assertIn('denied', request.call_args_list[1].args[2][-1]['content'])

    async def test_arguments_and_observations_filtered_before_call_display_and_model(self):
        policy = Guardrails({'redact': ['email']})
        self.gateway.policy = policy
        self.session.call_tool.return_value = CallToolResult(content=[TextContent(type='text', text='a@example.com')])
        events = []
        result, _ = await self.run_loop([self.call({'path': 'a@example.com'}),
                                        {'role': 'assistant', 'content': 'a@example.com'}],
                                       policy=policy, approve=lambda *_: True,
                                       notify=lambda *args: events.append(args))
        self.session.call_tool.assert_awaited_once_with('read', arguments={'path': '[EMAIL]'})
        self.assertEqual(result.answer, '[EMAIL]')
        self.assertNotIn('a@example.com', json.dumps(events))
        self.assertNotIn('a@example.com', json.dumps(result.evidence))

    async def test_blocked_tool_output_is_never_displayed_or_returned(self):
        policy = Guardrails({'blocked_output': ['secret']})
        self.gateway.policy = policy
        self.session.call_tool.return_value = CallToolResult(content=[TextContent(type='text', text='secret')])
        events = []
        with self.assertRaises(GuardrailError):
            await self.run_loop([self.call()], policy=policy, approve=lambda *_: True,
                                notify=lambda event, data: events.append(event))
        self.assertEqual(events, ['call'])

    async def test_input_refusal_precedes_server_startup(self):
        with patch('mcp_tools.runner.connect') as connection:
            with self.assertRaises(GuardrailError):
                await run_turn([], [{'role': 'user', 'content': 'blocked'}], '', '', 5,
                               policy=Guardrails({'blocked_input': ['blocked']}))
            connection.assert_not_called()

    async def test_timeout_disables_connection_without_reexecution(self):
        tool = self.gateway.tools['project__read']
        tool.server = replace(tool.server, timeout=0.01)
        async def slow(*args, **kwargs):
            await asyncio.sleep(10)
        self.session.call_tool.side_effect = slow
        with self.assertRaisesRegex(McpError, 'timed out'):
            await self.gateway.call(tool.name, {'path': 'x'})
        with self.assertRaisesRegex(McpError, 'unavailable'):
            await self.gateway.call(tool.name, {'path': 'x'})
        self.assertEqual(self.session.call_tool.await_count, 1)

    async def test_cancellation_propagates_without_final_answer(self):
        self.session.call_tool.side_effect = asyncio.CancelledError
        with self.assertRaises(asyncio.CancelledError):
            await self.run_loop([self.call()], approve=lambda *_: True)

    async def test_oversized_result_is_rejected(self):
        self.session.call_tool.return_value = CallToolResult(content=[TextContent(type='text', text='x' * 65537)])
        with self.assertRaisesRegex(McpError, '64 KiB'):
            await self.run_loop([self.call()], approve=lambda *_: True)

    async def test_plain_answer_does_not_invent_a_tool_trace(self):
        result, _ = await self.run_loop([{'role': 'assistant', 'content': 'Hello'}])
        self.assertEqual(result.evidence, [])
        self.session.call_tool.assert_not_called()

    def test_human_confirmation_and_terminal_escaping(self):
        output = io.StringIO()
        with patch('builtins.input', return_value='no'), patch('sys.stdout', output):
            self.assertFalse(confirm_tool('project__read', {'path': '\x1b[2J'}))
        self.assertNotIn('\x1b', output.getvalue())
        with patch('builtins.input', return_value='yes'):
            self.assertTrue(confirm_tool('project__read', {'path': 'notes.md'}))


@unittest.skipUnless(HAS_MCP, 'Install requirements-mcp.txt for MCP tests')
class HttpTests(unittest.IsolatedAsyncioTestCase):
    async def test_native_http_contract_and_errors(self):
        real_client = httpx.AsyncClient
        captured = []
        def respond(request):
            captured.append(json.loads(request.content))
            return httpx.Response(200, json={'done': True, 'message': {'role': 'assistant', 'content': 'ok'}})
        with patch('mcp_tools.runner.httpx.AsyncClient',
                   side_effect=lambda **kwargs: real_client(transport=httpx.MockTransport(respond), **kwargs)):
            message = await request_message('http://localhost:11434', 'demo', [], [{'type': 'function'}], 2)
        self.assertEqual(message['content'], 'ok')
        self.assertFalse(captured[0]['stream'])
        self.assertEqual(captured[0]['tools'], [{'type': 'function'}])
        for response in [httpx.Response(400, text='private server body'),
                         httpx.Response(200, text='{"done":true,"done":false}'),
                         httpx.Response(200, json={'done': False}),
                         httpx.Response(200, content=b'x' * 1048577)]:
            with self.subTest(response=response), patch('mcp_tools.runner.httpx.AsyncClient',
                    side_effect=lambda **kwargs: real_client(transport=httpx.MockTransport(lambda _: response), **kwargs)):
                with self.assertRaises(McpError) as caught:
                    await request_message('http://localhost:11434', 'demo', [], [], 2)
                self.assertNotIn('private server body', str(caught.exception))


if __name__ == '__main__':
    unittest.main()
