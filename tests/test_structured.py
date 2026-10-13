"""T5 validation boundaries; these tests do not use a real model."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from structured.output import JsonOutput, StructuredOutputError

ROOT = Path(__file__).resolve().parent.parent


class StructuredTests(unittest.TestCase):
    def setUp(self):
        self.output = JsonOutput.from_file(ROOT / 'schemas/plan.json')
        self.messages = [{'role': 'system', 'content': 'Tutor'},
                         {'role': 'user', 'content': 'Make a plan'}]
        self.valid = {'goal': 'Learn Python', 'steps': ['Read', 'Practice']}

    def test_valid_unicode_chunks_and_no_history_mutation(self):
        expected = {'goal': 'Учиться', 'steps': ['Практика']}
        raw = json.dumps(expected, ensure_ascii=False)
        generate = Mock(return_value=iter([raw[:10], raw[10:]]))
        original = deepcopy(self.messages)
        self.assertEqual(self.output.generate(self.messages, generate), expected)
        self.assertEqual(self.messages, original)
        sent, schema = generate.call_args.args
        self.assertIn('Return only a JSON object', sent[0]['content'])
        self.assertEqual(schema, self.output.schema)

    def test_invalid_syntax_can_be_repaired(self):
        generate = Mock(side_effect=[iter(['```json\n{}\n```']),
                                     iter([json.dumps(self.valid)])])
        self.assertEqual(self.output.generate(self.messages, generate), self.valid)
        self.assertEqual(generate.call_count, 2)
        correction = generate.call_args.args[0][-1]['content']
        self.assertIn('rejected', correction)
        self.assertNotIn('```', correction)

    def test_schema_violations_are_rejected(self):
        invalid = [{}, {'goal': 1, 'steps': ['Read']},
                   {'goal': 'Learn', 'steps': []},
                   {**self.valid, 'unexpected': True}]
        for value in invalid:
            with self.subTest(value=value):
                generate = Mock(side_effect=lambda *_: iter([json.dumps(value)]))
                with self.assertRaisesRegex(StructuredOutputError, 'after 2 attempt'):
                    self.output.generate(self.messages, generate)
                self.assertEqual(generate.call_count, 2)

    def test_strict_json_rejects_duplicates_nonfinite_and_trailing_text(self):
        output = JsonOutput({'type': 'object'})
        for raw in ['{"x":1,"x":2}', '{"x":NaN}', '{"x":Infinity}',
                    '{"x":1e9999}', '{} trailing', '']:
            with self.subTest(raw=raw), self.assertRaises(StructuredOutputError):
                output.generate([], lambda *_: iter([raw]), max_attempts=1)

    def test_transport_failure_and_cancellation_are_not_retried(self):
        for failure in [RuntimeError('offline'), KeyboardInterrupt()]:
            generate = Mock(side_effect=failure)
            with self.assertRaises(type(failure)):
                self.output.generate(self.messages, generate)
            generate.assert_called_once()

    def test_partial_transport_failure_is_not_returned(self):
        def interrupted(*_):
            yield json.dumps(self.valid)
            raise RuntimeError('stream incomplete')
        with self.assertRaisesRegex(RuntimeError, 'incomplete'):
            self.output.generate(self.messages, interrupted)

    def test_invalid_attempt_limit_makes_no_call(self):
        generate = Mock()
        for limit in [0, 6, True, 1.5]:
            with self.subTest(limit=limit), self.assertRaises(StructuredOutputError):
                self.output.generate(self.messages, generate, limit)
        generate.assert_not_called()

    def test_invalid_schema_and_external_reference_rejected(self):
        schemas = [[], {'type': 'array'}, {'type': 'object', 'required': 'x'},
                   {'type': 'object', '$ref': 'https://example.com/schema'},
                   {'type': 'object', '$schema': 'https://example.com/draft'},
                   {'type': 'object', 'properties': {'x': {'$ref': '#/$defs/x'}}}]
        for schema in schemas:
            with self.subTest(schema=schema), self.assertRaises(StructuredOutputError):
                JsonOutput(schema)

    def test_schema_file_errors_are_explained(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'schema.json'
            with self.assertRaises(StructuredOutputError):
                JsonOutput.from_file(path)
            path.write_text('{broken', encoding='utf-8')
            with self.assertRaises(StructuredOutputError):
                JsonOutput.from_file(path)

    def test_task_extraction_schema_checks_nested_priority(self):
        output = JsonOutput.from_file(ROOT / 'schemas/tasks.json')
        valid = {'tasks': [{'title': 'Fix login', 'priority': 'high'}]}
        self.assertEqual(output.generate([], lambda *_: [json.dumps(valid)]), valid)
        invalid = {'tasks': [{'title': 'Fix login', 'priority': 'urgent'}]}
        with self.assertRaises(StructuredOutputError):
            output.generate([], lambda *_: [json.dumps(invalid)], max_attempts=1)


if __name__ == '__main__':
    unittest.main()
