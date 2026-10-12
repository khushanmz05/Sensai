"""Read-only T4 permission and filesystem boundary tests."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from file_access.reader import FileAccessError, MAX_BYTES, SUPPORTED, WorkspaceReader


@unittest.skipUnless(SUPPORTED, 'Secure file reading requires POSIX directory descriptors')
class FileAccessTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)
        self.root = self.base / 'allowed'
        self.root.mkdir()
        self.outside = self.base / 'outside'
        self.outside.mkdir()
        (self.outside / 'secret.txt').write_text('OUTSIDE_SECRET', encoding='utf-8')
        self.reader = WorkspaceReader(self.root)
        self.addCleanup(self.reader.close)

    def test_reads_nested_unicode_file_with_spaces(self):
        folder = self.root / 'notes'
        folder.mkdir()
        original = 'Привет\nPython functions'
        path = folder / 'my notes.md'
        path.write_text(original, encoding='utf-8')
        result = self.reader.read_text('notes/my notes.md')
        self.assertEqual(result.content, original)
        self.assertEqual(result.path, 'notes/my notes.md')
        self.assertEqual(result.size_bytes, len(original.encode('utf-8')))
        self.assertEqual(path.read_text(encoding='utf-8'), original)

    def test_invalid_paths_denied_before_open(self):
        invalid = ['../outside/secret.txt', 'notes/../../outside/secret.txt',
                   str(self.outside / 'secret.txt'), 'C:/secret.txt', 'C:secret.txt',
                   '..\\secret.txt', '.git/config.md', 'notes/.private.txt',
                   'notes//a.txt', './a.txt', 'notes/./a.txt', '', 'a\0.txt',
                   'a\n.txt', 'file.pdf']
        with patch('file_access.reader.os.open') as opened:
            for name in invalid:
                with self.subTest(name=name), self.assertRaises(FileAccessError):
                    self.reader.read_text(name)
            opened.assert_not_called()

    def test_symlink_to_outside_file_is_denied(self):
        (self.root / 'link.txt').symlink_to(self.outside / 'secret.txt')
        with self.assertRaises(FileAccessError):
            self.reader.read_text('link.txt')

    def test_symlink_to_outside_directory_is_denied(self):
        (self.root / 'linked').symlink_to(self.outside, target_is_directory=True)
        with self.assertRaises(FileAccessError):
            self.reader.read_text('linked/secret.txt')

    def test_internal_symlink_is_also_denied(self):
        (self.root / 'real.txt').write_text('inside')
        (self.root / 'link.txt').symlink_to(self.root / 'real.txt')
        with self.assertRaises(FileAccessError):
            self.reader.read_text('link.txt')

    def test_hard_link_to_outside_is_denied(self):
        os.link(self.outside / 'secret.txt', self.root / 'hard.txt')
        with self.assertRaisesRegex(FileAccessError, 'Hard-linked'):
            self.reader.read_text('hard.txt')

    def test_size_limit_and_exact_boundary(self):
        path = self.root / 'large.txt'
        path.write_bytes(b'a' * MAX_BYTES)
        self.assertEqual(self.reader.read_text('large.txt').size_bytes, MAX_BYTES)
        path.write_bytes(b'a' * (MAX_BYTES + 1))
        with self.assertRaisesRegex(FileAccessError, 'limit'):
            self.reader.read_text('large.txt')

    def test_file_growth_after_stat_is_still_bounded(self):
        path = self.root / 'growing.txt'
        path.write_text('small')
        real_fstat = os.fstat
        def grow(fd):
            metadata = real_fstat(fd)
            with path.open('ab') as stream:
                stream.write(b'a' * MAX_BYTES)
            return metadata
        with patch('file_access.reader.os.fstat', side_effect=grow):
            with self.assertRaisesRegex(FileAccessError, 'limit'):
                self.reader.read_text('growing.txt')

    def test_invalid_utf8_and_binary_are_denied(self):
        for data in [b'\xff\xfe', b'hello\0world']:
            (self.root / 'binary.txt').write_bytes(data)
            with self.subTest(data=data), self.assertRaises(FileAccessError):
                self.reader.read_text('binary.txt')

    def test_directory_and_fifo_are_denied_without_blocking(self):
        (self.root / 'folder.txt').mkdir()
        os.mkfifo(self.root / 'pipe.txt')
        for name in ['folder.txt', 'pipe.txt']:
            with self.subTest(name=name), self.assertRaisesRegex(FileAccessError, 'regular'):
                self.reader.read_text(name)

    def test_missing_file_and_os_permission_failure(self):
        with self.assertRaises(FileAccessError):
            self.reader.read_text('missing.txt')
        with patch('file_access.reader.os.open', side_effect=PermissionError()):
            with self.assertRaises(FileAccessError):
                self.reader.read_text('denied.txt')

    def test_workspace_must_be_directory(self):
        for path in [self.base / 'missing', self.outside / 'secret.txt']:
            with self.subTest(path=path), self.assertRaises(FileAccessError):
                WorkspaceReader(path)

    def test_closed_reader_and_idempotent_close(self):
        self.reader.close()
        self.reader.close()
        with self.assertRaisesRegex(FileAccessError, 'closed'):
            self.reader.read_text('x.txt')

    def test_root_descriptor_stays_on_original_directory(self):
        (self.root / 'secret.txt').write_text('ALLOWED')
        self.root.rename(self.base / 'original')
        self.root.symlink_to(self.outside, target_is_directory=True)
        self.assertEqual(self.reader.read_text('secret.txt').content, 'ALLOWED')

    def test_directory_swap_during_read_cannot_follow_new_link(self):
        folder = self.root / 'nested'
        folder.mkdir()
        (folder / 'secret.txt').write_text('ALLOWED')
        real_open = os.open
        def swap(name, flags, **kwargs):
            if name == 'secret.txt':
                folder.rename(self.root / 'original')
                folder.symlink_to(self.outside, target_is_directory=True)
            return real_open(name, flags, **kwargs)
        with patch('file_access.reader.os.open', side_effect=swap):
            self.assertEqual(self.reader.read_text('nested/secret.txt').content, 'ALLOWED')


class UnsupportedPlatformTests(unittest.TestCase):
    def test_no_insecure_fallback(self):
        with patch('file_access.reader.SUPPORTED', False), self.assertRaises(FileAccessError):
            WorkspaceReader('.')


if __name__ == '__main__':
    unittest.main()
