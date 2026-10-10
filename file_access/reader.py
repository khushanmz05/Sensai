"""Read bounded UTF-8 text beneath an explicitly selected directory.

Uses POSIX directory descriptors and O_NOFOLLOW at every path component.
No fallback to resolve-then-open: unsupported systems fail closed.
"""
from dataclasses import dataclass
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import stat


SUPPORTED = os.open in os.supports_dir_fd and all(
    hasattr(os, name) for name in ('O_NOFOLLOW', 'O_DIRECTORY', 'O_NONBLOCK'))
MAX_BYTES = 16 * 1024
EXTENSIONS = frozenset({'.txt', '.md', '.py', '.json'})


class FileAccessError(ValueError):
    """A denied, unavailable or unsupported file read."""


@dataclass(frozen=True)
class FileSnapshot:
    path: str
    content: str
    size_bytes: int


class WorkspaceReader:
    """Read-only capability, anchored to one directory for its lifetime.

    The caller owns this reader: use it as a context manager or call close().
    A root chosen by the operator is resolved once, then held by descriptor.
    Individual requested paths may never traverse symbolic links.
    """

    def __init__(self, root):
        self._root_fd = None
        if not SUPPORTED:
            raise FileAccessError('File access requires Linux/WSL with directory-descriptor support.')
        try:
            self.root = Path(root).expanduser().resolve(strict=True)
            self._root_fd = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        except (OSError, RuntimeError, ValueError) as error:
            raise FileAccessError('Workspace must be an existing, readable directory.') from error

    def close(self):
        if self._root_fd is not None:
            os.close(self._root_fd)
            self._root_fd = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def read_text(self, relative_path):
        if self._root_fd is None:
            raise FileAccessError('Workspace reader is closed.')
        if not isinstance(relative_path, str) or not relative_path.strip():
            raise FileAccessError('Provide a relative file path.')
        if any(ord(char) < 32 or ord(char) == 127 for char in relative_path):
            raise FileAccessError('Control characters are not allowed in file paths.')
        if ('\\' in relative_path or PureWindowsPath(relative_path).drive
                or PurePosixPath(relative_path).is_absolute()):
            raise FileAccessError('Only relative paths using / are allowed.')
        parts = relative_path.split('/')
        if any(part in ('', '.', '..') for part in parts):
            raise FileAccessError('Empty path components, . and .. are not allowed.')
        if any(part.startswith('.') for part in parts):
            raise FileAccessError('Hidden files and directories are not allowed.')
        if PurePosixPath(relative_path).suffix.lower() not in EXTENSIONS:
            raise FileAccessError('Allowed file extensions: .txt, .md, .py, .json.')

        directory_fd = None
        file_fd = None
        try:
            directory_fd = os.dup(self._root_fd)
            for part in parts[:-1]:
                next_fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                                  dir_fd=directory_fd)
                os.close(directory_fd)
                directory_fd = next_fd
            file_fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                              dir_fd=directory_fd)
            metadata = os.fstat(file_fd)
            if not stat.S_ISREG(metadata.st_mode):
                raise FileAccessError('Only regular text files can be read.')
            if metadata.st_nlink != 1:
                raise FileAccessError('Hard-linked files are not allowed.')
            if metadata.st_size > MAX_BYTES:
                raise FileAccessError(f'File exceeds the {MAX_BYTES}-byte limit.')
            # Limit the read too: a file may grow after fstat().
            with os.fdopen(file_fd, 'rb') as stream:
                file_fd = None
                data = stream.read(MAX_BYTES + 1)
            if len(data) > MAX_BYTES:
                raise FileAccessError(f'File exceeds the {MAX_BYTES}-byte limit.')
            if b'\0' in data:
                raise FileAccessError('Binary content is not allowed.')
            return FileSnapshot(relative_path, data.decode('utf-8'), len(data))
        except UnicodeDecodeError as error:
            raise FileAccessError('File must contain UTF-8 text.') from error
        except OSError as error:
            raise FileAccessError(
                'Cannot read file: missing, inaccessible, or a symbolic link in the path.') from error
        finally:
            if file_fd is not None:
                os.close(file_fd)
            if directory_fd is not None:
                os.close(directory_fd)
