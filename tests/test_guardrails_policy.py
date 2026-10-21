"""Dependency-free tests for EV2 policy configuration and matching."""
from pathlib import Path
import tempfile
import unittest
from guardrails import GuardrailError, Guardrails


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.policy = Guardrails({
            'blocked_input': ['steal passwords'],
            'blocked_output': ['internal secret'],
            'redact': ['email', 'phone'],
        })


    def test_invalid_configuration_is_rejected(self):
        for config in ([], {'typo': True}, {'redact': ['name']},
                       {'redact': 'email'}, {'blocked_input': [' ']},
                       {'max_output_chars': True}, {'max_output_chars': 0}):
            with self.subTest(config=config), self.assertRaises(GuardrailError):
                Guardrails(config)


    def test_configuration_file_errors_are_safe(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'policy.json'
            path.write_text('{invalid secret@example.com', encoding='utf-8')
            with self.assertRaises(GuardrailError) as error:
                Guardrails.from_file(path)
            self.assertNotIn('secret@example.com', str(error.exception))


    def test_blocking_normalizes_case_whitespace_and_width(self):
        for text in ('STEAL   passwords', 'ｓｔｅａｌ passwords'):
            with self.assertRaises(GuardrailError):
                self.policy.check_input(text)
        self.assertEqual(self.policy.check_input('Explain password hashing'),
                         'Explain password hashing')


    def test_redacts_supported_pii_but_not_dates(self):
        self.assertEqual(self.policy.redact('a@example.com +34 612 345 678, 2026-10-21'),
                         '[EMAIL] [PHONE], 2026-10-21')


    def test_messages_are_copied(self):
        original = [{'role': 'user', 'content': 'a@example.com'}]
        self.assertEqual(self.policy.messages(original)[0]['content'], '[EMAIL]')
        self.assertEqual(original[0]['content'], 'a@example.com')


