import json
from typing import List, Dict, Any, Tuple

class TokenBudgetManager:
    """Manages token budgeting, usage estimation, and conversation compression."""

def __init__(self, max_token_limit: int = 4096, warning_threshold: float = 0.8):
    self.max_token_limit = max_token_limit
    self.warning_threshold = warning_threshold

def estimate_tokens(self, text: str) -> int:
    """Estimates token count using a lightweight heuristic (approx. 4 chars per token in English)."""
    if not text:
        return 0
    return max(1, len(text) // 4)

def calculate_history_tokens(self, messages: List[Dict[str, Any]]) -> int:
    """Calculates total estimated tokens for a list of message dictionaries."""
    total = 0
    for msg in messages:
        total += self. estimate_tokens(msg.get("content", ""))
        total += 4  # overhead per message role/formatting
    return total

def check_budget(self, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Checks current token consumption against limits and thresholds."""
    current_tokens = self.calculate_history_tokens(messages)
    usage_ratio = current_tokens / self.max_token_limit
    return {
        "current_tokens": current_tokens,
        "max_limit": self.max_token_limit,
        "usage_ratio": usage_ratio,
        "is_near_limit": usage_ratio >= self.warning_threshold,
        "tokens_remaining": max(0, self.max_token_limit - current_tokens)
    }

def compress_history(
    self,
    messages: List[Dict[str, Any]],
    preserve_recent_count: int = 4,
    pinned_keywords: List[str] = None
) -> List[Dict[str, Any]]:
    """
    Summarizes older messages when near the limit while preserving recent turns
    and critical/pinned facts.
  """
    pinned_keywords = pinned_keywords or []
    budget_status = self.check_budget(messages)

    if not budget_status["is_near_limit"] or len(messages) <= preserve_recent_count:
        return messages

    # Separate older messages from recent protected ones
    older_messages = messages[:-preserve_recent_count]
    recent_messages = messages[-preserve_recent_count:]

    # Extract or identify critical facts/pinned messages to preserve
    preserved_older = []
    to_summarize = []

    for msg in older_messages:
        content = msg.get("content", "")
        if any(keyword.lower() in content.lower() for keyword in pinned_keywords):
            preserved_older.append(msg)
        else:
            to_summarize.append(msg)

    # Build abstract summary of non-preserved older messages
    summary_text = "[Conversation Summary of Older Turns]:\n"
    for msg in to_summarize:
        role = msg.get("role", "user")
        snippet = msg.get("content", "")[:100]
        summary_text += f"- {role}: {snippet}...\n"

    summary_message = {
        "role": "system",
        "content": summary_text,
        "status": "completed"
    }

    # Reconstruct compressed message history
    compressed_history = [summary_message] + preserved_older + recent_messages
    return compressed_history
