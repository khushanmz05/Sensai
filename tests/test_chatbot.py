"""HTTP contract tests with a local fake Ollama, no model needed."""
import contextlib
import io
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading
import unittest
from unittest.mock import patch

import requests
import chatbot
from persona.registry import load_personas

PERSONA = {'id': 'tutor', 'name': 'Tutor', 'tone': 'calm', 'role': 'teacher', 'scope': 'basics'}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        data = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        self.server.payloads.append(data)
        status, chunks = self.server.replies.pop(0)
        self.send_response(status)
        self.send_header('Content-Type', 'application/x-ndjson')
        self.end_headers()
        for chunk in chunks:
            self.wfile.write((json.dumps(chunk, ensure_ascii=False) + '\n').encode())
            self.wfile.flush()


class ChatTests(unittest.TestCase):
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

    def reply(self, text='Hello'):
        self.server.replies.append((200, [
            {'message': {'content': text}, 'done': False},
            {'message': {'content': ''}, 'done': True},
        ]))

    def run_cli(self, inputs, personas=None, active=None):
        output = io.StringIO()
        with patch('builtins.input', side_effect=inputs), \
                contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            chatbot.run_chat('test-model', 'System prompt', self.url, 2, personas, active)
        return output.getvalue()

    def test_stream_delivers_separate_unicode_chunks(self):
        self.server.replies = [(200, [
            {'message': {'content': 'Привет '}, 'done': False},
            {'message': {'content': 'Mark'}, 'done': True},
        ])]
        chunks = list(chatbot.stream_reply(self.url, 'test', [], 2))
        self.assertEqual(chunks, ['Привет ', 'Mark'])
        self.assertTrue(self.server.payloads[0]['stream'])

    def test_history_includes_system_user_and_assistant(self):
        self.reply('Noted')
        self.reply('Mark')
        self.run_cli(['My name is Mark', 'What is my name?', '/exit'])
        self.assertEqual(self.server.payloads[1]['messages'], [
            {'role': 'system', 'content': 'System prompt'},
            {'role': 'user', 'content': 'My name is Mark'},
            {'role': 'assistant', 'content': 'Noted'},
            {'role': 'user', 'content': 'What is my name?'},
        ])

    def test_empty_input_makes_no_http_request(self):
        self.assertIn('Empty input', self.run_cli(['  ', '/exit']))
        self.assertEqual(self.server.payloads, [])

    def test_missing_model(self):
        self.server.replies = [(404, [{'error': 'model not found'}])]
        self.assertIn('ollama pull test-model', self.run_cli(['Hi', '/exit']))

    def test_partial_failure_does_not_change_history(self):
        self.server.replies = [(200, [{'message': {'content': 'partial'}}])]
        self.reply('Good')
        output = self.run_cli(['Failed question', 'Retry', '/exit'])
        self.assertIn('before completion', output)
        self.assertEqual(len(self.server.payloads[1]['messages']), 2)
        self.assertEqual(self.server.payloads[1]['messages'][-1]['content'], 'Retry')

    def test_error_inside_stream(self):
        self.server.replies = [(200, [{'error': 'model crashed'}])]
        self.assertIn('model crashed', self.run_cli(['Hi', '/exit']))

    def test_clear_retains_system_prompt(self):
        self.reply()
        self.reply()
        self.run_cli(['Hi', '/clear', 'Hello', '/exit'])
        self.assertEqual(len(self.server.payloads[1]['messages']), 2)
        self.assertEqual(self.server.payloads[1]['messages'][0]['role'], 'system')

    def test_connection_failure_is_explicit(self):
        with patch('chatbot.requests.post', side_effect=requests.ConnectionError):
            self.assertIn('ollama serve', self.run_cli(['Hi', '/exit']))

    def test_timeout_is_explicit(self):
        with patch('chatbot.requests.post', side_effect=requests.Timeout):
            self.assertIn('timed out', self.run_cli(['Hi', '/exit']))

    def test_interrupt_does_not_change_history(self):
        with patch('chatbot.stream_reply', side_effect=[KeyboardInterrupt, iter(['OK'])]) as call:
            self.assertIn('cancelled', self.run_cli(['Cancel me', 'Retry', '/exit']))
            self.assertEqual(len(call.call_args.args[2]), 2)

    def test_persona_switch_keeps_history(self):
        self.reply('Noted')
        self.reply('Mark')
        self.run_cli(['My name is Mark', '/persona tutor', 'What is my name?', '/exit'],
                     {'tutor': PERSONA})
        messages = self.server.payloads[1]['messages']
        self.assertTrue(messages[0]['content'].startswith('System prompt'))
        self.assertIn('Role: teacher', messages[0]['content'])
        self.assertEqual([m['content'] for m in messages[1:]],
                         ['My name is Mark', 'Noted', 'What is my name?'])

    def test_persona_list_and_unknown_make_no_http_request(self):
        output = self.run_cli(['/persona', '/persona nobody', '/exit'], {'tutor': PERSONA})
        self.assertIn('Personas: tutor', output)
        self.assertIn("Unknown persona 'nobody'", output)
        self.assertEqual(self.server.payloads, [])

    def test_start_persona_and_switch_between_real_personas(self):
        self.reply('Recursion is a function calling itself.')
        self.reply('What is the base case?')
        output = self.run_cli(['Explain recursion', '/persona reviewer', 'Check me', '/exit'],
                              load_personas(), 'explainer')
        self.assertIn('persona: explainer', output)
        first, second = (payload['messages'] for payload in self.server.payloads)
        self.assertIn('Persona: Explainer', first[0]['content'])
        self.assertIn('Persona: Reviewer', second[0]['content'])
        self.assertEqual(second[1:], first[1:] + [
            {'role': 'assistant', 'content': 'Recursion is a function calling itself.'},
            {'role': 'user', 'content': 'Check me'},
        ])

    def test_persona_list_marks_active(self):
        output = self.run_cli(['/persona', '/exit'], load_personas(), 'reviewer')
        self.assertIn('explainer, reviewer (active)', output)


if __name__ == '__main__':
    unittest.main()
