"""Trusted, operator-owned stdio server configuration. Never supplied by a model."""
from dataclasses import dataclass
import math
from pathlib import Path
import re
import sys

from structured.output import strict_json


class McpError(ValueError):
    """An MCP failure safe to show without server payloads or tracebacks."""


NAME = re.compile(r'[A-Za-z][A-Za-z0-9_]{0,39}\Z')


@dataclass(frozen=True)
class ServerConfig:
    name: str
    command: str
    args: tuple
    cwd: str
    allow_tools: tuple
    auto_approve: tuple = ()
    timeout: float = 15


def load_config(path):
    try:
        path = Path(path).resolve(strict=True)
        with path.open('rb') as handle:
            raw = handle.read(65537)
        if len(raw) > 65536:
            raise McpError('MCP configuration exceeds 64 KiB.')
        data = strict_json(raw.decode('utf-8'))
        if not isinstance(data, dict) or set(data) != {'servers'}:
            raise McpError('MCP config must contain only a servers list.')
        rows = data['servers']
        if not isinstance(rows, list) or not 1 <= len(rows) <= 4:
            raise McpError('Configure between one and four MCP servers.')
        servers, seen = [], set()
        for row in rows:
            required = {'name', 'command', 'args', 'allow_tools'}
            if (not isinstance(row, dict) or not required <= set(row)
                    or set(row) - required - {'cwd', 'timeout', 'auto_approve'}):
                raise McpError('Invalid MCP server fields.')
            name = row['name']
            if not isinstance(name, str) or not NAME.fullmatch(name) or name in seen:
                raise McpError('MCP server names must be unique simple identifiers.')
            seen.add(name)
            command, args = row['command'], row['args']
            if not isinstance(command, str) or not command.strip() or '\0' in command:
                raise McpError('MCP command must be an executable, not a shell expression.')
            if not isinstance(args, list) or any(not isinstance(a, str) or '\0' in a for a in args):
                raise McpError('MCP args must be a list of strings.')
            allow, auto = row['allow_tools'], row.get('auto_approve', [])
            for values in (allow, auto):
                if (not isinstance(values, list) or len(values) > 32
                        or any(not isinstance(v, str) or not NAME.fullmatch(v) for v in values)
                        or len(set(values)) != len(values)):
                    raise McpError('MCP tool allowlists must contain unique simple names.')
            if not allow or not set(auto) <= set(allow):
                raise McpError('auto_approve must be a subset of nonempty allow_tools.')
            timeout = row.get('timeout', 15)
            if (type(timeout) not in (int, float) or not math.isfinite(timeout)
                    or not 0 < timeout <= 60):
                raise McpError('MCP timeout must be between 0 and 60 seconds.')
            cwd = row.get('cwd', '.')
            if not isinstance(cwd, str):
                raise McpError('MCP cwd must be a path relative to the config file.')
            directory = (path.parent / cwd).resolve(strict=True)
            if not directory.is_dir():
                raise McpError('MCP cwd is not a directory.')
            servers.append(ServerConfig(name, sys.executable if command == '$PYTHON' else command,
                                        tuple(args), str(directory), tuple(allow), tuple(auto), timeout))
        return tuple(servers)
    except McpError:
        raise
    except (OSError, UnicodeError, ValueError, TypeError, RecursionError) as error:
        raise McpError('Cannot read valid MCP configuration; check the file and paths.') from error
