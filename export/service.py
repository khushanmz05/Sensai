import html
import json
import secrets
import sqlite3
import threading
import time
from typing import Any, Dict, List, Optional


class ExportError(Exception):
    """Base error for export and publication."""


def sanitize_snapshot_data(data: Dict[str, Any]) -> Dict[str, Any]:
    sanitized: Dict[str, Any] = {}
    allowed_keys = {'title', 'messages', 'sections', 'version', 'type', 'created_at', 'summary'}
    for k, v in data.items():
        if k in allowed_keys:
            if k == 'messages' and isinstance(v, list):
                sanitized['messages'] = [
                    {'role': m.get('role', 'user'), 'content': m.get('content', '')}
                    for m in v
                    if isinstance(m, dict) and m.get('role') in ('user', 'assistant')
                ]
            else:
                sanitized[k] = v
    return sanitized


class SnapshotStore:
    def __init__(self, db_path: str = ':memory:'):
        self.db_path = db_path
        self._lock = threading.Lock()
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self):
        with self._lock, self.conn:
            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS snapshots (
                    snapshot_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    snapshot_type TEXT NOT NULL,
                    data_json TEXT NOT NULL,
                    created_at REAL NOT NULL
                )
            ''')

    def publish_snapshot(
        self,
        title: str,
        snapshot_type: str,
        data: Dict[str, Any],
        custom_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        title = title.strip()
        if not title:
            raise ExportError('Title cannot be empty.')
        if snapshot_type not in ('conversation', 'artifact'):
            raise ExportError("snapshot_type must be 'conversation' or 'artifact'.")

        snapshot_id = (custom_id or secrets.token_urlsafe(10)).strip()
        cleaned_data = sanitize_snapshot_data(data)
        now = time.time()
        data_json = json.dumps(cleaned_data, ensure_ascii=False)

        try:
            with self._lock, self.conn:
                self.conn.execute('''
                    INSERT INTO snapshots (snapshot_id, title, snapshot_type, data_json, created_at)
                    VALUES (?, ?, ?, ?, ?)
                ''', (snapshot_id, title, snapshot_type, data_json, now))
        except sqlite3.IntegrityError:
            raise ExportError(f'Snapshot {snapshot_id!r} already exists.')

        return self.get_snapshot(snapshot_id)

    def get_snapshot(self, snapshot_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            row = self.conn.execute(
                'SELECT * FROM snapshots WHERE snapshot_id = ?', (snapshot_id,)
            ).fetchone()
            if not row:
                return None
            return {
                'snapshot_id': row['snapshot_id'],
                'title': row['title'],
                'type': row['snapshot_type'],
                'data': json.loads(row['data_json']),
                'created_at': row['created_at'],
            }

    def export_as_markdown(self, snapshot_id: str) -> str:
        snap = self.get_snapshot(snapshot_id)
        if not snap:
            raise ExportError(f'Snapshot {snapshot_id!r} not found.')

        data = snap['data']
        lines = [f"# {snap['title']}", '']

        if snap['type'] == 'conversation':
            for msg in data.get('messages', []):
                role = msg.get('role', 'user').capitalize()
                content = msg.get('content', '')
                lines.append(f"### {role}")
                lines.append(content.strip())
                lines.append('')
        elif snap['type'] == 'artifact':
            for sec_id, content in data.get('sections', {}).items():
                lines.append(f"## {sec_id}")
                lines.append(content.strip())
                lines.append('')

        return '\n'.join(lines).strip() + '\n'

    def export_as_json(self, snapshot_id: str) -> str:
        snap = self.get_snapshot(snapshot_id)
        if not snap:
            raise ExportError(f'Snapshot {snapshot_id!r} not found.')
        return json.dumps(snap, indent=2, ensure_ascii=False)

    def export_as_html(self, snapshot_id: str) -> str:
        snap = self.get_snapshot(snapshot_id)
        if not snap:
            raise ExportError(f'Snapshot {snapshot_id!r} not found.')

        title = html.escape(snap['title'])
        body_parts = [f"<h1>{title}</h1>"]

        if snap['type'] == 'conversation':
            for msg in snap['data'].get('messages', []):
                role = html.escape(msg.get('role', 'user').capitalize())
                content = html.escape(msg.get('content', '')).replace('\n', '<br>')
                cls = 'user' if role.lower() == 'user' else 'assistant'
                body_parts.append(
                    f'<div class="msg {cls}"><strong>{role}</strong><p>{content}</p></div>'
                )
        elif snap['type'] == 'artifact':
            for sec_id, content in snap['data'].get('sections', {}).items():
                s_title = html.escape(sec_id)
                s_content = html.escape(content).replace('\n', '<br>')
                body_parts.append(f'<div class="section"><h2>{s_title}</h2><p>{s_content}</p></div>')

        rendered_body = '\n'.join(body_parts)
        return f'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{title}</title>
  <style>
    body {{ font-family: system-ui, sans-serif; max-width: 800px; margin: 2rem auto; padding: 0 1rem; color: #333; }}
    h1 {{ border-bottom: 2px solid #333; padding-bottom: .5rem; }}
    .msg {{ margin: 1rem 0; padding: 1rem; border-radius: 6px; background: #f8f9fa; }}
    .msg.user {{ background: #e3f2fd; }}
    .msg.assistant {{ background: #f5f5f5; border-left: 4px solid #0066cc; }}
    .section {{ margin-top: 1.5rem; }}
    @media print {{
      body {{ max-width: 100%; margin: 0; }}
      .msg {{ page-break-inside: avoid; }}
    }}
  </style>
</head>
<body>
  {rendered_body}
</body>
</html>
'''

    def close(self):
        with self._lock:
            self.conn.close()

