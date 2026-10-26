import json
import unittest
from unittest.mock import AsyncMock
from unittest.mock import Mock, patch

import requests

from evaluation.judge import EvaluationError, evaluate_response
from events.contract import EventStream


class EvaluationJudgeTests(unittest.TestCase):
    def setUp(self):
        self.arguments = {
            "question": "What is the refund period?",
            "answer": "The refund period is 30 days.",
            "context": "Refunds are accepted within 30 days of purchase.",
            "host": "http://localhost:11434",
            "model": "test-model",
        }

    @patch("evaluation.judge.requests.post")
    def test_evaluates_answer_and_returns_validated_scores(self, post):
        result = {
            "relevance": 0.98,
            "coherence": 0.95,
            "faithfulness": 1.0,
            "hallucination_detected": False,
            "unsupported_claims": [],
            "explanation": "The answer matches the provided evidence.",
        }
        response = Mock()
        response.json.return_value = {"message": {"content": json.dumps(result)}}
        response.raise_for_status.return_value = None
        post.return_value = response

        evaluation = evaluate_response(**self.arguments)

        self.assertEqual(evaluation["status"], "completed")
        self.assertEqual(evaluation["faithfulness"], 1.0)
        self.assertFalse(evaluation["hallucination_detected"])
        post.assert_called_once()
        self.assertEqual(post.call_args.args[0], "http://localhost:11434/api/chat")
        self.assertEqual(post.call_args.kwargs["json"]["model"], "test-model")
        self.assertFalse(post.call_args.kwargs["json"]["stream"])

    def test_skips_evaluation_without_source_context(self):
        args = dict(self.arguments, context="  ")
        result = evaluate_response(**args)
        self.assertEqual(result, {"status": "skipped", "reason": "no_source_context"})

    def test_skips_empty_answer(self):
        args = dict(self.arguments, answer="")
        result = evaluate_response(**args)
        self.assertEqual(result, {"status": "skipped", "reason": "empty_answer"})

    def test_skips_empty_question(self):
        args = dict(self.arguments, question=" ")
        result = evaluate_response(**args)
        self.assertEqual(result, {"status": "skipped", "reason": "empty_question"})

    @patch("evaluation.judge.requests.post")
    def test_rejects_scores_outside_range(self, post):
        result = {
            "relevance": 1.5,
            "coherence": 0.9,
            "faithfulness": 0.8,
            "hallucination_detected": True,
            "unsupported_claims": ["The answer adds an unsupported deadline."],
            "explanation": "Unsupported claim.",
        }
        response = Mock()
        response.json.return_value = {"message": {"content": json.dumps(result)}}
        response.raise_for_status.return_value = None
        post.return_value = response

        with self.assertRaises(EvaluationError):
            evaluate_response(**self.arguments)

    @patch("evaluation.judge.requests.post", side_effect=requests.ConnectionError("offline"))
    def test_reports_evaluator_dependency_failure(self, post):
        with self.assertRaises(EvaluationError):
            evaluate_response(**self.arguments)

    @patch("evaluation.judge.requests.post")
    def test_rejects_invalid_json_from_judge(self, post):
        response = Mock()
        response.json.return_value = {"message": {"content": "not json"}}
        response.raise_for_status.return_value = None
        post.return_value = response

        with self.assertRaises(EvaluationError):
            evaluate_response(**self.arguments)

    @patch("evaluation.judge.requests.post")
    def test_rejects_malformed_evaluator_response_shape(self, post):
        response = Mock()
        response.json.return_value = {"message": "not an object"}
        response.raise_for_status.return_value = None
        post.return_value = response

        with self.assertRaises(EvaluationError):
            evaluate_response(**self.arguments)


class EvaluationWebIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_completed_grounded_run_emits_evaluation_event(self):
        from web import app as web_app

        class FakeBridge:
            def __init__(self, worker_func):
                self.stop_event = Mock()

            async def iter_events(self):
                yield ("chunk", "The refund period is 30 days.")
                yield ("done", None)

            def cancel(self):
                return None

        stream = EventStream()
        run = {
            "stream": stream,
            "session_id": "ev1-test-session",
            "user_content": "What is the refund period?",
            "persona": None,
            "mode": "ollama",
            "retrieved_results": [{"source_file": "policy.md", "start_line": 1, "end_line": 2}],
            "formatted_context": "Refunds are accepted within 30 days of purchase.",
            "message": "What is the refund period?",
            "host": "http://localhost:11434",
            "model": "test-model",
            "messages": [],
            "timeout": 10,
            "guardrails": None,
            "schema": None,
            "cancelled": False,
        }
        evaluation = {
            "status": "completed",
            "relevance": 1.0,
            "coherence": 0.9,
            "faithfulness": 1.0,
            "hallucination_detected": False,
            "unsupported_claims": [],
            "explanation": "Supported by the retrieved evidence.",
        }

        with patch("web.app.RealtimeStreamBridge", FakeBridge), \
                patch("web.app.evaluate_response", return_value=evaluation) as judge, \
                patch("web.app.persist_turn"):
            events = [event async for event in web_app.generate_events(run)]

        evaluation_events = [event for event in events if "event: evaluation" in event]
        self.assertEqual(len(evaluation_events), 1)
        self.assertIn('"faithfulness": 1.0', evaluation_events[0])
        judge.assert_called_once_with(
            question="What is the refund period?",
            answer="The refund period is 30 days.",
            context="Refunds are accepted within 30 days of purchase.",
            host="http://localhost:11434",
            model="test-model",
        )

    async def test_context_free_run_emits_a_skipped_evaluation(self):
        from web import app as web_app

        stream = EventStream()
        run = {
            "stream": stream,
            "session_id": "ev1-skip-session",
            "user_content": "Hello",
            "persona": None,
            "mode": "stub",
            "retrieved_results": [],
            "formatted_context": "",
            "message": "Hello",
            "host": "http://localhost:11434",
            "model": "test-model",
            "messages": [],
            "timeout": 10,
            "guardrails": None,
            "schema": None,
            "cancelled": False,
        }

        with patch("web.app.persist_turn"):
            events = [event async for event in web_app.generate_events(run)]

        evaluation_events = [event for event in events if "event: evaluation" in event]
        self.assertEqual(len(evaluation_events), 1)
        self.assertIn('"status": "skipped"', evaluation_events[0])
        self.assertIn('"reason": "stub_mode"', evaluation_events[0])


if __name__ == "__main__":
    unittest.main()
