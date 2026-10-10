"""T4 create-only operations and one-use approval decisions."""
from dataclasses import FrozenInstanceError
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch

from file_access.reader import FileAccessError, MAX_BYTES, SUPPORTED, WorkspaceReader
from file_access.writer import WorkspaceWriter


@unittest.skipUnless(SUPPORTED, 'Requires POSIX directory descriptors')
class FileWriteTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)
        self.root = self.base / 'allowed'
        self.root.mkdir()
        self.outside = self.base / 'outside'
        self.outside.mkdir()
        self.writer = WorkspaceWriter(self.root)
        self.addCleanup(self.writer.close)

    def test_prepare_and_reject_have_no_writes(self):
        plan = self.writer.prepare_create('answer.md', 'Hello')
        self.assertEqual(list(self.root.iterdir()), [])
        self.assertFalse(self.writer.decide(plan.id, False))
        self.assertEqual(list(self.root.iterdir()), [])

    def test_approved_create_writes_exact_utf8_and_can_be_read(self):
        content = 'Привет\nNo added newline'
        plan = self.writer.prepare_create('answer.md', content)
        self.assertEqual(plan.size_bytes, len(content.encode('utf-8')))
        with self.assertRaises(FrozenInstanceError):
            plan.path = 'different.md'
        self.assertTrue(self.writer.decide(plan.id, True))
        self.assertEqual((self.root / 'answer.md').read_bytes(), content.encode('utf-8'))
        self.assertEqual(self.writer.read_text('answer.md').content, content)
        self.assertEqual(stat.S_IMODE((self.root / 'answer.md').stat().st_mode), 0o600)
        self.assertEqual(len(list(self.root.iterdir())), 1)

    def test_only_boolean_true_approves(self):
        for value in ['yes', 1, None, False]:
            plan = self.writer.prepare_create('answer.txt', 'Hello')
            self.assertFalse(self.writer.decide(plan.id, value))
        self.assertFalse((self.root / 'answer.txt').exists())

    def test_decisions_are_one_use_and_new_preview_expires_old(self):
        old = self.writer.prepare_create('old.md', 'Old')
        new = self.writer.prepare_create('new.md', 'New')
        with self.assertRaises(FileAccessError):
            self.writer.decide(old.id, True)
        self.writer.decide(new.id, True)
        with self.assertRaises(FileAccessError):
            self.writer.decide(new.id, True)
        self.assertFalse((self.root / 'old.md').exists())

    def test_existing_file_symlink_and_directory_not_overwritten(self):
        existing = self.root / 'existing.txt'
        existing.write_text('KEEP')
        (self.root / 'link.txt').symlink_to(self.outside / 'missing.txt')
        (self.root / 'folder.txt').mkdir()
        for path in ['existing.txt', 'link.txt', 'folder.txt']:
            with self.subTest(path=path), self.assertRaisesRegex(FileAccessError, 'exists'):
                self.writer.prepare_create(path, 'REPLACE')
        self.assertEqual(existing.read_text(), 'KEEP')
        self.assertFalse((self.outside / 'missing.txt').exists())

    def test_file_created_while_awaiting_approval_is_preserved(self):
        plan = self.writer.prepare_create('answer.txt', 'New')
        (self.root / 'answer.txt').write_text('OTHER_PROCESS')
        with self.assertRaises(FileAccessError):
            self.writer.decide(plan.id, True)
        self.assertEqual((self.root / 'answer.txt').read_text(), 'OTHER_PROCESS')

    def test_target_race_at_publish_cannot_overwrite(self):
        plan = self.writer.prepare_create('answer.txt', 'New')
        real_link = os.link
        def race(src, dst, **kwargs):
            (self.root / 'answer.txt').write_text('RACE_WINNER')
            return real_link(src, dst, **kwargs)
        with patch('file_access.writer.os.link', side_effect=race):
            with self.assertRaises(FileAccessError):
                self.writer.decide(plan.id, True)
        self.assertEqual((self.root / 'answer.txt').read_text(), 'RACE_WINNER')
        self.assertEqual([p.name for p in self.root.iterdir()], ['answer.txt'])

    def test_invalid_paths_create_nothing(self):
        for path in ['../outside/x.txt', str(self.outside / 'x.txt'), '.secret.txt',
                     'notes/../../x.txt', 'x.exe', 'C:/x.txt', 'a\n.txt']:
            with self.subTest(path=path), self.assertRaises(FileAccessError):
                self.writer.prepare_create(path, 'Text')
        self.assertEqual(list(self.root.iterdir()), [])
        self.assertEqual(list(self.outside.iterdir()), [])

    def test_symlinked_parent_denied(self):
        (self.root / 'linked').symlink_to(self.outside, target_is_directory=True)
        with self.assertRaises(FileAccessError):
            self.writer.prepare_create('linked/x.txt', 'Text')
        self.assertEqual(list(self.outside.iterdir()), [])

    def test_changed_parent_requires_new_preview(self):
        parent = self.root / 'notes'
        parent.mkdir()
        plan = self.writer.prepare_create('notes/x.md', 'Hello')
        parent.rename(self.root / 'old-notes')
        parent.mkdir()
        with self.assertRaisesRegex(FileAccessError, 'changed'):
            self.writer.decide(plan.id, True)
        self.assertFalse((parent / 'x.md').exists())
        self.assertFalse((self.root / 'old-notes/x.md').exists())

    def test_parent_changed_to_symlink_while_waiting_is_denied(self):
        parent = self.root / 'notes'
        parent.mkdir()
        plan = self.writer.prepare_create('notes/x.md', 'Hello')
        parent.rename(self.root / 'old-notes')
        parent.symlink_to(self.outside, target_is_directory=True)
        with self.assertRaises(FileAccessError):
            self.writer.decide(plan.id, True)
        self.assertFalse((self.outside / 'x.md').exists())

    def test_root_replacement_while_waiting_is_denied(self):
        plan = self.writer.prepare_create('x.md', 'Hello')
        self.root.rename(self.base / 'original')
        self.root.symlink_to(self.outside, target_is_directory=True)
        with self.assertRaises(FileAccessError):
            self.writer.decide(plan.id, True)
        self.assertFalse((self.base / 'original/x.md').exists())
        self.assertFalse((self.outside / 'x.md').exists())

    def test_size_encoding_and_binary_limits(self):
        for content in ['', '\0', '\ud800', 'a' * (MAX_BYTES + 1), 'я' * MAX_BYTES]:
            with self.subTest(length=len(content)), self.assertRaises(FileAccessError):
                self.writer.prepare_create('x.txt', content)
        plan = self.writer.prepare_create('x.txt', 'a' * MAX_BYTES)
        self.writer.decide(plan.id, True)
        self.assertEqual((self.root / 'x.txt').stat().st_size, MAX_BYTES)

    def test_failed_flush_does_not_publish_partial_file(self):
        plan = self.writer.prepare_create('x.txt', 'Hello')
        with patch('file_access.writer.os.fsync', side_effect=OSError('disk failure')):
            with self.assertRaises(FileAccessError):
                self.writer.decide(plan.id, True)
        self.assertEqual(list(self.root.iterdir()), [])
        with self.assertRaises(FileAccessError):
            self.writer.decide(plan.id, True)

    def test_missing_parent_is_not_created(self):
        with self.assertRaises(FileAccessError):
            self.writer.prepare_create('missing/x.md', 'Hello')
        self.assertFalse((self.root / 'missing').exists())

    def test_readonly_capability_has_no_creation_method(self):
        with WorkspaceReader(self.root) as reader:
            self.assertFalse(hasattr(reader, 'prepare_create'))

    def test_plan_cannot_be_used_by_another_writer_or_after_close(self):
        plan = self.writer.prepare_create('x.md', 'Hello')
        with WorkspaceWriter(self.root) as other:
            with self.assertRaises(FileAccessError):
                other.decide(plan.id, True)
        self.writer.close()
        with self.assertRaises(FileAccessError):
            self.writer.decide(plan.id, True)
        self.assertEqual(list(self.root.iterdir()), [])


if __name__ == '__main__':
    unittest.main()
