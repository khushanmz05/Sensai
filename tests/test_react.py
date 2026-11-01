"""Unit tests for the ReAct Loop (A1) engine."""
import time
import unittest
from core.react import ReActLoop


class ReActLoopTests(unittest.TestCase):

    def test_natural_stop_without_tools(self):
        """Test that the loop stops naturally when the model provides plain text."""
        loop = ReActLoop(max_steps=3)
        mock_llm = lambda messages: "This is a direct answer without any tools."

        result = loop.run("Hello", mock_llm)

        self.assertEqual(result["final_answer"], "This is a direct answer without any tools.")
        self.assertEqual(result["steps_taken"], 1)
        self.assertEqual(result["stopping_reason"], "natural_stop")

    def test_tool_call_execution(self):
        """Test that the loop successfully parses an action, executes a tool, and retrieves a final answer."""
        loop = ReActLoop(max_steps=3)
        loop.register_tool("multiply", lambda x, y: x * y)

        # Mock responses: Step 1 requests a tool call, Step 2 provides the final answer
        responses = [
            '```json\n{"action": "multiply", "action_input": {"x": 4, "b": 5}}\n```'.replace('"b": 5', '"y": 5'),
            '```json\n{"final_answer": "The product is 20"}\n```'
        ]
        mock_llm = lambda messages: responses.pop(0) if responses else "done"

        result = loop.run("Calculate 4 * 5", mock_llm)

        self.assertEqual(result["final_answer"], "The product is 20")
        self.assertEqual(result["stopping_reason"], "completed")
        self.assertEqual(result["steps_taken"], 2)

        # Verify trace captured tool observation
        observation_steps = [s for s in result["trace"] if "observation" in s]
        self.assertEqual(len(observation_steps), 1)
        self.assertEqual(observation_steps[0]["observation"], 20)

    def test_max_steps_limit(self):
        """Test that the loop terminates when max_steps is reached."""
        loop = ReActLoop(max_steps=2)
        # LLM keeps attempting actions that trigger steps
        mock_llm = lambda messages: '```json\n{"action": "unknown_tool", "action_input": {}}\n```'

        result = loop.run("Loop forever", mock_llm)

        self.assertEqual(result["steps_taken"], 2)
        self.assertEqual(result["stopping_reason"], "max_steps_reached")

    def test_time_limit_exceeded(self):
        """Test that the loop stops early if max_time_seconds is exceeded."""
        loop = ReActLoop(max_steps=5, max_time_seconds=0.01)

        def slow_llm(messages):
            time.sleep(0.03)  # Delay longer than the time limit
            return '```json\n{"action": "test", "action_input": {}}\n```'

        result = loop.run("Take your time", slow_llm)

        self.assertEqual(result["stopping_reason"], "time_limit_exceeded")


if __name__ == "__main__":
    unittest.main()