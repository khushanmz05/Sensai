import html
import json
import secrets
import sqlite3
import textwrap
import threading
import time
from typing import Any, Dict, List, Optional, Tuple


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


def _sanitize_pdf_text(text: str) -> str:
    replacements = {
        '\u2014': '--',
        '\u2013': '-',
        '\u201c': '"',
        '\u201d': '"',
        '\u2018': "'",
        '\u2019': "'",
        '\u2026': '...',
        '\u2022': '*',
        '\xa0': ' ',
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
    return text


def _escape_pdf_literal(text: str) -> str:
    cleaned = _sanitize_pdf_text(text)
    return cleaned.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')


def build_pdf_bytes(title: str, blocks: List[Tuple[str, str]]) -> bytes:
    pages_streams: List[bytes] = []
    current_stream: List[str] = []
    y = 780.0

    def start_page():
        nonlocal y
        current_stream.clear()
        current_stream.append('BT')
        y = 780.0

    def end_page():
        current_stream.append('ET')
        content_str = '\n'.join(current_stream)
        pages_streams.append(content_str.encode('latin-1', errors='replace'))

    start_page()

    def add_line(font_tag: str, size: int, text: str, dy: float):
        nonlocal y
        if y < 65.0:
            end_page()
            start_page()
        escaped = _escape_pdf_literal(text)
        current_stream.append(f'{font_tag} {size} Tf')
        current_stream.append(f'50 {y:.1f} Td')
        current_stream.append(f'({escaped}) Tj')
        current_stream.append(f'-50 -{y:.1f} Td')
        y -= dy

    # Render Title
    for title_line in textwrap.wrap(title, width=50, break_long_words=True) or [title]:
        add_line('/F1', 18, title_line, 24.0)
    y -= 10.0

    for heading, body in blocks:
        if y < 85.0:
            end_page()
            start_page()

        if heading:
            for h_line in textwrap.wrap(heading, width=65, break_long_words=True) or [heading]:
                add_line('/F1', 12, h_line, 16.0)

        paragraphs = (body or '').split('\n')
        for p in paragraphs:
            p = p.strip()
            if not p:
                y -= 8.0
                continue
            wrapped_lines = textwrap.wrap(p, width=75, break_long_words=True, replace_whitespace=False)
            for line in (wrapped_lines or [p]):
                add_line('/F2', 10, line, 14.0)
        y -= 10.0

    end_page()

    total_pages = len(pages_streams)
    page_obj_ids = [5 + 2 * i for i in range(total_pages)]

    objects: Dict[int, bytes] = {}
    objects[1] = b'<< /Type /Catalog /Pages 2 0 R >>'
    kids_str = ' '.join(f'{pid} 0 R' for pid in page_obj_ids)
    objects[2] = f'<< /Type /Pages /Kids [{kids_str}] /Count {total_pages} >>'.encode('ascii')
    objects[3] = b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>'
    objects[4] = b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>'

    for i in range(total_pages):
        pid = 5 + 2 * i
        cid = 6 + 2 * i
        stream_bytes = pages_streams[i]
        objects[pid] = (
            f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595.28 841.89] '
            f'/Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> '
            f'/Contents {cid} 0 R >>'
        ).encode('ascii')
        objects[cid] = (
            f'<< /Length {len(stream_bytes)} >>\nstream\n'.encode('ascii')
            + stream_bytes +
            b'\nendstream'
        )

    max_id = 4 + 2 * total_pages
    out = bytearray(b'%PDF-1.4\n%\xe2\xe3\xcf\xd3\n')
    offsets: Dict[int, int] = {}
    for obj_id in range(1, max_id + 1):
        offsets[obj_id] = len(out)
        out.extend(f'{obj_id} 0 obj\n'.encode('ascii'))
        out.extend(objects[obj_id])
        out.extend(b'\nendobj\n')

    startxref = len(out)
    out.extend(f'xref\n0 {max_id + 1}\n0000000000 65535 f \n'.encode('ascii'))
    for obj_id in range(1, max_id + 1):
        out.extend(f'{offsets[obj_id]:010d} 00000 n \n'.encode('ascii'))
    out.extend(
        f'trailer\n<< /Size {max_id + 1} /Root 1 0 R >>\nstartxref\n{startxref}\n%%EOF\n'.encode('ascii')
    )
    return bytes(out)


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

    def export_as_pdf(self, snapshot_id: str) -> bytes:
        snap = self.get_snapshot(snapshot_id)
        if not snap:
            raise ExportError(f'Snapshot {snapshot_id!r} not found.')

        data = snap['data']
        blocks: List[Tuple[str, str]] = []
        if snap['type'] == 'conversation':
            for msg in data.get('messages', []):
                role = msg.get('role', 'user').capitalize()
                content = msg.get('content', '')
                blocks.append((role, content))
        elif snap['type'] == 'artifact':
            for sec_id, content in data.get('sections', {}).items():
                blocks.append((sec_id, content))

        return build_pdf_bytes(snap['title'], blocks)

    def close(self):
        with self._lock:
            self.conn.close()

