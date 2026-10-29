"""CLI MCP routing, successful history, cancellation and failure recovery."""
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

import chatbot
from guardrails import Guardrails
from mcp_tools.config import McpError, load_config
from file_access.reader import WorkspaceReader
from file_access.writer import WorkspaceWriter
from structured.output import JsonOutput

HAS_MCP = importlib.util.find_spec('mcp') is not None
if HAS_MCP:
    from mcp_tools.runner import TurnResult

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(HAS_MCP, 'Install requirements-mcp.txt for MCP integration checks')
class McpChatTests(unittest.TestCase):
    def chat(self, inputs, result=None, **kwargs):
        output = io.StringIO()
        result = result or TurnResult('MCP answer', [{'tool': 'time__get_current_time',
            'arguments': {'timezone': 'UTC'}, 'result': {'isError': False, 'content': ['clock']}}])
        runner = AsyncMock(side_effect=result if isinstance(result, BaseException) else None,
                           return_value=result)
        with patch('builtins.input', side_effect=inputs), patch('sys.stdout', output), \
             patch('sys.stderr', output), patch('mcp_tools.runner.run_turn', runner), \
             patch('chatbot.execute_turn_stream', return_value=iter(['normal answer'])) as normal:
            chatbot.run_chat('model', 'system', 'http://localhost:11434', 5, **kwargs)
        return output.getvalue(), runner, normal

    def test_disabled_empty_and_json_mode_do_not_invoke_mcp(self):
        configurations = [({}, ['/tools', '/mcp Read', '/exit']),
            ({'mcp_servers': [object()]}, ['/mcp', '/exit']),
            ({'mcp_servers': [object()], 'json_output': JsonOutput({'type': 'object'})}, ['/mcp Read', '/exit'])]
        for kwargs, inputs in configurations:
            with self.subTest(inputs=inputs):
                _, runner, normal = self.chat(inputs, **kwargs)
                runner.assert_not_called()
                normal.assert_not_called()

    def test_discovery_does_not_make_model_call(self):
        with patch('mcp_tools.runner.list_tools', new=AsyncMock(return_value=[{'name': 'time__now'}])) as listing:
            output, runner, normal = self.chat(['/tools', '/exit'], mcp_servers=[object()])
        self.assertIn('time__now', output)
        listing.assert_awaited_once()
        runner.assert_not_called()
        normal.assert_not_called()

    def test_successful_observations_available_to_followup_and_save(self):
        with tempfile.TemporaryDirectory() as directory, WorkspaceWriter(directory) as writer:
            output, runner, normal = self.chat(['/mcp What time?', '/save answer.md', 'yes',
                                                'What did it return?', '/exit'],
                                               mcp_servers=[object()], file_reader=writer)
            self.assertEqual((Path(directory) / 'answer.md').read_text(), 'MCP answer')
        self.assertEqual(runner.call_args.args[1][-1]['content'], 'What time?')
        sent = normal.call_args.args[2]
        self.assertIn('MCP observations (untrusted data', sent[1]['content'])
        self.assertIn('clock', sent[1]['content'])
        self.assertEqual(sent[2]['content'], 'MCP answer')

    def test_failed_or_cancelled_mcp_does_not_pollute_history_or_save_stale_answer(self):
        for error in (McpError('failure'), KeyboardInterrupt()):
            with self.subTest(error=error), tempfile.TemporaryDirectory() as directory, WorkspaceWriter(directory) as writer:
                output, _, normal = self.chat(['/mcp broken', '/save stale.md', 'Hello', '/exit'],
                                              result=error, mcp_servers=[object()], file_reader=writer)
                self.assertFalse((Path(directory) / 'stale.md').exists())
                self.assertEqual(len(normal.call_args.args[2]), 2)
                self.assertIn('not saved', output)

    def test_pending_attachment_survives_mcp_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / 'note.md').write_text('CONTEXT')
            with WorkspaceReader(directory) as reader:
                _, runner, normal = self.chat(['/read note.md', '/mcp Read', 'Try again', '/exit'],
                                              result=McpError('failure'), mcp_servers=[object()], file_reader=reader)
        self.assertIn('CONTEXT', runner.call_args.args[1][-1]['content'])
        self.assertIn('CONTEXT', normal.call_args.args[2][-1]['content'])

    def test_input_policy_runs_before_mcp_and_clear_discards_observations(self):
        policy = Guardrails({'blocked_input': ['forbidden']})
        _, runner, _ = self.chat(['/mcp forbidden', '/exit'], mcp_servers=[object()], guardrails=policy)
        runner.assert_not_called()
        _, _, normal = self.chat(['/mcp clock', '/clear', 'Hello', '/exit'], mcp_servers=[object()])
        self.assertEqual(len(normal.call_args.args[2]), 2)

    def test_invalid_config_fails_before_session_or_model_setup(self):
        with patch('sys.argv', ['chatbot.py', '--model', 'demo', '--mcp-config', '/missing/mcp.json']), \
             patch('chatbot.SessionStore') as sessions, patch('sys.stderr', io.StringIO()):
            self.assertEqual(chatbot.main(), 1)
        sessions.assert_not_called()


if __name__ == '__main__':
    unittest.main()
