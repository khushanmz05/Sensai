"""End-to-end workflow contracts with a deterministic model transport."""
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import Mock

from core.chat import ChatError
from structured.output import JsonOutput, StructuredOutputError
from structured.results import ResultError, ResultStore
from structured.workflow import generate_result, render_result, select_output


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / 'results.db'
        self.store = ResultStore(self.path)
        self.data = {'tasks': [{'title': 'Fix login', 'priority': 'high'}]}

    def generate(self, data=None, **kwargs):
        stream = kwargs.pop('stream_func', Mock(return_value=iter([json.dumps(data or self.data)])))
        return generate_result('Fix login urgently', kwargs.pop('kind', 'tasks'), 'test-model',
                               'http://localhost:11434', 10, self.store,
                               stream_func=stream, **kwargs)

    def test_generate_reopen_complete_and_export(self):
        stream = Mock(return_value=iter([json.dumps(self.data)]))
        result = self.generate(stream_func=stream)
        self.assertEqual(stream.call_args.kwargs['schema'], select_output('tasks').schema)
        reopened = ResultStore(self.path)
        self.assertEqual(reopened.get(result['id'])['data'], self.data)
        reopened.set_completed(result['id'], 0, True)
        self.assertEqual(self.store.get(result['id'])['completed'], [True])
        self.assertIn('[x] [high] Fix login', render_result(reopened.get(result['id'])))
        self.assertEqual(json.loads(reopened.export(result['id'])), self.data)
        self.assertEqual(len(reopened.list()), 1)

    def test_plan_and_empty_tasks_have_consumable_checklists(self):
        result = self.generate({'goal': 'Learn', 'steps': ['Read']}, kind='plan')
        self.assertIn('1. [ ] Read', render_result(result))
        empty = self.generate({'tasks': []})
        self.assertEqual(empty['completed'], [])
        self.assertIn('No actionable tasks', render_result(empty))

    def test_custom_schema_is_enforced_and_exported(self):
        schema = {'type': 'object', 'properties': {'count': {'type': 'integer'}},
                  'required': ['count'], 'additionalProperties': False}
        result = self.generate({'count': 3}, kind='custom', schema=schema)
        self.assertEqual(JsonOutput(schema).parse(self.store.export(result['id'])), {'count': 3})
        with self.assertRaises(ResultError):
            self.store.set_completed(result['id'], 0, True)

    def test_invalid_response_repaired_before_single_save(self):
        stream = Mock(side_effect=[iter(['{"tasks":[{"title":"Fix","priority":"urgent"}]}']),
                                   iter([json.dumps(self.data)])])
        self.generate(stream_func=stream)
        self.assertEqual(stream.call_count, 2)
        self.assertEqual(len(self.store.list()), 1)

    def test_exhaustion_and_transport_failure_do_not_save(self):
        for stream, error in [(Mock(side_effect=lambda *a, **k: iter(['{}'])), StructuredOutputError),
                              (Mock(side_effect=ChatError('offline')), ChatError)]:
            with self.subTest(error=error), self.assertRaises(error):
                self.generate(stream_func=stream)
            self.assertEqual(self.store.list(), [])

    def test_invalid_schema_never_calls_model(self):
        stream = Mock()
        with self.assertRaises(StructuredOutputError):
            self.generate(kind='custom', schema={'type': 'array'}, stream_func=stream)
        stream.assert_not_called()

    def test_cancelled_generation_does_not_save(self):
        stop = threading.Event()
        def stream(*args, **kwargs):
            yield json.dumps(self.data)
            stop.set()
        with self.assertRaises(ChatError):
            self.generate(stream_func=stream, stop_event=stop)
        self.assertEqual(self.store.list(), [])

    def test_consumer_cannot_weaken_task_contract(self):
        with self.assertRaises(StructuredOutputError):
            self.store.save('tasks', {'type': 'object'}, {'tasks': [{}]}, 'test')
        self.assertEqual(self.store.list(), [])

    def test_invalid_completion_preserves_progress(self):
        result = self.generate()
        for index, completed in [(-1, True), (1, True), (True, True), (0, 'true')]:
            with self.subTest(index=index, completed=completed), self.assertRaises(ResultError):
                self.store.set_completed(result['id'], index, completed)
        self.assertEqual(self.store.get(result['id'])['completed'], [False])

    def test_output_limit_closes_generator_without_saving(self):
        closed = []
        def stream(*args):
            try:
                yield 'x' * 101
            finally:
                closed.append(True)
        with self.assertRaisesRegex(StructuredOutputError, 'size limit'):
            select_output('tasks').generate([], stream, max_chars=100)
        self.assertEqual(closed, [True])

    def test_email_format_checked_at_consumer_boundary(self):
        output = JsonOutput({'type': 'object', 'properties': {'email': {'type': 'string', 'format': 'email'}}})
        with self.assertRaises(StructuredOutputError):
            output.parse('{"email":"invalid"}')
        self.assertEqual(output.parse('{"email":"a@example.com"}'), {'email': 'a@example.com'})


if __name__ == '__main__':
    unittest.main()
