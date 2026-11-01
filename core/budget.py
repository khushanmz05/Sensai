"""Token budgeting, estimation, and conversation compression utilities (M2)."""
from typing import List, Dict, Any

def estimate_tokens(text: str) -> int:
    """Estimates token count using a lightweight heuristic (approx. 4 chars per token)."""
    if not text:
        return 0
    return max(1, len(text) // 4)

def calculate_history_tokens(messages: List[Dict[str, Any]]) -> int:
    """Calculates total estimated tokens for a list of message dictionaries."""
    total = 0
    for msg in messages:
        total += estimate_tokens(msg.get("content", ""))
        total += 4  # overhead per message role/formatting
    return total

def compress_history(
    messages: List[Dict[str, Any]],
    max_tokens: int = 4096,
    preserve_recent_count: int = 4,
    pinned_keywords: List[str] = None
) -> List[Dict[str, Any]]:
    """Summarizes older messages when near the limit while preserving recent turns and critical facts."""
    pinned_keywords = pinned_keywords or []

    current_tokens = calculate_history_tokens(messages)
    if current_tokens <= max_tokens or len(messages) <= preserve_recent_count:
        return messages

    older_messages = messages[:-preserve_recent_count]
    recent_messages = messages[-preserve_recent_count:]

    preserved_older = []
    to_summarize = []

    for msg in older_messages:
        content = msg.get("content", "")
        if any(keyword.lower() in content.lower() for keyword in pinned_keywords):
            preserved_older.append(msg)
        else:
            to_summarize.append(msg)

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

    return [summary_message] + preserved_older + recent_messages