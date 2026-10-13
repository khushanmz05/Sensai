import pytest

from session.store import DatabaseError, SessionStore


@pytest.fixture
def store(tmp_path):
    """Give every test a fresh temporary SQLite database."""
    return SessionStore(tmp_path / "test_sessions.db")


def test_create_and_load_session(store):
    session = store.create_session("My first session")

    loaded = store.get_session(session["id"])

    assert loaded is not None
    assert loaded["id"] == session["id"]
    assert loaded["title"] == "My first session"
    assert loaded["status"] == "active"
    assert loaded["created_at"] > 0
    assert loaded["updated_at"] > 0


def test_list_sessions_returns_most_recent_first(store):
    first = store.create_session("Older")
    second = store.create_session("Newer")

    sessions = store.list_sessions()

    assert len(sessions) == 2
    assert sessions[0]["id"] == second["id"]
    assert sessions[1]["id"] == first["id"]


def test_save_and_load_messages(store):
    session = store.create_session("Conversation")

    store.add_message(session["id"], "user", "Hello")
    store.add_message(session["id"], "assistant", "Hi! How can I help?")

    messages = store.get_messages(session["id"])

    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[0]["content"] == "Hello"
    assert messages[1]["role"] == "assistant"
    assert messages[1]["content"] == "Hi! How can I help?"


def test_message_order_is_preserved(store):
    session = store.create_session()

    store.add_message(session["id"], "user", "First message")
    store.add_message(session["id"], "assistant", "First answer")
    store.add_message(session["id"], "user", "Second message")
    store.add_message(session["id"], "assistant", "Second answer")

    messages = store.get_messages(session["id"])

    assert [message["content"] for message in messages] == [
        "First message",
        "First answer",
        "Second message",
        "Second answer",
    ]


def test_session_messages_are_isolated(store):
    first_session = store.create_session("First")
    second_session = store.create_session("Second")

    store.add_message(first_session["id"], "user", "Only first")
    store.add_message(second_session["id"], "user", "Only second")

    first_messages = store.get_messages(first_session["id"])
    second_messages = store.get_messages(second_session["id"])

    assert len(first_messages) == 1
    assert first_messages[0]["content"] == "Only first"

    assert len(second_messages) == 1
    assert second_messages[0]["content"] == "Only second"


def test_active_session_is_saved_and_restored(store):
    session = store.create_session("Active session")

    store.set_active_session("default", session["id"])

    active = store.get_active_session("default")

    assert active is not None
    assert active["id"] == session["id"]
    assert active["title"] == "Active session"


def test_restart_restores_active_session_and_history(tmp_path):
    db_path = tmp_path / "persistent.db"

    first_run = SessionStore(db_path)
    session = first_run.create_session("Saved chat")
    first_run.set_active_session("default", session["id"])
    first_run.add_message(session["id"], "user", "Hello before restart")
    first_run.add_message(session["id"], "assistant", "Hello after restart")

    # Simulates closing the CLI and launching it again.
    second_run = SessionStore(db_path)

    active = second_run.get_active_session("default")
    assert active is not None
    assert active["id"] == session["id"]

    messages = second_run.get_messages(active["id"])

    assert [message["content"] for message in messages] == [
        "Hello before restart",
        "Hello after restart",
    ]


def test_rename_session(store):
    session = store.create_session("Old title")

    updated = store.rename_session(session["id"], "New title")

    assert updated is not None
    assert updated["id"] == session["id"]
    assert updated["title"] == "New title"


def test_failed_and_cancelled_messages_are_not_returned_by_default(store):
    session = store.create_session()

    store.add_message(session["id"], "user", "Good question")
    store.add_message(session["id"], "assistant", "Good response")
    store.add_message(
        session["id"],
        "assistant",
        "Partial failed response",
        status="failed",
    )
    store.add_message(
        session["id"],
        "assistant",
        "Partial cancelled response",
        status="cancelled",
    )

    visible_messages = store.get_messages(session["id"])

    assert [message["content"] for message in visible_messages] == [
        "Good question",
        "Good response",
    ]


def test_failed_and_cancelled_messages_can_be_inspected(store):
    session = store.create_session()

    store.add_message(session["id"], "user", "Question")
    store.add_message(session["id"], "assistant", "Failed", status="failed")
    store.add_message(session["id"], "assistant", "Cancelled", status="cancelled")

    all_messages = store.get_messages(
        session["id"],
        statuses=("completed", "failed", "cancelled"),
    )

    assert [message["status"] for message in all_messages] == [
        "completed",
        "failed",
        "cancelled",
    ]


def test_unknown_session_cannot_receive_messages(store):
    with pytest.raises(ValueError, match="Unknown session"):
        store.add_message(
            "not-a-real-session-id",
            "user",
            "This must not be inserted",
        )


def test_invalid_role_is_rejected(store):
    session = store.create_session()

    with pytest.raises(ValueError, match="Invalid message role"):
        store.add_message(session["id"], "invalid-role", "Nope")


def test_invalid_message_status_is_rejected(store):
    session = store.create_session()

    with pytest.raises(ValueError, match="Invalid message status"):
        store.add_message(
            session["id"],
            "assistant",
            "Nope",
            status="in-progress",
        )


def test_missing_database_is_created(tmp_path):
    db_path = tmp_path / "new_folder" / "new_database.db"

    store = SessionStore(db_path)

    assert db_path.exists()
    assert store.list_sessions() == []


def test_corrupted_database_raises_a_clear_error(tmp_path):
    db_path = tmp_path / "corrupted.db"
    db_path.write_bytes(b"this is definitely not a SQLite database")

    with pytest.raises(DatabaseError, match="corrupted|unreadable|Cannot open"):
        SessionStore(db_path)