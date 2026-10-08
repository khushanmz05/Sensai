from dataclasses import asdict, dataclass
import json
from pathlib import Path
import sqlite3
import threading
import time
from typing import Any, Dict, List, Optional


class ArtifactError(Exception):
    """Base error for artifact operations."""


class VersionConflictError(ArtifactError):
    """Raised when expected_version does not match current version."""


@dataclass
class ArtifactPatch:
    artifact_id: str
    expected_version: int
    section_id: str
    operation: str
    value: str = ''
    title: Optional[str] = None

    def validate(self):
        if not self.artifact_id or not self.artifact_id.strip():
            raise ArtifactError('artifact_id must be a non-empty string.')
        if type(self.expected_version) is not int or self.expected_version < 1:
            raise ArtifactError('expected_version must be a positive integer.')
        if not self.section_id or not self.section_id.strip():
            raise ArtifactError('section_id must be a non-empty string.')
        if self.operation not in ('update', 'insert', 'delete'):
            raise ArtifactError(f"Unsupported operation '{self.operation}'. Must be update, insert, or delete.")


class ArtifactStore:
    def __init__(self, db_path: str = ':memory:'):
        self.db_path = db_path
        self._lock = threading.Lock()
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self):
        with self._lock, self.conn:
            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS artifacts (
                    artifact_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    sections_json TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                )
            ''')
            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS artifact_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    artifact_id TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    sections_json TEXT NOT NULL,
                    patch_json TEXT,
                    created_at REAL NOT NULL,
                    UNIQUE(artifact_id, version)
                )
            ''')
            self.conn.execute('CREATE INDEX IF NOT EXISTS idx_art_hist_id ON artifact_history (artifact_id)')

    def create_artifact(
        self,
        artifact_id: str,
        title: str,
        initial_sections: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        artifact_id = artifact_id.strip()
        if not artifact_id:
            raise ArtifactError('artifact_id cannot be empty.')
        title = title.strip()
        if not title:
            raise ArtifactError('title cannot be empty.')

        sections = dict(initial_sections or {})
        now = time.time()
        sections_json = json.dumps(sections, ensure_ascii=False)

        with self._lock, self.conn:
            existing = self.conn.execute(
                'SELECT artifact_id FROM artifacts WHERE artifact_id = ?', (artifact_id,)
            ).fetchone()
            if existing:
                raise ArtifactError(f'Artifact {artifact_id!r} already exists.')

            self.conn.execute('''
                INSERT INTO artifacts (artifact_id, title, version, sections_json, created_at, updated_at)
                VALUES (?, ?, 1, ?, ?, ?)
            ''', (artifact_id, title, sections_json, now, now))

            self.conn.execute('''
                INSERT INTO artifact_history (artifact_id, version, title, sections_json, patch_json, created_at)
                VALUES (?, 1, ?, ?, NULL, ?)
            ''', (artifact_id, title, sections_json, now))

        return self.get_artifact(artifact_id)

    def get_artifact(self, artifact_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            row = self.conn.execute(
                'SELECT * FROM artifacts WHERE artifact_id = ?', (artifact_id,)
            ).fetchone()
            if not row:
                return None
            return {
                'artifact_id': row['artifact_id'],
                'title': row['title'],
                'version': row['version'],
                'sections': json.loads(row['sections_json']),
                'created_at': row['created_at'],
                'updated_at': row['updated_at'],
            }

    def list_artifacts(self) -> List[Dict[str, Any]]:
        with self._lock:
            rows = self.conn.execute('SELECT * FROM artifacts ORDER BY updated_at DESC').fetchall()
            return [
                {
                    'artifact_id': r['artifact_id'],
                    'title': r['title'],
                    'version': r['version'],
                    'sections_count': len(json.loads(r['sections_json'])),
                    'created_at': r['created_at'],
                    'updated_at': r['updated_at'],
                }
                for r in rows
            ]

    def apply_patch(self, patch: ArtifactPatch) -> Dict[str, Any]:
        patch.validate()

        with self._lock, self.conn:
            row = self.conn.execute(
                'SELECT * FROM artifacts WHERE artifact_id = ?', (patch.artifact_id,)
            ).fetchone()
            if not row:
                raise ArtifactError(f'Artifact {patch.artifact_id!r} not found.')

            current_version = row['version']
            if patch.expected_version != current_version:
                raise VersionConflictError(
                    f'Version conflict for {patch.artifact_id}: '
                    f'expected {patch.expected_version}, but current version is {current_version}.'
                )

            sections: Dict[str, str] = json.loads(row['sections_json'])
            title = patch.title if patch.title else row['title']

            if patch.operation == 'update':
                if patch.section_id not in sections:
                    raise ArtifactError(f'Section {patch.section_id!r} does not exist to update.')
                sections[patch.section_id] = patch.value

            elif patch.operation == 'insert':
                if patch.section_id in sections:
                    raise ArtifactError(f'Section {patch.section_id!r} already exists.')
                sections[patch.section_id] = patch.value

            elif patch.operation == 'delete':
                if patch.section_id not in sections:
                    raise ArtifactError(f'Section {patch.section_id!r} does not exist to delete.')
                del sections[patch.section_id]

            new_version = current_version + 1
            now = time.time()
            sections_json = json.dumps(sections, ensure_ascii=False)
            patch_json = json.dumps(asdict(patch), ensure_ascii=False)

            self.conn.execute('''
                UPDATE artifacts
                SET version = ?, title = ?, sections_json = ?, updated_at = ?
                WHERE artifact_id = ?
            ''', (new_version, title, sections_json, now, patch.artifact_id))

            self.conn.execute('''
                INSERT INTO artifact_history (artifact_id, version, title, sections_json, patch_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (patch.artifact_id, new_version, title, sections_json, patch_json, now))

        return self.get_artifact(patch.artifact_id)

    def get_history(self, artifact_id: str) -> List[Dict[str, Any]]:
        with self._lock:
            rows = self.conn.execute('''
                SELECT * FROM artifact_history WHERE artifact_id = ? ORDER BY version ASC
            ''', (artifact_id,)).fetchall()
            return [
                {
                    'artifact_id': r['artifact_id'],
                    'version': r['version'],
                    'title': r['title'],
                    'sections': json.loads(r['sections_json']),
                    'patch': json.loads(r['patch_json']) if r['patch_json'] else None,
                    'created_at': r['created_at'],
                }
                for r in rows
            ]

    def render_markdown(self, artifact_id: str) -> str:
        art = self.get_artifact(artifact_id)
        if not art:
            raise ArtifactError(f'Artifact {artifact_id!r} not found.')

        lines = [f"# {art['title']}", '']
        for sec_id, content in art['sections'].items():
            lines.append(f"## {sec_id}")
            lines.append(content.strip())
            lines.append('')
        return '\n'.join(lines).strip() + '\n'

    def close(self):
        with self._lock:
            self.conn.close()

