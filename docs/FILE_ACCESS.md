# T4 first increment: read-only file context

Owner: B. Status: CLI implementation; full T4 remains in progress.
The next increment will cover write/create permissions and action approval.

## Usage (Linux/WSL)

From the repository root, with the virtual environment activated:

```bash
python chatbot.py --model llama3.2:1b --workspace examples
```

Enter `/read project_notes.md`, then ask `Which language and database does this
project use?`. The supplied example says Python and SQLite. `/read` itself does
not call the model or print the file contents. It reports the file name and size.

Combine with T5:

```bash
python chatbot.py --model llama3.2:1b --workspace examples --json-schema schemas/tasks.json
```

Enter `/read project_notes.md`, then `Extract the two tasks and their priorities`.
Expected meaning: login screen (high), README update (low).

## Permission boundary

- File access is disabled unless the operator supplies `--workspace`.
- One root directory is resolved and opened at startup. Requests must use relative
  paths with `/` separators. Absolute paths, drive-qualified paths, empty components,
  `.` and `..` components, control characters and hidden names are rejected.
- Only regular UTF-8 `.txt`, `.md`, `.py`, `.json` files are accepted, up to
  16,384 bytes. Reads are bounded even if the file grows after the size check.
  NUL-containing content is rejected as binary. Empty text files are allowed.
- Each path component is opened relative to a directory descriptor with
  `O_NOFOLLOW`. A symbolic link is rejected even when it points inside the root.
  Hard-linked files are rejected. Directories, devices and named pipes are not
  accepted as content; nonblocking open prevents a FIFO from hanging the chat.
- The root descriptor is held until the chat exits. Replacing a directory name
  with a symbolic link cannot redirect the read through that link.
- No write, create, delete, shell or model-initiated tool operation is exposed.

This is an application permission boundary, not an OS sandbox. The operator must
choose a directory whose allowed files may be sent to the configured Ollama host.
The host may be remote if `--host` is explicitly configured. Mount administration,
concurrent editing by other processes and confidentiality classification of files
are outside this increment. A concurrently edited file is not an atomic filesystem snapshot.

The implementation requires POSIX directory-descriptor support and is tested in
Linux/WSL. Native Windows rejects `--workspace` with an explanation; ordinary
chat and T5 do not require this option. No unsafe path-opening fallback is used.

## Context lifecycle

One file can be pending. A successful `/read` replaces the pending file. A failed
read clears it, preventing accidental reuse of an older attachment. `/clear`
discards both pending content and conversation history. To attach a path containing
spaces, type it directly after `/read` without shell quotes.

The next question contains a JSON-encoded file reference in a user message.
The system prompt marks file references as untrusted data; changing personas
retains this rule. This does not prove model resistance to prompt injection.
Permissions are enforced in code independently of model text.

After a successful answer, the question and file reference are committed to
session history once. The file is not reread for follow-ups. On an Ollama error,
invalid JSON exhaustion or cancellation, history is unchanged and the pending file
is retained for a retry. `/clear` removes it. Like other chat history, file context
is lost on exit. Token budgeting is a separate feature, not implemented here.

## Verification

```bash
python -m unittest discover -s tests -v
```

Tests cover allowed reads, traversal, hidden paths, symbolic/hard links, nonregular
files, size/encoding limits, directory replacement during reads, disabled access,
context/history behavior, cancellation and combination with T5.

Manual negative checks in the chat:

```text
/read ../README.md
/read /etc/passwd
/read missing.md
```

Each must report a file error without calling Ollama. Then read the valid example
again and ask a question to confirm recovery. A symlink check can be performed in
a temporary directory; do not alter real project files for that test.

Implementation reference: [Python os file operations](https://docs.python.org/3.12/library/os.html#files-and-directories).
