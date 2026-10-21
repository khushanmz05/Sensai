"""EV2 policy, streaming boundaries and CLI regression tests; no Ollama needed."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

import chatbot
from core.chat import ChatError, execute_turn_stream
from guardrails import GuardrailError, Guardrails
from session import SessionStore
from structured.output import JsonOutput


class GuardrailTests(unittest.TestCase):
    def setUp(self):
        self.policy = Guardrails({
            'blocked_input': ['steal passwords'],
            'blocked_output': ['internal secret'],
            'redact': ['email', 'phone'],
        })

    def generate(self, chunks, **kwargs):
        return execute_turn_stream('http://unused', 'test',
                                   [{'role': 'user', 'content': 'Hello'}], 1,
                                   stream_func=lambda *a, **k: iter(chunks),
                                   guardrails=self.policy, **kwargs)


    def test_pii_split_across_chunks_is_never_released(self):
        self.assertEqual(list(self.generate(['Contact a@', 'example.com'])),
                         ['Contact [EMAIL]'])

    def test_blocked_output_emits_no_prefix(self):
        stream = self.generate(['Helpful prefix ', 'internal ', 'secret'])
        with self.assertRaises(GuardrailError):
            next(stream)

    def test_input_block_does_not_call_model(self):
        model = Mock()
        with self.assertRaises(GuardrailError):
            list(execute_turn_stream('', '', [{'role': 'user', 'content': 'steal passwords'}],
                                     1, stream_func=model, guardrails=self.policy))
        model.assert_not_called()

    def test_bounded_output_closes_generator(self):
        self.policy.max_output_chars = 4
        closed = []
        def source(*args, **kwargs):
            try:
                yield '12345'
                self.fail('Must stop reading after reaching the limit')
            finally:
                closed.append(True)
        with self.assertRaises(GuardrailError):
            list(execute_turn_stream('', '', [], 1, stream_func=source,
                                     guardrails=self.policy))
        self.assertEqual(closed, [True])

    def test_error_does_not_release_partial_output_or_remote_text(self):
        def source(*args, **kwargs):
            yield 'a@example.com'
            raise ChatError('failed for a@example.com')
        stream = execute_turn_stream('', '', [], 1, stream_func=source,
                                     guardrails=self.policy)
        with self.assertRaises(ChatError) as error:
            next(stream)
        self.assertNotIn('a@example.com', str(error.exception))

    def test_cancelled_buffer_is_not_released(self):
        stop = threading.Event()
        stop.set()
        with self.assertRaises(GuardrailError):
            next(self.generate(['partial'], stop_event=stop))

    def test_json_escaped_pii_is_redacted_after_parsing(self):
        schema = JsonOutput({'type': 'object', 'properties': {'email': {'type': 'string'}}})
        text = ''.join(self.generate(['{"email":"a\\u0040example.com"}'], json_output=schema))
        self.assertEqual(json.loads(text), {'email': '[EMAIL]'})

    def test_json_schema_conflict_is_refused(self):
        schema = JsonOutput({'type': 'object', 'properties': {
            'email': {'const': 'a@example.com'}}, 'required': ['email']})
        with self.assertRaises(GuardrailError):
            next(self.generate(['{"email":"a@example.com"}'], json_output=schema))

    def test_json_keys_with_pii_are_refused(self):
        with self.assertRaises(GuardrailError):
            next(self.generate(['{"a@example.com":1}'],
                               json_output=JsonOutput({'type': 'object'})))

    def test_disabled_policy_keeps_streaming(self):
        stream = execute_turn_stream('', '', [], 1,
                                     stream_func=lambda *a: iter(['a@', 'example.com']))
        self.assertEqual(list(stream), ['a@', 'example.com'])

    def test_cli_blocks_before_retrieval_then_recovers(self):
        output = io.StringIO()
        with patch('builtins.input', side_effect=['steal passwords', 'Hello', '/exit']), \
                patch('chatbot.retrieve', return_value=[]) as retrieve, \
                patch('chatbot.stream_reply', return_value=iter(['OK'])) as model, \
                contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            chatbot.run_chat('test', 'Prompt', '', 1, store=object(), guardrails=self.policy)
        model.assert_called_once()
        retrieve.assert_called_once()
        self.assertEqual(retrieve.call_args.args[0], 'Hello')
        self.assertIn('Input blocked', output.getvalue())
        self.assertIn('OK', output.getvalue())

    def test_cli_sanitizes_model_request_history_and_persistence(self):
        output = io.StringIO()
        with tempfile.TemporaryDirectory() as folder:
            store = SessionStore(Path(folder) / 'sessions.db')
            with patch('builtins.input', side_effect=['Email a@example.com', '/exit']), \
                    patch('chatbot.stream_reply', return_value=iter(['Call +34 612 345 678'])) as model, \
                    contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
                chatbot.run_chat('test', 'Prompt', '', 1, session_store=store,
                                 guardrails=self.policy)
            messages = store.get_messages(store.get_active_session('default')['id'])
            self.assertEqual([m['content'] for m in messages],
                             ['Email [EMAIL]', 'Call [PHONE]'])
            self.assertNotIn('a@example.com', str(model.call_args))
            self.assertNotIn('+34', output.getvalue())


if __name__ == '__main__':
    unittest.main()
