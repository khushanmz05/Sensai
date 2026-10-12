"""CLI approval and save behavior: no model-generated confirmation."""
import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import chatbot
from file_access.reader import SUPPORTED, WorkspaceReader
from file_access.writer import WorkspaceWriter
from structured.output import JsonOutput


@unittest.skipUnless(SUPPORTED, 'Requires POSIX directory descriptors')
class SaveChatTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.writer = WorkspaceWriter(self.root)
        self.addCleanup(self.writer.close)

    def chat(self, inputs, reader=None, replies=None, json_output=None):
        output = io.StringIO()
        with patch('builtins.input', side_effect=inputs) as user_input, \
                patch('chatbot.stream_reply', side_effect=replies or (lambda *_: iter(['ANSWER']))) as model, \
                contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            chatbot.run_chat('test', 'Prompt', 'http://unused', 1, json_output=json_output,
                             file_reader=reader if reader is not None else self.writer)
        return output.getvalue(), model, user_input

    def test_confirmation_creates_exact_answer_without_extra_model_call(self):
        output, model, user_input = self.chat(['Hello', '/save answer.md', 'yes', '/exit'])
        self.assertIn('Content preview', output)
        self.assertIn('| ANSWER', output)
        self.assertIn('Created answer.md', output)
        self.assertEqual((self.root / 'answer.md').read_text(), 'ANSWER')
        model.assert_called_once()
        self.assertIn('Type yes', user_input.call_args_list[2].args[0])

    def test_rejection_empty_input_eof_and_interrupt_do_not_create_file(self):
        for answer in ['no', '', 'y', 'да', EOFError(), KeyboardInterrupt()]:
            with self.subTest(answer=answer):
                output, _, _ = self.chat(['Hello', '/save answer.md', answer, '/exit'])
                self.assertIn('Save cancelled', output)
                self.assertFalse((self.root / 'answer.md').exists())

    def test_readonly_mode_rejects_save_without_confirmation(self):
        with WorkspaceReader(self.root) as reader:
            output, model, user_input = self.chat(['Hello', '/save answer.md', '/exit'], reader=reader)
        self.assertIn('Saving is disabled', output)
        self.assertEqual(user_input.call_count, 3)
        self.assertFalse((self.root / 'answer.md').exists())

    def test_no_answer_and_clear_prevent_save(self):
        for inputs in [['/save answer.md', '/exit'],
                       ['Hello', '/clear', '/save answer.md', '/exit']]:
            output, _, _ = self.chat(inputs)
            self.assertIn('No completed answer', output)
            self.assertFalse((self.root / 'answer.md').exists())

    def test_partial_failed_response_is_never_saved(self):
        def failure(*_):
            yield 'PARTIAL'
            raise chatbot.ChatError('incomplete')
        output, _, _ = self.chat(['Hello', '/save answer.md', '/exit'], replies=failure)
        self.assertIn('No completed answer', output)
        self.assertFalse((self.root / 'answer.md').exists())

    def test_failed_new_generation_does_not_save_stale_answer(self):
        output, _, _ = self.chat(['First', 'Second', '/save answer.md', '/exit'],
                                replies=[iter(['OLD']), chatbot.ChatError('failed')])
        self.assertIn('No completed answer', output)
        self.assertFalse((self.root / 'answer.md').exists())

    def test_json_mode_saves_only_validated_output(self):
        self.chat(['Hello', '/save answer.json', 'yes', '/exit'],
                  replies=[iter(['INVALID']), iter(['{"ok":true}'])],
                  json_output=JsonOutput({'type': 'object'}))
        self.assertEqual((self.root / 'answer.json').read_text(), '{\n  "ok": true\n}')

    def test_model_yes_is_not_approval(self):
        self.chat(['Hello', '/save answer.md', 'no', '/exit'], replies=[iter(['yes'])])
        self.assertFalse((self.root / 'answer.md').exists())

    def test_existing_file_rejected_without_confirmation(self):
        (self.root / 'answer.md').write_text('KEEP')
        output, _, user_input = self.chat(['Hello', '/save answer.md', '/exit'])
        self.assertIn('overwriting is not allowed', output)
        self.assertEqual(user_input.call_count, 3)
        self.assertEqual((self.root / 'answer.md').read_text(), 'KEEP')

    def test_save_decisions_do_not_enter_conversation_history(self):
        _, model, _ = self.chat(['Hello', '/save answer.md', 'no', 'Continue', '/exit'])
        messages = model.call_args.args[2]
        self.assertEqual([m['content'] for m in messages[1:]], ['Hello', 'ANSWER', 'Continue'])

    def test_preview_escapes_control_characters(self):
        output = io.StringIO()
        with patch('builtins.input', return_value='no'), contextlib.redirect_stdout(output):
            chatbot.confirm_save(self.writer, 'x.md', 'Hello\x1b[2J\rHIDE\u202e')
        self.assertNotIn('\x1b', output.getvalue())
        self.assertNotIn('\r', output.getvalue())
        self.assertNotIn('\u202e', output.getvalue())
        self.assertIn('\\u001b', output.getvalue())

    def test_allow_create_requires_workspace(self):
        with patch('sys.argv', ['chatbot.py', '--model', 'test', '--allow-create']), \
                contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as exit:
            chatbot.main()
        self.assertEqual(exit.exception.code, 2)


if __name__ == '__main__':
    unittest.main()
