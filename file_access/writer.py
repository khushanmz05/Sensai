"""Create a new text file after a decision bound to an immutable preview."""
from dataclasses import dataclass
import os
import uuid

from file_access.reader import FileAccessError, MAX_BYTES, WorkspaceReader


@dataclass(frozen=True)
class CreatePlan:
    id: str
    path: str
    content: str
    size_bytes: int


def _identity(metadata):
    return metadata.st_dev, metadata.st_ino


def _require_absent(directory_fd, name):
    try:
        os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
    except FileNotFoundError:
        return
    raise FileAccessError('Target already exists; overwriting is not allowed.')


class WorkspaceWriter(WorkspaceReader):
    """Read + create capability. Construct only when creation is explicitly enabled.

    At most one preview is pending. Decisions consume it, and neither the path nor
    content can be supplied again at execution time. Approval provenance is the
    caller's responsibility; the CLI accepts it only from the human input prompt.
    """

    def __init__(self, root):
        self._pending = None
        if not {os.link, os.stat, os.unlink} <= os.supports_dir_fd:
            raise FileAccessError('Safe file creation requires Linux/WSL directory-descriptor support.')
        super().__init__(root)

    def close(self):
        self._pending = None
        super().close()

    def _check_root(self):
        if self._root_fd is None:
            raise FileAccessError('Workspace reader is closed.')
        if _identity(os.stat(self.root, follow_symlinks=False)) != _identity(os.fstat(self._root_fd)):
            raise FileAccessError('Workspace changed; restart before saving a file.')

    def prepare_create(self, relative_path, content):
        self._pending = None
        if not isinstance(content, str) or not content or '\0' in content:
            raise FileAccessError('Save content must be nonempty text without NUL characters.')
        try:
            data = content.encode('utf-8')
        except UnicodeError as error:
            raise FileAccessError('Save content must be valid UTF-8 text.') from error
        if len(data) > MAX_BYTES:
            raise FileAccessError(f'Answer exceeds the {MAX_BYTES}-byte save limit.')
        try:
            self._check_root()
            with self._open_parent(relative_path) as (directory_fd, name):
                _require_absent(directory_fd, name)
                parent_identity = _identity(os.fstat(directory_fd))
        except OSError as error:
            raise FileAccessError('Cannot prepare save: parent missing, inaccessible or a symbolic link.') from error
        plan = CreatePlan(uuid.uuid4().hex, relative_path, content, len(data))
        self._pending = (plan, parent_identity)
        return plan

    def decide(self, plan_id, approved):
        if self._pending is None or self._pending[0].id != plan_id:
            raise FileAccessError('Save request is unknown, expired or already decided.')
        plan, expected_parent = self._pending
        self._pending = None
        if approved is not True:
            return False
        try:
            self._check_root()
            with self._open_parent(plan.path) as (directory_fd, name):
                if _identity(os.fstat(directory_fd)) != expected_parent:
                    raise FileAccessError('Destination directory changed; request a new preview.')
                _require_absent(directory_fd, name)
                self._publish(directory_fd, name, plan.content.encode('utf-8'))
        except FileExistsError as error:
            raise FileAccessError('Target appeared during confirmation; it was not overwritten.') from error
        except OSError as error:
            raise FileAccessError('Save failed: destination unavailable or filesystem operation denied.') from error
        return True

    @staticmethod
    def _publish(directory_fd, name, data):
        # Write privately, then publish by link: complete content, no overwrite.
        temporary = '.sensai-' + uuid.uuid4().hex + '.tmp'
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                     0o600, dir_fd=directory_fd)
        try:
            with os.fdopen(fd, 'wb') as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            os.link(temporary, name, src_dir_fd=directory_fd, dst_dir_fd=directory_fd,
                    follow_symlinks=False)
        finally:
            os.unlink(temporary, dir_fd=directory_fd)
