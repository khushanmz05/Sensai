"""Settings shared by the CLI and web service, overridable via environment variables."""
from dataclasses import dataclass
import os
from pathlib import Path
from typing import Optional
import requests


def _get_env_path(name: str, default: str) -> Path:
    val = os.getenv(name)
    if val:
        return Path(val).resolve()
    return (Path(__file__).resolve().parent.parent / default).resolve()


@dataclass
class Settings:
    ollama_host: str = os.getenv('SENSAI_OLLAMA_HOST') or os.getenv('OLLAMA_HOST', 'http://localhost:11434')
    default_model: str = os.getenv('SENSAI_MODEL') or os.getenv('OLLAMA_MODEL', 'llama3.2:1b')
    mode: str = os.getenv('SENSAI_MODE', 'ollama')  # 'ollama' or 'stub'
    sessions_db: Path = _get_env_path('SENSAI_DB', 'sensai_sessions.db')
    events_db: Path = _get_env_path('SENSAI_EVENTS_DB', 'sensai_events.db')
    prompts_db: Path = _get_env_path('SENSAI_PROMPTS_DB', 'sensai_prompts.db')
    artifacts_db: Path = _get_env_path('SENSAI_ARTIFACTS_DB', 'sensai_artifacts.db')
    snapshots_db: Path = _get_env_path('SENSAI_SNAPSHOTS_DB', 'sensai_snapshots.db')
    workspace_dir: Optional[Path] = Path(os.getenv('SENSAI_WORKSPACE')).resolve() if os.getenv('SENSAI_WORKSPACE') else None

    @property
    def clean_ollama_host(self) -> str:
        return self.ollama_host.rstrip('/')

    _last_alive_check: float = 0.0
    _last_alive_result: bool = False

    def check_ollama_alive(self, timeout: float = 0.15) -> bool:
        """Check if the configured Ollama server is reachable, cached for 3 seconds."""
        import time
        now = time.time()
        if now - self._last_alive_check < 3.0:
            return self._last_alive_result

        self._last_alive_check = now
        try:
            resp = requests.get(f"{self.clean_ollama_host}/api/version", timeout=timeout)
            self._last_alive_result = (resp.status_code == 200)
        except Exception:
            try:
                resp = requests.get(self.clean_ollama_host, timeout=timeout)
                self._last_alive_result = (resp.status_code == 200)
            except Exception:
                self._last_alive_result = False
        return self._last_alive_result


settings = Settings()
