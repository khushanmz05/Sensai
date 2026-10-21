# Sensai

Python 3.10+ CLI chatbot using the Ollama HTTP API directly. No LLM framework or Ollama SDK.
This working copy includes the CLI chat, personas (A5), and structured workflows
(T5) with persistent task lists, plans and custom records in the CLI and browser.
T4 provides opt-in file context and creation of new files for Linux/WSL.
The first A3 increment previews each save and requires explicit confirmation.
It does not implement the full Sensai feature catalogue.

## Install and run for the first time

**Start with [the step-by-step installation guide](START.md).** It explains how
to install Ubuntu through WSL on Windows, obtain the project, install dependencies
and Ollama, download a model, ask your first question, and run the tests. Each step
identifies the terminal to use and the expected result. It also includes fixes for
common errors and instructions for [starting again later](START.md#start-again-tomorrow).

The documented path is Ubuntu 24.04, directly or inside WSL 2. Python 3.10 or newer
is required. Windows users should use WSL to exercise the file features, which
are not supported in native PowerShell. No API key is needed for the local model.
The web UI remains a prototype; the installation guide runs the CLI.

The examples below assume setup is complete, your Ubuntu terminal is in the
project folder, and `.venv` is active. Leave an existing chat with `/exit` before
running another shell command. `llama3.2:1b` is the demonstration model; any
installed chat model can be selected, with behavior depending on its capabilities.

## Usage

```bash
python3 chatbot.py --model llama3.2:1b
python3 chatbot.py --model YOUR_INSTALLED_MODEL --system-prompt prompts/system.txt
python3 chatbot.py --model llama3.2:1b --host http://localhost:11434 --timeout 240
python3 chatbot.py --help
```

Edit `prompts/system.txt` to change the system prompt; restart to reload it.
The default prompt is located relative to the script, so other working directories work.
Custom relative prompt paths are resolved relative to your current working directory.
The model is explicitly required on the command line; no model name is hardcoded.

- `/exit`: quit
- `/clear`: clear turns, retain the system prompt
- `/persona`: list personas; `/persona <id>`: switch persona, keep history
- `--persona <id>`: start with a persona; personas live in `personas/*.json`
  (fields `id`, `name`, `tone`, `role`, `scope`; `--persona-dir` to use another folder)
- Ctrl+C during generation: discard this turn and continue chatting
- Ctrl+C or EOF at the input prompt: exit cleanly

## Implemented requirements

| Bootstrap requirement | Implementation |
| --- | --- |
| CLI and selectable model | argparse, required `--model` |
| Progressive responses | `stream=True`, read NDJSON chunks, print with flush |
| In-session history | resend system prompt + successful previous turns + new user turn |
| Prompt loaded from a file | `--system-prompt`, UTF-8 file validation |
| Missing model | HTTP 404 with model pull instruction |
| Empty input | explanation, no request sent |
| Connection failure | explicit error, return to input |

Also handles timeouts, HTTP errors, errors within streams, malformed responses,
empty answers and streams that end without a completion marker.
Only a complete question/answer pair is committed to history. Partial visible output
is not reused after an error. All model calls use `POST /api/chat` directly.

## Structured JSON output (T5, member B)

Install the updated requirements, then run from the project directory:

```bash
python3 chatbot.py --model llama3.2:1b --json-schema schemas/plan.json
python3 chatbot.py --model llama3.2:1b --json-schema schemas/tasks.json --json-attempts 2
```

For the first example, ask `Make a three-step plan to learn Python functions`.
For the second, ask `Extract tasks: fix login (high priority), update README (low priority)`.
The model must return the structure declared in the selected file. The schema is
sent through Ollama's `format` field and checked locally with `jsonschema`.

JSON responses are buffered until complete and valid; ordinary chat still streams.
Invalid content gets at most two total attempts by default (configurable from 1 to 5).
Rejected output and retry instructions never enter conversation history. Transport
errors and cancellation are not retried. After exhaustion, the chat remains usable.

This increment accepts draft 2020-12 inline schemas with a top-level object and no
`$ref`/`$dynamicRef` references. `format` annotations (such as email) are not asserted.
Validation verifies structure, not factual accuracy or permission to execute an action.
Both CLI examples passed on the user's local model (see docs/VERIFY.md).
Open `/structured` in the web service to extract tasks, create plans or define
custom fields, then complete checklist items and download validated JSON.
CLI equivalents start with `/extract tasks <text>` and `/extract plan <goal>`.
Results persist across restarts. Structured generation requires a real Ollama model
and does not fall back to stub output. See [the workflow and verification guide](docs/STRUCTURED_WORKSPACE.md).
The new workflow's live acceptance walkthrough remains to be run in WSL.

## Files and architecture

- `chatbot.py`: CLI, prompt loading, session loop and direct HTTP streaming
- `prompts/system.txt`: editable assistant instructions
- `requirements.txt`: HTTP, web server and JSON Schema dependencies
- `structured/output.py`: reusable JSON validation and bounded correction loop
- `schemas/`: example plan and task-extraction schemas
- `tests/test_structured.py`: validation and retry boundary checks
- `file_access/reader.py`: bounded reads beneath an explicit workspace root
- `file_access/writer.py`: immutable save previews and approved create-only writes
- `docs/FILE_ACCESS.md`: T4 behavior, permission boundaries and manual checks
- `tests/test_chatbot.py`: local HTTP contract and error tests
- `docs/SCOPING.md`: full 28-feature scope, architecture, ownership and six-week plan for four members
- `docs/USER_STORIES.md`: stories and observable acceptance criteria
- `docs/VERIFY.md`: automated results and manual demo checklist
- `START.md`: installation from scratch, first launch, repeat launch and troubleshooting

`main()` loads configuration and the prompt. `run_chat()` owns history and terminal IO.
`stream_reply()` sends the message list and yields response text without managing history.
File access supports explicitly requested context and confirmed creation in the CLI.
There is no persistence, full RAG pipeline, existing-file editing or code execution yet.

## Read a project file (T4 first increment, Linux/WSL)

```bash
python chatbot.py --model llama3.2:1b --workspace examples
```

Then enter each line in the chat:

```text
/read project_notes.md
Which language and database does this project use?
/read ../README.md
/exit
```

The first command queues one file for the next question. The expected answer is
Python and SQLite. The traversal command must be rejected without a model call.
Paths are relative to `--workspace`; omit `--workspace` to disable file access.
Only `.txt`, `.md`, `.py` and `.json` UTF-8 files up to 16 KiB are allowed.
Absolute paths, `..`, hidden paths, symbolic links and hard-linked files are denied.
Creation requires the additional `--allow-create` flag described below.
Model-initiated tool calls are not implemented in this increment.

T4 also works with `--json-schema schemas/tasks.json`. Read `project_notes.md`,
then ask to extract the two tasks. Use `/clear` to discard all conversation and
pending file context. More details are in `docs/FILE_ACCESS.md`.

## Save an answer after confirmation (T4 / initial A3)

```bash
mkdir -p local-output
python chatbot.py --model llama3.2:1b --workspace local-output --allow-create
```

Ask a question, wait for its completed answer, then enter `/save answer.md`.
The CLI displays the exact path, UTF-8 byte count and full content preview. Type
`yes` to create the file; any other input, EOF or Ctrl+C cancels without creating it.
The `local-output/` folder is ignored by Git. To read the result, use `/read answer.md`.

Existing files, including symbolic links, cannot be overwritten. Only `.txt`, `.md`,
`.py` and `.json` files up to 16 KiB are allowed. Parent directories must already exist.
This is a synchronous CLI approval for creating a new file, not general agent approval,
editing, scheduling or publication. The model cannot approve its own output.

## Configurable CLI guardrails (EV2, member B)

```bash
python3 chatbot.py --model llama3.2:1b --guardrails guardrails/demo.json
```

Opt-in input/output phrase rules and email/international-phone redaction.
Enabled mode buffers responses before display and validates JSON again after
filtering. Normal CLI turns are sanitized before persistence and `/save`.
See [configuration, demos, tests and remaining scope](docs/GUARDRAILS.md).
Web endpoints, existing stored data and management commands are not covered yet.

## Live web search (T3, member B)

```bash
python3 chatbot.py --model llama3.2:1b --search-url http://127.0.0.1:8088
```

Enter `/search Python asyncio documentation` to search and answer with sources.
Requires a running SearXNG instance with JSON enabled. See
[local provider setup, demos and verification](docs/WEB_SEARCH.md).
Search snippets and URLs enter the conversation as untrusted evidence; the CLI
reports failed or empty searches without asking the model to invent results.
Works with `--guardrails`, file context, local RAG and structured JSON output.

## Tests

```bash
python3 -m unittest discover -s tests -v
```

Tests start an ephemeral localhost HTTP server and exercise the API contract.
They do not need Ollama and do not establish model answer quality. For real-model
verification use `docs/VERIFY.md`.

## Limits

History is in RAM and is lost at exit. We resend all completed turns; there is no
budgeting or summarization and very long sessions can exceed the model context.
The selected model controls response quality and may not reliably obey the prompt.
The timeout is an inactivity timeout, not a total generation time limit.
Input is one line per turn. All 28 catalogue entries remain in the planning scope.
B1 and A5 have CLI implementations; T5 is integrated into the CLI and both
example scenarios have user-reported real-model evidence. R1 and X1 are partial prototypes. The remaining features are planned.
The six-week plan and 56 user stories are in docs/.

## Web Service & Centralized Configuration

Sensai includes a FastAPI web service (`web/app.py`) providing a browser chat interface (`/`), observability dashboard (`/dashboard`), and a complete REST API connected directly to the real backend stores and core chat engine.

### Configuration via Environment Variables

All settings are centralized in `core/config.py` and can be overridden via environment variables or CLI flags:

| Variable | Description | Default |
| --- | --- | --- |
| `SENSAI_OLLAMA_HOST` | Fixed server-side Ollama HTTP URL (client cannot choose outbound host) | `http://localhost:11434` |
| `SENSAI_MODEL` | Default model name for web runs | `llama3.2:1b` |
| `SENSAI_MODE` | Runtime mode: `ollama` (real model) or `stub` (offline simulation) | `ollama` (auto-falls back if unreachable) |
| `SENSAI_DB` | Path to SQLite session database | `sensai_sessions.db` |
| `SENSAI_EVENTS_DB` | Path to SQLite observability event store | `sensai_events.db` |
| `SENSAI_PROMPTS_DB` | Path to SQLite prompt versioning store | `sensai_prompts.db` |
| `SENSAI_ARTIFACTS_DB` | Path to SQLite artifact store | `sensai_artifacts.db` |
| `SENSAI_SNAPSHOTS_DB` | Path to SQLite public snapshot store | `sensai_snapshots.db` |
| `SENSAI_WORKSPACE` | Root directory for workspace file read and write | `./workspace` |

### Running the Web Service

```bash
uvicorn web.app:app --host 127.0.0.1 --port 8000
```
Open `http://localhost:8000` for the Web Chat UI or `http://localhost:8000/dashboard` for metrics and prompt version inspection.

## Sources

Assignment: Sensai_bootstrap.pdf, Sensai_project.pdf, features_catalog.pdf supplied with the task.
API reference: https://docs.ollama.com/api/chat
Streaming: https://docs.ollama.com/api/streaming
Structured output: https://docs.ollama.com/capabilities/structured-outputs
Schema validation: https://python-jsonschema.readthedocs.io/en/stable/validate/
