"""Persist validated structured deliverables separately from the chat transcript."""
from contextlib import closing
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sqlite3
import uuid

from structured.output import JsonOutput

DEFAULT_DB = Path(os.getenv('SENSAI_STRUCTURED_DB') or
                  Path(__file__).resolve().parent.parent / 'sensai_structured.db')


class ResultError(ValueError):
    pass


class ResultStore:
    def __init__(self, path=DEFAULT_DB):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path)) as conn, conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS structured_results (
                id TEXT PRIMARY KEY, kind TEXT NOT NULL, model TEXT NOT NULL,
                created_at TEXT NOT NULL, schema_json TEXT NOT NULL,
                data_json TEXT NOT NULL, completed_json TEXT NOT NULL)''')

    def save(self, kind, schema, data, model):
        if kind not in ('tasks', 'plan', 'custom'):
            raise ResultError('Unknown structured workflow.')
        raw = json.dumps(data, ensure_ascii=False, allow_nan=False)
        JsonOutput(schema).parse(raw)  # Defense at the persistence boundary.
        if kind in ('tasks', 'plan'):
            expected = JsonOutput.from_file(Path(__file__).resolve().parent.parent / 'schemas' / (kind + '.json'))
            expected.parse(raw)  # A caller cannot weaken the built-in consumer contract.
        count = len(data['tasks']) if kind == 'tasks' else len(data['steps']) if kind == 'plan' else 0
        result_id = uuid.uuid4().hex
        created = datetime.now(timezone.utc).isoformat()
        with closing(sqlite3.connect(self.path)) as conn, conn:
            conn.execute('INSERT INTO structured_results VALUES (?, ?, ?, ?, ?, ?, ?)',
                         (result_id, kind, model, created, json.dumps(schema), raw,
                          json.dumps([False] * count)))
        return self.get(result_id)

    def get(self, result_id):
        with closing(sqlite3.connect(self.path)) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute('SELECT * FROM structured_results WHERE id=?', (result_id,)).fetchone()
        if row is None:
            raise ResultError('Structured result not found.')
        return {'id': row['id'], 'kind': row['kind'], 'model': row['model'],
                'created_at': row['created_at'], 'schema': json.loads(row['schema_json']),
                'data': json.loads(row['data_json']), 'completed': json.loads(row['completed_json'])}

    def list(self):
        with closing(sqlite3.connect(self.path)) as conn:
            conn.row_factory = sqlite3.Row
            return [dict(row) for row in conn.execute(
                'SELECT id, kind, model, created_at FROM structured_results ORDER BY created_at DESC LIMIT 100')]

    def set_completed(self, result_id, index, completed):
        if type(index) is not int or type(completed) is not bool:
            raise ResultError('Completion requires an integer index and boolean value.')
        with closing(sqlite3.connect(self.path)) as conn, conn:
            conn.execute('BEGIN IMMEDIATE')
            row = conn.execute('SELECT completed_json FROM structured_results WHERE id=?', (result_id,)).fetchone()
            if row is None:
                raise ResultError('Structured result not found.')
            states = json.loads(row[0])
            if not 0 <= index < len(states):
                raise ResultError('Checklist item does not exist.')
            states[index] = completed
            conn.execute('UPDATE structured_results SET completed_json=? WHERE id=?',
                         (json.dumps(states), result_id))
        return self.get(result_id)

    def export(self, result_id):
        result = self.get(result_id)
        raw = json.dumps(result['data'], ensure_ascii=False, indent=2, allow_nan=False)
        JsonOutput(result['schema']).parse(raw)
        return raw
