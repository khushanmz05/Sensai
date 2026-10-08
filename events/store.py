import json
import sqlite3
import threading
import time
from typing import Any, Dict, List, Optional

from events.contract import EventError, validate_event

AUTH_KEYS = {
    'password', 'secret', 'token', 'auth_token', 'access_token',
    'api_key', 'apikey', 'authorization', 'secret_key', 'private_key',
}


def is_sensitive(key: str) -> bool:
    k = key.lower()
    if k in ('tokens', 'token_count', 'total_tokens'):
        return False
    if k in AUTH_KEYS:
        return True
    return any(
        k.endswith(f'_{auth}') or k.startswith(f'{auth}_')
        for auth in ('token', 'key', 'secret', 'password')
    )


def sanitize_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    sanitized = {}
    for key, value in payload.items():
        if is_sensitive(key):
            sanitized[key] = '[REDACTED]'
        elif isinstance(value, dict):
            sanitized[key] = sanitize_payload(value)
        elif isinstance(value, list):
            sanitized[key] = [
                sanitize_payload(item) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            sanitized[key] = value
    return sanitized


class EventStore:
    def __init__(self, db_path: str = ':memory:'):
        self.db_path = db_path
        self._lock = threading.Lock()
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self):
        with self._lock, self.conn:
            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    sequence INTEGER NOT NULL,
                    type TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    UNIQUE(run_id, sequence)
                )
            ''')
            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    completed_at REAL,
                    tokens INTEGER DEFAULT 0,
                    latency_ms REAL DEFAULT 0,
                    error_message TEXT,
                    persona_id TEXT,
                    prompt_version TEXT,
                    session_id TEXT
                )
            ''')
            self.conn.execute('CREATE INDEX IF NOT EXISTS idx_events_run_id ON events (run_id)')
            self.conn.execute('CREATE INDEX IF NOT EXISTS idx_runs_created_at ON runs (created_at)')

    def record_run_metadata(
        self,
        run_id: str,
        persona_id: Optional[str] = None,
        prompt_version: Optional[str] = None,
        session_id: Optional[str] = None,
    ):
        with self._lock, self.conn:
            row = self.conn.execute('SELECT run_id FROM runs WHERE run_id = ?', (run_id,)).fetchone()
            if row:
                self.conn.execute('''
                    UPDATE runs
                    SET persona_id = COALESCE(?, persona_id),
                        prompt_version = COALESCE(?, prompt_version),
                        session_id = COALESCE(?, session_id)
                    WHERE run_id = ?
                ''', (persona_id, prompt_version, session_id, run_id))
            else:
                self.conn.execute('''
                    INSERT INTO runs (run_id, status, created_at, persona_id, prompt_version, session_id)
                    VALUES (?, 'running', ?, ?, ?, ?)
                ''', (run_id, time.time(), persona_id, prompt_version, session_id))

    def record_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        validated = validate_event(event)
        sanitized_payload = sanitize_payload(validated['payload'])
        payload_json = json.dumps(sanitized_payload, ensure_ascii=False)

        run_id = validated['run_id']
        sequence = validated['sequence']
        event_type = validated['type']
        timestamp = validated['timestamp']

        with self._lock, self.conn:
            self.conn.execute('''
                INSERT INTO events (run_id, sequence, type, payload_json, timestamp)
                VALUES (?, ?, ?, ?, ?)
            ''', (run_id, sequence, event_type, payload_json, timestamp))

            run_row = self.conn.execute('SELECT * FROM runs WHERE run_id = ?', (run_id,)).fetchone()
            if not run_row:
                self.conn.execute('''
                    INSERT INTO runs (run_id, status, created_at)
                    VALUES (?, 'running', ?)
                ''', (run_id, timestamp))

            if event_type == 'metrics':
                raw_tokens = validated['payload'].get('tokens', 0)
                raw_latency = validated['payload'].get('latency_ms', 0)
                tokens = int(raw_tokens) if isinstance(raw_tokens, (int, float)) else 0
                latency = float(raw_latency) if isinstance(raw_latency, (int, float)) else 0.0
                self.conn.execute('''
                    UPDATE runs
                    SET tokens = tokens + ?,
                        latency_ms = latency_ms + ?
                    WHERE run_id = ?
                ''', (tokens, latency, run_id))

            elif event_type == 'error':
                error_msg = str(sanitized_payload.get('message', ''))
                self.conn.execute('''
                    UPDATE runs
                    SET status = 'failed',
                        error_message = ?,
                        completed_at = ?
                    WHERE run_id = ?
                ''', (error_msg, timestamp, run_id))

            elif event_type == 'done':
                final_status = str(sanitized_payload.get('status', 'completed'))
                self.conn.execute('''
                    UPDATE runs
                    SET status = ?,
                        completed_at = ?
                    WHERE run_id = ?
                ''', (final_status, timestamp, run_id))

        return {**validated, 'payload': sanitized_payload}

    def get_events(self, run_id: str) -> List[Dict[str, Any]]:
        with self._lock:
            rows = self.conn.execute('''
                SELECT run_id, sequence, type, payload_json, timestamp
                FROM events
                WHERE run_id = ?
                ORDER BY sequence ASC
            ''', (run_id,)).fetchall()

        return [
            {
                'run_id': row['run_id'],
                'sequence': row['sequence'],
                'type': row['type'],
                'payload': json.loads(row['payload_json']),
                'timestamp': row['timestamp'],
            }
            for row in rows
        ]

    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            row = self.conn.execute('SELECT * FROM runs WHERE run_id = ?', (run_id,)).fetchone()
        return dict(row) if row else None

    def get_runs(self, limit: int = 50) -> List[Dict[str, Any]]:
        """List recent runs."""
        with self._lock:
            rows = self.conn.execute('''
                SELECT * FROM runs ORDER BY created_at DESC LIMIT ?
            ''', (limit,)).fetchall()
        return [dict(r) for r in rows]

    def get_metrics(self, since: Optional[float] = None) -> Dict[str, Any]:
        query = 'SELECT * FROM runs'
        params: List[Any] = []
        if since is not None:
            query += ' WHERE created_at >= ?'
            params.append(since)

        with self._lock:
            rows = self.conn.execute(query, params).fetchall()

        total_runs = len(rows)
        completed_runs = sum(1 for r in rows if r['status'] == 'completed')
        failed_runs = sum(1 for r in rows if r['status'] == 'failed')
        cancelled_runs = sum(1 for r in rows if r['status'] == 'cancelled')
        total_tokens = sum(r['tokens'] for r in rows)

        completed_latencies = [r['latency_ms'] for r in rows if r['status'] == 'completed']
        avg_latency = (
            sum(completed_latencies) / len(completed_latencies)
            if completed_latencies
            else 0.0
        )
        error_rate = (failed_runs / total_runs) if total_runs > 0 else 0.0

        return {
            'total_runs': total_runs,
            'completed_runs': completed_runs,
            'failed_runs': failed_runs,
            'cancelled_runs': cancelled_runs,
            'error_rate': round(error_rate, 4),
            'total_tokens': total_tokens,
            'avg_latency_ms': round(avg_latency, 2),
            'recent_runs': [dict(r) for r in rows[-10:]],
        }

    def close(self):
        with self._lock:
            self.conn.close()
