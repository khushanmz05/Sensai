import json
import os
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Iterable

DEFAULT_DB_PATH = Path(os.getenv("SENSAI_DB", "sensai.db"))

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    status TEXT NOT NULL DEFAULT 'active'
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'completed',
    created_at REAL NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS active_session (
    user_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS profiles (
    user_id TEXT PRIMARY KEY,
    language TEXT,
    explanation_level TEXT,
    preferred_persona TEXT,
    updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS session_personas (
    session_id TEXT PRIMARY KEY,
    persona_id TEXT NOT NULL,
    updated_at REAL NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_messages_session
ON messages(session_id, id);
"""


class DatabaseError(Exception):
    """Raised when the SQLite database is missing or corrupted."""


class SessionStore:
    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialise()

    def _connect(self) -> sqlite3.Connection:
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            return conn
        except sqlite3.DatabaseError as exc:
            raise DatabaseError(f"Cannot open database: {self.db_path}") from exc

    def _initialise(self) -> None:
        try:
            with self._connect() as conn:
                conn.executescript(SCHEMA)
        except sqlite3.DatabaseError as exc:
            raise DatabaseError(
                f"Database is corrupted or unreadable: {self.db_path}"
            ) from exc

    @contextmanager
    def _transaction(self):
        conn = self._connect()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def create_session(self, title: str = "New session", persona_id: str | None = None, session_id: str | None = None) -> dict:
        now = time.time()
        sid = session_id or str(uuid.uuid4())
        with self._transaction() as conn:
            conn.execute(
                "INSERT INTO sessions (id, title, created_at, updated_at) "
                "VALUES (?, ?, ?, ?)",
                (sid, title, now, now),
            )
            if persona_id and str(persona_id).strip():
                conn.execute(
                    "INSERT INTO session_personas (session_id, persona_id, updated_at) "
                    "VALUES (?, ?, ?)",
                    (sid, str(persona_id).strip(), now),
                )
        return self.get_session(sid)

    def get_session(self, session_id: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM sessions WHERE id = ?", (session_id,)
            ).fetchone()
            if not row:
                return None
            res = dict(row)
            p_row = conn.execute(
                "SELECT persona_id FROM session_personas WHERE session_id = ?", (session_id,)
            ).fetchone()
            res["persona_id"] = p_row["persona_id"] if p_row else None
            return res

    def list_sessions(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT s.*, sp.persona_id "
                "FROM sessions s "
                "LEFT JOIN session_personas sp ON s.id = sp.session_id "
                "ORDER BY s.updated_at DESC"
            ).fetchall()
        return [dict(row) for row in rows]

    def rename_session(self, session_id: str, title: str) -> dict | None:
        with self._transaction() as conn:
            conn.execute(
                "UPDATE sessions SET title = ?, updated_at = ? WHERE id = ?",
                (title, time.time(), session_id),
            )
        return self.get_session(session_id)

    def set_session_status(self, session_id: str, status: str) -> None:
        if status not in {"active", "completed", "failed", "cancelled"}:
            raise ValueError(f"Invalid session status: {status}")
        with self._transaction() as conn:
            conn.execute(
                "UPDATE sessions SET status = ?, updated_at = ? WHERE id = ?",
                (status, time.time(), session_id),
            )

    def set_session_persona(self, session_id: str, persona_id: str | None) -> None:
        now = time.time()
        with self._transaction() as conn:
            if not conn.execute("SELECT 1 FROM sessions WHERE id = ?", (session_id,)).fetchone():
                raise ValueError(f"Unknown session: {session_id}")
            if persona_id and str(persona_id).strip():
                conn.execute(
                    "INSERT INTO session_personas (session_id, persona_id, updated_at) "
                    "VALUES (?, ?, ?) "
                    "ON CONFLICT(session_id) DO UPDATE SET "
                    "persona_id = excluded.persona_id, updated_at = excluded.updated_at",
                    (session_id, str(persona_id).strip(), now),
                )
            else:
                conn.execute("DELETE FROM session_personas WHERE session_id = ?", (session_id,))
            conn.execute("UPDATE sessions SET updated_at = ? WHERE id = ?", (now, session_id))

    def get_session_persona(self, session_id: str) -> str | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT persona_id FROM session_personas WHERE session_id = ?", (session_id,)
            ).fetchone()
        return row["persona_id"] if row else None

    def clear_session_messages(self, session_id: str) -> None:
        now = time.time()
        with self._transaction() as conn:
            if not conn.execute("SELECT 1 FROM sessions WHERE id = ?", (session_id,)).fetchone():
                raise ValueError(f"Unknown session: {session_id}")
            conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
            conn.execute("UPDATE sessions SET updated_at = ? WHERE id = ?", (now, session_id))

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        status: str = "completed",
    ) -> dict:
        if role not in {"system", "user", "assistant", "tool"}:
            raise ValueError(f"Invalid message role: {role}")
        if status not in {"completed", "failed", "cancelled"}:
            raise ValueError(f"Invalid message status: {status}")

        now = time.time()
        with self._transaction() as conn:
            if not conn.execute(
                "SELECT 1 FROM sessions WHERE id = ?", (session_id,)
            ).fetchone():
                raise ValueError(f"Unknown session: {session_id}")

            conn.execute(
                "INSERT INTO messages "
                "(session_id, role, content, status, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (session_id, role, content, status, now),
            )
            conn.execute(
                "UPDATE sessions SET updated_at = ? WHERE id = ?",
                (now, session_id),
            )

        return {
            "session_id": session_id,
            "role": role,
            "content": content,
            "status": status,
            "created_at": now,
        }

    def get_messages(
        self,
        session_id: str,
        statuses: Iterable[str] = ("completed",),
    ) -> list[dict]:
        placeholders = ",".join("?" for _ in statuses)
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT id, session_id, role, content, status, created_at
                FROM messages
                WHERE session_id = ? AND status IN ({placeholders})
                ORDER BY id ASC
                """,
                (session_id, *statuses),
            ).fetchall()
        return [dict(row) for row in rows]

    def set_active_session(self, user_id: str, session_id: str) -> None:
        with self._transaction() as conn:
            if not conn.execute(
                "SELECT 1 FROM sessions WHERE id = ?", (session_id,)
            ).fetchone():
                raise ValueError(f"Unknown session: {session_id}")
            conn.execute(
                """
                INSERT INTO active_session (user_id, session_id)
                VALUES (?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    session_id = excluded.session_id
                """,
                (user_id, session_id),
            )

    def get_active_session(self, user_id: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT s.*
                FROM active_session a
                JOIN sessions s ON s.id = a.session_id
                WHERE a.user_id = ?
                """,
                (user_id,),
            ).fetchone()
        return dict(row) if row else None

    def save_profile(
        self,
        user_id: str,
        language: str | None = None,
        explanation_level: str | None = None,
        preferred_persona: str | None = None,
    ) -> dict:
        now = time.time()
        with self._transaction() as conn:
            conn.execute(
                """
                INSERT INTO profiles
                    (user_id, language, explanation_level,
                     preferred_persona, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    language = COALESCE(excluded.language, profiles.language),
                    explanation_level = COALESCE(
                        excluded.explanation_level,
                        profiles.explanation_level
                    ),
                    preferred_persona = COALESCE(
                        excluded.preferred_persona,
                        profiles.preferred_persona
                    ),
                    updated_at = excluded.updated_at
                """,
                (user_id, language, explanation_level, preferred_persona, now),
            )
        return self.get_profile(user_id)

    def get_profile(self, user_id: str) -> dict:
        defaults = {
            "user_id": user_id,
            "language": "English",
            "explanation_level": "detailed",
            "preferred_persona": "explainer",
            "updated_at": None,
        }
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM profiles WHERE user_id = ?", (user_id,)
            ).fetchone()
        return dict(row) if row else defaults

    def profile_to_context(self, user_id: str) -> str:
        profile = self.get_profile(user_id)
        return json.dumps(
            {
                "language": profile["language"],
                "explanation_level": profile["explanation_level"],
                "preferred_persona": profile["preferred_persona"],
            },
            ensure_ascii=False,
        )