from .store import SessionStore


def build_system_message(store: SessionStore, user_id: str = "default") -> str:
    """Create the profile-aware system prompt sent before Ollama."""
    profile = store.get_profile(user_id)

    return (
        "You are SensAI, a helpful AI assistant.\n"
        f"Respond in {profile['language']}.\n"
        f"Use a {profile['explanation_level']} explanation style.\n"
        f"Adopt this persona: {profile['preferred_persona']}.\n"
        "Use the conversation history for context."
    )