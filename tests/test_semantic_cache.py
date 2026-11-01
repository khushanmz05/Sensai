import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from core.chat import execute_turn_stream, semantic_cache_key
from retrieval.semantic_cache import SemanticCache


class SemanticCacheTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.temp_dir.name) / "cache.sqlite3")
        self.cache = SemanticCache(
            db_path=self.db_path,
            threshold=0.90,
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    @patch.object(SemanticCache, "_embed")
    def test_cache_hit_for_similar_query(self, mock_embed):
        mock_embed.side_effect = [
            [1.0, 0.0],
            [0.99, 0.01],
        ]

        self.cache.put(
            "How do I reset my password?",
            "Use the password reset page.",
            "support-context",
        )

        response, similarity, query_embedding = self.cache.get(
            "How can I reset my password?",
            "support-context",
        )

        self.assertEqual(response, "Use the password reset page.")
        self.assertGreaterEqual(similarity, 0.90)
        self.assertEqual(query_embedding, [0.99, 0.01])

    @patch.object(SemanticCache, "_embed")
    def test_cache_miss_for_dissimilar_query(self, mock_embed):
        mock_embed.side_effect = [
            [1.0, 0.0],
            [0.0, 1.0],
        ]

        self.cache.put(
            "How do I reset my password?",
            "Use the password reset page.",
            "support-context",
        )

        response, similarity, query_embedding = self.cache.get(
            "What are your opening hours?",
            "support-context",
        )

        self.assertIsNone(response)
        self.assertEqual(similarity, 0.0)
        self.assertEqual(query_embedding, [0.0, 1.0])

    @patch.object(SemanticCache, "_embed", return_value=[1.0, 0.0])
    def test_cache_is_isolated_by_context(self, mock_embed):
        self.cache.put(
            "How do I reset my password?",
            "Use the password reset page.",
            "context-a",
        )

        response, similarity, query_embedding = self.cache.get(
            "How do I reset my password?",
            "context-b",
        )

        self.assertIsNone(response)
        self.assertEqual(similarity, 0.0)
        self.assertEqual(query_embedding, [1.0, 0.0])

    @patch.object(SemanticCache, "_embed", return_value=[1.0, 0.0])
    def test_cache_persists_across_instances(self, mock_embed):
        self.cache.put(
            "How do I reset my password?",
            "Use the password reset page.",
            "support-context",
        )

        second_cache = SemanticCache(
            db_path=self.db_path,
            threshold=0.90,
        )

        response, similarity, query_embedding = second_cache.get(
            "How do I reset my password?",
            "support-context",
        )

        self.assertEqual(response, "Use the password reset page.")
        self.assertGreaterEqual(similarity, 0.90)
        self.assertEqual(query_embedding, [1.0, 0.0])


class SemanticCacheIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.messages = [
            {
                "role": "system",
                "content": "You are a support assistant.",
            },
            {
                "role": "user",
                "content": "How do I reset my password?",
            },
        ]

    def test_cache_hit_skips_model_call(self):
        fake_cache = Mock()
        fake_cache.get.return_value = (
            "Use the password reset page.",
            1.0,
            [1.0, 0.0],
        )

        with patch(
            "core.chat.get_semantic_cache",
            return_value=fake_cache,
        ):
            with patch("core.chat.stream_reply") as mock_stream:
                result = list(
                    execute_turn_stream(
                        host="http://localhost:11434",
                        model="test-model",
                        to_send=self.messages,
                        timeout=10,
                    )
                )

        self.assertEqual(
            result,
            ["Use the password reset page."],
        )
        mock_stream.assert_not_called()
        fake_cache.put.assert_not_called()

    @patch('core.chat.SemanticCache')
    def test_cache_uses_turn_host_for_embeddings(self, cache_class):
        import core.chat as chat

        old_cache = chat._semantic_cache
        chat._semantic_cache = None
        try:
            chat.get_semantic_cache('http://ollama.internal:11434')
        finally:
            chat._semantic_cache = old_cache

        self.assertEqual(
            cache_class.call_args.kwargs['base_url'],
            'http://ollama.internal:11434',
        )

    def test_cache_miss_calls_model_and_stores_response(self):
        fake_cache = Mock()
        fake_cache.get.return_value = (None, 0.0, [1.0, 0.0])

        with patch(
            "core.chat.get_semantic_cache",
            return_value=fake_cache,
        ):
            with patch(
                "core.chat.stream_reply",
                return_value=iter(["Use ", "the reset page."]),
            ) as mock_stream:
                result = list(
                    execute_turn_stream(
                        host="http://localhost:11434",
                        model="test-model",
                        to_send=self.messages,
                        timeout=10,
                    )
                )

        self.assertEqual(result, ["Use ", "the reset page."])
        mock_stream.assert_called_once()

        fake_cache.put.assert_called_once()
        stored_args = fake_cache.put.call_args.args

        self.assertEqual(
            stored_args[0],
            "How do I reset my password?",
        )
        self.assertEqual(
            stored_args[1],
            "Use the reset page.",
        )
        self.assertTrue(stored_args[2])

    def test_cache_key_changes_with_model_or_system_context(self):
        base = semantic_cache_key("http://localhost:11434", "model-a", self.messages)
        other_model = semantic_cache_key("http://localhost:11434", "model-b", self.messages)
        other_system = semantic_cache_key(
            "http://localhost:11434",
            "model-a",
            [
                {"role": "system", "content": "You are a different assistant."},
                self.messages[-1],
            ],
        )

        self.assertNotEqual(base, other_model)
        self.assertNotEqual(base, other_system)

    def test_stop_event_allows_cache_when_not_cancelled(self):
        fake_cache = Mock()
        fake_cache.get.return_value = ("Cached response.", 1.0, [1.0, 0.0])

        with patch("core.chat.get_semantic_cache", return_value=fake_cache), patch(
            "core.chat.stream_reply"
        ) as model:
            result = list(
                execute_turn_stream(
                    host="http://localhost:11434",
                    model="test-model",
                    to_send=self.messages,
                    timeout=10,
                    stop_event=threading.Event(),
                )
            )

        self.assertEqual(result, ["Cached response."])
        model.assert_not_called()

    def test_context_dependent_or_guarded_requests_bypass_cache(self):
        fake_cache = Mock()
        model = Mock(return_value=iter(["Fresh response."]))
        history = self.messages[:-1] + [
            {"role": "user", "content": "Earlier question"},
            {"role": "assistant", "content": "Earlier answer"},
            self.messages[-1],
        ]

        with patch("core.chat.get_semantic_cache", return_value=fake_cache):
            list(
                execute_turn_stream(
                    "http://localhost:11434", "test-model", history, 10,
                    stream_func=model,
                )
            )
            list(
                execute_turn_stream(
                    "http://localhost:11434", "test-model", self.messages, 10,
                    stream_func=model, cache_context_independent=False,
                )
            )

        fake_cache.get.assert_not_called()
        self.assertEqual(model.call_count, 2)

    def test_cache_error_falls_back_to_model_generation(self):
        fake_cache = Mock()
        fake_cache.get.side_effect = RuntimeError("embedding unavailable")
        model = Mock(return_value=iter(["Fresh response."]))

        with patch("core.chat.get_semantic_cache", return_value=fake_cache):
            result = list(
                execute_turn_stream(
                    "http://localhost:11434", "test-model", self.messages, 10,
                    stream_func=model,
                )
            )

        self.assertEqual(result, ["Fresh response."])
        model.assert_called_once()



if __name__ == "__main__":
    unittest.main()
