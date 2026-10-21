"""T3 CLI integration with fake search/model responses; requires app dependencies."""
import contextlib
import io
import unittest
from unittest.mock import Mock, patch

import chatbot
from guardrails import Guardrails
from web_search import SearchError, SearchPage, SearchResult


class SearchChatTests(unittest.TestCase):
    def setUp(self):
        self.page = SearchPage('query', (SearchResult('Python', 'https://python.org',
                                                    'Documentation'),), 'now')

    def chat(self, inputs, searcher=None, policy=None, **kwargs):
        output = io.StringIO()
        with patch('builtins.input', side_effect=inputs), \
                patch('chatbot.stream_reply', side_effect=lambda *a, **k: iter(['Answer'])) as model, \
                contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            chatbot.run_chat('test', 'Prompt', '', 1, searcher=searcher,
                             guardrails=policy, **kwargs)
        return output.getvalue(), model

    def test_disabled_search_does_not_call_model(self):
        text, model = self.chat(['/search test', '/exit'])
        self.assertIn('disabled', text)
        model.assert_not_called()

    def test_empty_query_does_not_search(self):
        searcher = Mock()
        text, model = self.chat(['/search', '/exit'], searcher)
        self.assertIn('Usage:', text)
        searcher.search.assert_not_called()
        model.assert_not_called()

    def test_sources_enter_context_and_next_turn_history(self):
        searcher = Mock()
        searcher.search.return_value = self.page
        text, model = self.chat(['/search Python', 'Explain further', '/exit'], searcher)
        searcher.search.assert_called_once_with('Python')
        self.assertIn('https://python.org', text)
        self.assertEqual(model.call_count, 2)
        for call in model.call_args_list:
            messages = call.args[2]
            self.assertIn('untrusted data', messages[0]['content'])
            self.assertIn('https://python.org', str(messages[1:]))

    def test_provider_failure_does_not_generate_and_chat_recovers(self):
        searcher = Mock()
        searcher.search.side_effect = SearchError('Search unavailable')
        text, model = self.chat(['/search test', 'Hello', '/exit'], searcher)
        self.assertIn('Search unavailable', text)
        model.assert_called_once()
        searcher.search.assert_called_once_with('test')
        messages = model.call_args.args[2]
        # The permanent system rule mentions web evidence even when no search
        # succeeded. Check actual conversation turns, not the instruction text.
        conversation = [message for message in messages if message['role'] != 'system']
        self.assertEqual(conversation, [{'role': 'user', 'content': 'Hello'}])

    def test_no_results_does_not_generate(self):
        searcher = Mock()
        searcher.search.return_value = SearchPage('q', (), 'now')
        text, model = self.chat(['/search test', '/exit'], searcher)
        self.assertIn('no results', text)
        model.assert_not_called()

    def test_guardrails_run_before_external_query(self):
        searcher = Mock()
        searcher.search.return_value = self.page
        policy = Guardrails({'blocked_input': ['forbidden'], 'redact': ['email']})
        self.chat(['/search forbidden', '/search a@example.com', '/exit'], searcher, policy)
        searcher.search.assert_called_once_with('[EMAIL]')

    def test_search_and_local_retrieval_both_reach_model(self):
        searcher = Mock()
        searcher.search.return_value = self.page
        with patch('chatbot.retrieve', return_value=[]), \
                patch('chatbot.format_context', return_value='LOCAL NOTE'):
            _, model = self.chat(['/search compare Python', '/exit'], searcher, store=object())
        self.assertIn('LOCAL NOTE', str(model.call_args))
        self.assertIn('https://python.org', str(model.call_args))

    def test_cancelled_search_does_not_generate(self):
        searcher = Mock()
        searcher.search.side_effect = KeyboardInterrupt()
        text, model = self.chat(['/search test', '/exit'], searcher)
        self.assertIn('Search cancelled', text)
        model.assert_not_called()
