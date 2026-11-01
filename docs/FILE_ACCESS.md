# File access and confirmed creation

The CLI can attach a workspace file or create a new file after confirmation.
Existing files cannot be edited or overwritten. For model-selected file reads and
browser tool approvals, see [MCP tools](MCP.md). These are separate entry points.

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
- The default `WorkspaceReader` capability exposes no creation or mutation.
  `--allow-create` explicitly selects `WorkspaceWriter`, which supports the
  confirmed creation flow below. Neither capability exposes overwrite, delete,
  shell execution or model-initiated tool operations.

This is an application permission boundary, not an OS sandbox. The operator must
choose a directory whose allowed files may be sent to the configured Ollama host.
The host may be remote if `--host` is explicitly configured. Mount administration,
concurrent editing by other processes and confidentiality classification of files
are outside this increment. A concurrently edited file is not an atomic filesystem snapshot.

The implementation requires POSIX directory-descriptor support and is tested in
Linux/WSL. Native Windows rejects `--workspace` with an explanation; ordinary
chat and T5 do not require this option. No unsafe path-opening fallback is used.

## Create a new file with confirmation

```bash
mkdir -p local-output
python chatbot.py --model llama3.2:1b --workspace local-output --allow-create
```

Ask for a short explanation, then `/save answer.md`. The complete answer is shown
with the destination and UTF-8 byte count. The preview escapes nonprinting characters
so terminal controls cannot hide the operation. The saved bytes remain the original
answer. Type `yes` to approve (case-insensitive, surrounding spaces ignored).
Anything else, EOF or Ctrl+C cancels without writing. `/read answer.md` can inspect
the new file. `local-output/` is ignored by Git.

Creation follows the same path, extension and 16-KiB rules as reading. A parent
directory must already exist. Existing entries (including dangling symbolic links)
are never overwritten. The service checks the destination before showing a preview,
then again after approval. If the parent directory identity changed, the request
is rejected. The final publish operation also refuses an existing target, covering
a race in which another process creates it just before publication.

The creation service stores one immutable plan and returns its id, relative path,
content and byte count. `decide(plan_id, approved)` accepts no replacement path or
content. Only boolean `True` approves. A decision is consumed once; a new preview
invalidates the previous one. The trusted CLI derives that boolean only from the
human confirmation prompt. It is never taken from model output or a file.

After approval, content is written to a private temporary file in the checked
parent directory, flushed and published with a no-overwrite hard link. The temporary
name is removed on handled success/failure. The final file has mode 0600, is not
executable, and contains exactly the completed answer (no extra newline). A process
kill or machine crash can leave a hidden temporary file; this is not crash recovery
or a guarantee of directory-metadata durability. No existing target is deleted.

A failed/interrupted generation clears the eligible save answer; partially visible
output or an older answer will not silently be saved. `/clear` also clears it.
JSON mode saves only the locally validated JSON response. Save requests, previews
and decisions do not add turns or make another model call.

This file-creation flow uses a synchronous CLI approval. It does not expose file
creation in the browser or persist waiting requests across restarts. The Python API
assumes a trusted caller supplies approval decisions. The directory
must be under the operator's control; this is not a sandbox against another local
process that can arbitrarily rename/mount directories or modify temporary files.

## Context lifecycle

One file can be pending. A successful `/read` replaces the pending file. A failed
read clears it, preventing accidental reuse of an older attachment. `/clear`
discards pending content and starts a new session; the previous session stays saved.
To attach a path containing
spaces, type it directly after `/read` without shell quotes.

The next question contains a JSON-encoded file reference in a user message.
The system prompt marks file references as untrusted data; changing personas
retains this rule. This does not prove model resistance to prompt injection.
Permissions are enforced in code independently of model text.

After a successful answer, the question and file reference are committed to
session history once. The file is not reread for follow-ups. On an Ollama error,
invalid JSON exhaustion or cancellation, history is unchanged and the pending file
is retained for a retry. `/clear` removes the pending attachment. Successfully saved
turns, including their file context, remain in the persisted session. An attachment
that has not yet been sent is held only in memory. See [configuration](CONFIGURATION.md)
for session commands and [the feature register](FEATURES.md) for memory limits.

## Verification

```bash
python -m unittest discover -s tests -v
```

Tests cover allowed reads, traversal, hidden paths, symbolic/hard links, nonregular
files, size/encoding limits, directory replacement during reads, disabled access,
context/history behavior, cancellation and combination with T5. Creation tests add
one-use approval, rejection, no-overwrite races, directory replacement during the
approval wait, UTF-8 content, write failure cleanup and incomplete-answer refusal.

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
