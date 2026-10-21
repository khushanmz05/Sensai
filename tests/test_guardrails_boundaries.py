"""Policy and audit boundaries; no model or web dependencies required."""
import json
import unittest
from guardrails import Guardrails, GuardrailError
from events.contract import EventStream, to_sse
from events.store import EventStore


class BoundaryTests(unittest.TestCase):
    def setUp(self):
        self.policy = Guardrails({'blocked_input': ['steal passwords'],
                                  'blocked_output': ['internal secret'],
                                  'redact': ['email', 'phone']})

    def test_nested_input_is_copied_and_filtered(self):
        original = {'items': [{'text': 'a@example.com +34 612 345 678'}]}
        result = self.policy.json_input(original)
        self.assertEqual(result['items'][0]['text'], '[EMAIL] [PHONE]')
        self.assertIn('a@example.com', json.dumps(original))

    def test_nested_blocked_input_and_personal_keys_are_refused(self):
        for value in [{'items': ['steal passwords']}, {'a@example.com': 'value'}]:
            with self.assertRaises(GuardrailError):
                self.policy.json_input(value)

    def test_schema_personal_data_is_refused_without_rewriting(self):
        schema = {'type': 'object', 'description': 'a@example.com'}
        with self.assertRaises(GuardrailError):
            self.policy.check_schema(schema)
        self.assertEqual(schema['description'], 'a@example.com')

    def test_schema_blocked_instruction_is_refused(self):
        with self.assertRaises(GuardrailError):
            self.policy.check_schema({'type': 'object', 'description': 'steal passwords'})

    def test_browser_and_sqlite_receive_same_filtered_event(self):
        store = EventStore()
        self.addCleanup(store.close)
        stream = EventStream(on_event=store.record_event, payload_filter=self.policy.event_payload)
        event = stream.emit('tool_result', sources=[{'source_file': 'a@example.com.txt'}])
        self.assertNotIn('a@example.com', to_sse(event))
        self.assertEqual(store.get_events(stream.run_id)[0], event)

    def test_rejected_event_never_calls_recorder_or_consumes_sequence(self):
        recorded = []
        stream = EventStream(on_event=recorded.append, payload_filter=self.policy.event_payload)
        with self.assertRaises(GuardrailError):
            stream.emit('text_delta', text='internal secret')
        self.assertEqual(recorded, [])
        self.assertEqual(stream.sequence, 0)
        self.assertEqual(stream.done('failed')['sequence'], 0)

    def test_metrics_remain_numeric_and_control_events_can_finish(self):
        stream = EventStream(payload_filter=self.policy.event_payload)
        metrics = stream.emit('metrics', tokens=12, latency_ms=2.4)
        self.assertEqual(metrics['payload']['tokens'], 12)
        event = stream.emit('error', message='a@example.com')
        self.assertEqual(event['payload']['message'], '[EMAIL]')
        self.assertEqual(stream.done('failed')['payload']['status'], 'failed')

    def test_disabled_policy_preserves_event_contract(self):
        self.assertEqual(EventStream().emit('text_delta', text='a@example.com')['payload']['text'], 'a@example.com')


if __name__ == '__main__':
    unittest.main()
