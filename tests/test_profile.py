from session.profile import build_system_message
from session.store import SessionStore


def test_missing_profile_returns_defaults(tmp_path):
    store = SessionStore(tmp_path / "profiles.db")

    profile = store.get_profile("default")

    assert profile["user_id"] == "default"
    assert profile["language"] == "English"
    assert profile["explanation_level"] == "detailed"
    assert profile["preferred_persona"] == "explainer"


def test_save_and_load_profile(tmp_path):
    store = SessionStore(tmp_path / "profiles.db")

    store.save_profile(
        "alex",
        language="French",
        explanation_level="concise",
        preferred_persona="coding tutor",
    )

    profile = store.get_profile("alex")

    assert profile["user_id"] == "alex"
    assert profile["language"] == "French"
    assert profile["explanation_level"] == "concise"
    assert profile["preferred_persona"] == "coding tutor"
    assert profile["updated_at"] is not None


def test_partial_profile_update_keeps_previous_values(tmp_path):
    store = SessionStore(tmp_path / "profiles.db")

    store.save_profile(
        "alex",
        language="English",
        explanation_level="detailed",
        preferred_persona="explainer",
    )

    store.save_profile("alex", language="Spanish")

    profile = store.get_profile("alex")

    assert profile["language"] == "Spanish"
    assert profile["explanation_level"] == "detailed"
    assert profile["preferred_persona"] == "explainer"


def test_profile_is_injected_into_system_message(tmp_path):
    store = SessionStore(tmp_path / "profiles.db")

    store.save_profile(
        "alex",
        language="Spanish",
        explanation_level="beginner-friendly",
        preferred_persona="patient programming teacher",
    )

    prompt = build_system_message(store, "alex")

    assert "SensAI" in prompt
    assert "Respond in Spanish." in prompt
    assert "beginner-friendly explanation style" in prompt
    assert "patient programming teacher" in prompt


def test_default_profile_is_injected_when_no_profile_is_saved(tmp_path):
    store = SessionStore(tmp_path / "profiles.db")

    prompt = build_system_message(store, "new-user")

    assert "Respond in English." in prompt
    assert "detailed explanation style" in prompt
    assert "persona: explainer" in prompt


def test_profiles_are_separate_per_user(tmp_path):
    store = SessionStore(tmp_path / "profiles.db")

    store.save_profile(
        "alex",
        language="English",
        explanation_level="detailed",
        preferred_persona="explainer",
    )
    store.save_profile(
        "other-user",
        language="French",
        explanation_level="short",
        preferred_persona="reviewer",
    )

    alex = store.get_profile("alex")
    other = store.get_profile("other-user")

    assert alex["language"] == "English"
    assert alex["preferred_persona"] == "explainer"

    assert other["language"] == "French"
    assert other["preferred_persona"] == "reviewer"