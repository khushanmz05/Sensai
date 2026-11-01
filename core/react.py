import time
import json
from typing import Callable, Dict, Any, List, Optional, Tuple


class ReActLoop:
    def __init__(
            self,
            max_steps: int = 5,
            max_time_seconds: float = 30.0,
            tool_registry: Optional[Dict[str, Callable]] = None
    ):
        self.max_steps = max_steps
        self.max_time_seconds = max_time_seconds
        self.tool_registry = tool_registry or {}

    def register_tool(self, name: str, func: Callable):
        self.tool_registry[name] = func

    def run(
            self,
            initial_prompt: str,
            llm_generate_func: Callable[[List[Dict[str, str]]], str],
            system_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Executes a bounded ReAct loop:
        Thought -> Action -> Observation -> ... -> Final Answer.
        """
        start_time = time.time()
        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        messages.append({"role": "user", "content": initial_prompt})

        steps_taken = 0
        stopping_reason = "max_steps_reached"
        final_answer = None

        history_trace: List[Dict[str, Any]] = []

        while steps_taken < self.max_steps:
            # Check time limits
            elapsed = time.time() - start_time
            if elapsed > self.max_time_seconds:
                stopping_reason = "time_limit_exceeded"
                break

            steps_taken += 1

            # 1. LLM Generation step (Thought / Action plan)
            try:
                response_text = llm_generate_func(messages)
            except Exception as e:
                stopping_reason = f"llm_error: {str(e)}"
                break

            history_trace.append({"step": steps_taken, "model_output": response_text})

            # 2. Check for tool action calls (Expected JSON block or custom syntax)
            action, tool_name, tool_args = self._parse_action(response_text)

            if action == "final_answer":
                final_answer = tool_args  # payload or text
                stopping_reason = "completed"
                break
            elif action == "tool_call" and tool_name:
                if tool_name not in self.tool_registry:
                    observation = f"Error: Tool '{tool_name}' not found in registry."
                else:
                    try:
                        observation = self.tool_registry[tool_name](**tool_args)
                    except Exception as e:
                        observation = f"Error executing tool '{tool_name}': {str(e)}"

                # Append assistant thought/action and tool observation to loop messages
                messages.append({"role": "assistant", "content": response_text})
                messages.append({"role": "tool", "content": json.dumps(observation, ensure_ascii=False)})
                history_trace.append({"step": steps_taken, "observation": observation})
            else:
                # If the model didn't call a tool or finish, treat response as final text
                final_answer = response_text
                stopping_reason = "natural_stop"
                break

        total_time = time.time() - start_time
        return {
            "final_answer": final_answer,
            "steps_taken": steps_taken,
            "stopping_reason": stopping_reason,
            "total_time_seconds": round(total_time, 3),
            "trace": history_trace
        }

    def _parse_action(self, text: str) -> Tuple[str, Optional[str], Any]:
        """
        Parses model text to detect tool calls or final answers.
        Example convention: looks for JSON blocks or specific tags.
        """
        try:
            # Check if text contains a JSON action block
            if "```json" in text:
                json_str = text.split("```json")[1].split("```")[0].strip()
            elif "{" in text and "}" in text:
                # Attempt to extract json substring
                start = text.find("{")
                end = text.rfind("}") + 1
                json_str = text[start:end]
            else:
                return "text", None, text

            data = json.loads(json_str)
            if isinstance(data, dict):
                if "action" in data and "action_input" in data:
                    return "tool_call", data["action"], data["action_input"]
                if "final_answer" in data:
                    return "final_answer", None, data["final_answer"]
        except Exception:
            pass

        return "text", None, text