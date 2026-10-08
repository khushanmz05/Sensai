import difflib
from pathlib import Path
import sqlite3
import threading
import time
from typing import Any, Dict, List, Optional

DEFAULT_PROMPT_PATH = Path(__file__).resolve().parent / 'system.txt'


class PromptError(Exception):
    """A prompt version error."""


class PromptVersionStore:
    
    def __init__(self, db_path: str = ':memory:', default_file: Optional[Path] = DEFAULT_PROMPT_PATH):
        self.db_path = db_path
        self._lock = threading.Lock()
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_db(default_file)

    def _init_db(self, default_file: Optional[Path]):
        with self._lock, self.conn:
            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS prompt_versions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    version_id TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    author TEXT NOT NULL,
                    description TEXT NOT NULL,
                    is_active INTEGER DEFAULT 0,
                    UNIQUE(name, version_id)
                )
            ''')
            self.conn.execute('CREATE INDEX IF NOT EXISTS idx_prompts_name ON prompt_versions (name)')

            # Seed default system prompt if table is empty and file exists
            count = self.conn.execute('SELECT COUNT(*) FROM prompt_versions').fetchone()[0]
            if count == 0 and default_file and default_file.exists():
                try:
                    content = default_file.read_text(encoding='utf-8').strip()
                    if content:
                        self.conn.execute('''
                            INSERT INTO prompt_versions (
                                name, version_id, content, timestamp, author, description, is_active
                            ) VALUES (?, ?, ?, ?, ?, ?, 1)
                        ''', ('system', 'v1', content, time.time(), 'system', 'Initial bootstrap prompt'))
                except OSError:
                    pass

    def create_version(
        self,
        name: str = 'system',
        content: str = '',
        author: str = 'user',
        description: str = '',
        activate: bool = True,
    ) -> Dict[str, Any]:
        """Create a new timestamped version of a prompt."""
        name = name.strip()
        if not name:
            raise PromptError('Prompt name cannot be empty.')
        content = content.strip()
        if not content:
            raise PromptError('Prompt content cannot be empty.')

        with self._lock, self.conn:
            # Determine next version id
            rows = self.conn.execute(
                'SELECT version_id FROM prompt_versions WHERE name = ? ORDER BY id DESC', (name,)
            ).fetchall()
            next_num = len(rows) + 1
            version_id = f'v{next_num}'

            if activate:
                self.conn.execute(
                    'UPDATE prompt_versions SET is_active = 0 WHERE name = ?', (name,)
                )

            now = time.time()
            self.conn.execute('''
                INSERT INTO prompt_versions (
                    name, version_id, content, timestamp, author, description, is_active
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (name, version_id, content, now, author.strip(), description.strip(), 1 if activate else 0))

        return self.get_version(name, version_id)

    def get_version(self, name: str, version_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a specific prompt version."""
        with self._lock:
            row = self.conn.execute('''
                SELECT * FROM prompt_versions WHERE name = ? AND version_id = ?
            ''', (name, version_id)).fetchone()
        return dict(row) if row else None

    def get_active_version(self, name: str = 'system') -> Optional[Dict[str, Any]]:
        with self._lock:
            row = self.conn.execute('''
                SELECT * FROM prompt_versions WHERE name = ? AND is_active = 1
                ORDER BY id DESC LIMIT 1
            ''', (name,)).fetchone()
        return dict(row) if row else None

    def list_versions(self, name: str = 'system') -> List[Dict[str, Any]]:
        with self._lock:
            rows = self.conn.execute('''
                SELECT * FROM prompt_versions WHERE name = ? ORDER BY id ASC
            ''', (name,)).fetchall()
        return [dict(r) for r in rows]

    def rollback(self, name: str, version_id: str) -> Dict[str, Any]:
        with self._lock, self.conn:
            target = self.conn.execute('''
                SELECT * FROM prompt_versions WHERE name = ? AND version_id = ?
            ''', (name, version_id)).fetchone()
            if not target:
                raise PromptError(f'Unknown version {version_id!r} for prompt {name!r}.')

            self.conn.execute('UPDATE prompt_versions SET is_active = 0 WHERE name = ?', (name,))
            self.conn.execute('''
                UPDATE prompt_versions SET is_active = 1 WHERE name = ? AND version_id = ?
            ''', (name, version_id))

        return self.get_version(name, version_id)

    def diff_versions(self, name: str, version_a: str, version_b: str) -> Dict[str, Any]:
        va = self.get_version(name, version_a)
        vb = self.get_version(name, version_b)
        if not va:
            raise PromptError(f'Version {version_a!r} not found for {name!r}.')
        if not vb:
            raise PromptError(f'Version {version_b!r} not found for {name!r}.')

        lines_a = va['content'].splitlines(keepends=True)
        lines_b = vb['content'].splitlines(keepends=True)

        diff_lines = list(difflib.unified_diff(
            lines_a, lines_b,
            fromfile=f'{name}@{version_a}',
            tofile=f'{name}@{version_b}',
        ))

        added = sum(1 for line in diff_lines if line.startswith('+') and not line.startswith('+++'))
        removed = sum(1 for line in diff_lines if line.startswith('-') and not line.startswith('---'))

        return {
            'name': name,
            'version_a': version_a,
            'version_b': version_b,
            'diff': ''.join(diff_lines),
            'lines_added': added,
            'lines_removed': removed,
        }

    def compare_performance(
        self,
        event_store,
        name: str,
        version_a: str,
        version_b: str,
    ) -> Dict[str, Any]:
        text_diff = self.diff_versions(name, version_a, version_b)
        metrics_a = event_store.get_metrics_by_prompt_version(version_a)
        metrics_b = event_store.get_metrics_by_prompt_version(version_b)

        latency_diff_ms = metrics_b['avg_latency_ms'] - metrics_a['avg_latency_ms']
        token_diff = metrics_b['avg_tokens'] - metrics_a['avg_tokens']
        error_rate_diff = metrics_b['error_rate'] - metrics_a['error_rate']

        return {
            'name': name,
            'version_a': {'version_id': version_a, 'metrics': metrics_a},
            'version_b': {'version_b': version_b, 'metrics': metrics_b},
            'diff': text_diff,
            'comparison': {
                'latency_diff_ms': round(latency_diff_ms, 2),
                'token_diff': round(token_diff, 2),
                'error_rate_diff': round(error_rate_diff, 4),
            },
        }

    def close(self):
        with self._lock:
            self.conn.close()

