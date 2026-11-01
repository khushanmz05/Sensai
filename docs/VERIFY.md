# Verification

## T3 CLI and web: 29 October 2026

Branch `b-t3-search`, based on main `dc16e46`: **320 tests and 148 subtests**
passed in 37.05 seconds, no skips, one existing Pydantic warning. Eleven new tests
cover async HTTP errors/limits/deadline/cancellation, web sources/privacy/history,
local notes without sending them to search engines, empty/failed searches, and
Stop/disconnect at provider/model boundaries. These use controlled transports.

Real SearXNG revision `cff884f98b1141bb6d5d3f104094fddafba78ef1` ran in a separate
WSL Python environment. Queries returned official TaskGroup, SQLite and logging
documentation. Real `qwen3:0.6b` used a local note and SQLite web results, then
answered Python/SQLite with source URLs in a follow-up. Browser checks displayed
clickable sources and answers, a real error after stopping the provider, and
recovery after restarting it. Pressing Stop during a live browser search also
reached `Run cancelled`. The final config selects Brave, DuckDuckGo and
Google CSE. Some queries reported partial engine failures. Docker was unavailable.

Source delivery does not establish answer accuracy: the small model produced
inaccurate technical claims in browser answers. No universal citation checking,
full-page reading or prompt-injection guarantee is claimed. See WEB_SEARCH.md.

## T1 MCP: 29 October 2026

Web follow-up: the full suite passed **309 tests and 132 subtests** in 37.06
seconds, with no skips and the same existing Pydantic warning. Ten additional
ASGI/SSE tests use isolated databases, real stdio project/Time servers and
deterministic model messages. They cover disabled/incompatible modes, discovery,
approval and persisted observations, rejection, duplicate/cross-run approvals,
120-second approval expiry (shortened in the test), Stop during approval and
model requests, event-stream disconnect cleanup, automatic Time calls, redaction
and blocked final answers.

Browser checks with the real `qwen3:0.6b` and EV2 enabled passed project-file
approval → real result → Python/SQLite answer, and an explicit
`time__get_current_time` request → matching Madrid timestamp. A generic time
request after a project conversation selected `convert_time` with invalid data;
the tool returned `isError: true` but the model incorrectly claimed success.
The UI exposes the real error (expanded with a warning), and the demo now names
the precise tool. This is evidence of the small model's planning/interpretation
limits, not a successful time demonstration. Do not trust final prose without
checking the tool result.

Browser Reject also ended the proposed file call without executing it. In a
fresh conversation, Stop during file approval reached `Run cancelled` and
disabled both decision buttons. A repeated file prompt in a time conversation
instead produced a reused time answer without a call; fresh-context demos and
visible tool evidence are therefore essential for this model.

The user also independently demonstrated CLI discovery, approved project reading,
Python/SQLite follow-up, current Madrid time and rejection after `/clear` in
pasted terminal logs on this date.

Earlier CLI-only verification:

Branch `b-mcp`, based on main `5750d6a`. With `requirements-mcp.txt` installed,
`python -m pytest tests -q` passed **299 tests** and **130 subtests** in 33.54 seconds
in Ubuntu 24.04 / WSL, with no skips. One existing Pydantic configuration
deprecation warning remains in `structured/api.py`. `pip check` and
`git -c core.whitespace=cr-at-eol diff --check` also passed (the existing CRLF line
endings in test_file_chat.py are preserved). There are 29 new MCP checks across
test_mcp.py and test_mcp_chat.py.

Before MCP changes, the same full collection had 269 passes and one failure:
test_file_chat expected a positional schema argument, while the current core
supplies it by keyword. That stale assertion was corrected without changing the
JSON/file behavior; the original 270 tests now pass alongside the MCP checks.

The new suite exercises real stdio initialization/discovery/calls against our
project server and the installed third-party Time server, traversal denial,
missing servers/tools, initialization timeout and child cleanup, cancellation of
a live call with process cleanup, tool error observations, argument validation,
allowlisting, bounded loops/results, policy filtering, HTTP failures, rejection,
and CLI history/save/recovery. Model transport in these automated tests is fake.

Separate live checks used Ollama 0.40.2, `qwen3:0.6b`, MCP SDK 1.30.0 and
`mcp-server-time` 2026.10.10. The model selected `project__read_project_file`, read
the actual project_notes.md through MCP and answered Python/SQLite. It selected
`time__get_current_time` in a second turn and used the returned Madrid timestamp.
A CLI walkthrough with EV2 enabled additionally exercised `/tools`, scripted `no`
and `yes`, rejection without a call, approval, both results and clean exit.
These are agent-run checks, not a substitute for the user's manual demo.

During the walkthrough, SDK cleanup wrapped the rejection exception and obscured
its message. The integration now preserves safe policy/rejection messages, with
a regression check. The 0.6B model also declined to select a tool for one prompt
wording; the final documented walkthrough succeeded. Do not claim model planning
is reliable for arbitrary wording. Remote MCP HTTP/SSE transports remain pending;
the web UI is covered by the newer verification above.
See [MCP.md](MCP.md) for reproducible commands, two stories and current limits.

## T4 creation and initial A3 approval: 10 October 2026

`python -m unittest discover -s tests -v` passed **97 tests** in 10.176 seconds
in WSL, with no skips. The prior 68 tests passed alongside 17 new creation-policy
checks and 12 CLI approval checks. Coverage includes rejected/expired decisions,
exact UTF-8 content, no-overwrite races, changed directories, temporary-file cleanup
after a flush failure, invalid/partial answers and model text that says `yes`.

An agent-run demonstration used local `llama3.2:1b`, `schemas/plan.json` and a
temporary workspace. Scripted CLI input exercised both confirmation outcomes:

1. The model returned a valid two-step JSON plan.
2. `/save cancelled.json` followed by `no` created no file.
3. `/save answer.json` followed by `yes` created the 187-byte JSON response.
4. Another `/save answer.json` was refused without overwriting it.
5. `/read answer.json` successfully loaded the saved content.

The saved JSON was parsed, the rejected path was confirmed absent, and no temporary
save files remained. The demonstration workspace was removed afterward. These
scripted checks do not substitute for a user's own manual approval demonstration.
Existing-file editing, model-selected tools, persistent approvals and web approval
are still pending; neither full T4 nor general A3 is claimed complete.

### User-reported manual save checks

The user supplied terminal output from WSL with `--workspace local-output
--allow-create` and `llama3.2:1b`:

- `/save answer.md` followed by `yes` reported creation of an 845-byte file.
- A second save also received `yes`, so it correctly created another file; a
  subsequent request answered with `no` reported cancellation without creation.
- Another `/save answer.md` reported that the target exists and overwriting
  is not allowed.

These outputs confirm the manual CLI paths for approval, rejection and overwrite
refusal. The model's explanation mixed languages; response quality is a separate
limitation and is not validated by the save operation. Generated answers remain
in the Git-ignored local-output directory.

## Previous T4 read-only increment: 10 October 2026

In the user's WSL working copy, `python -m unittest discover -s tests -v` passed
**68 tests** in 10.129 seconds, with no skips. This includes the prior 43 tests,
16 file-access boundary checks and 9 CLI file-context checks. `git diff --check`
also passed. Tests include directory replacement, symbolic/hard links, traversal,
file growth after the size check, FIFO handling, context clearing and T5 integration.

A direct agent-run CLI demonstration on the installed `llama3.2:1b` used
`--workspace examples --json-schema schemas/tasks.json`:

1. `/read ../README.md` was rejected by the path policy.
2. `/read project_notes.md` loaded the 232-byte sample file.
3. A request to extract the two tasks returned `Add a login screen (high priority)`
   with `high`, and `Update the README (low priority)` with `low`.
4. T5 schema validation passed and the chat exited normally.

This validates one real-model integration example, not general model quality or
prompt-injection resistance. Full T4 remains incomplete: write/create operations,
model-selected tool calls and shared web integration are pending. See FILE_ACCESS.md.

## Previous T5 increment: 10 October 2026

`python -m unittest discover -s tests -v`: **43 tests passed** (10.238 seconds).
The original 27 checks still pass; 16 new checks cover the T5 increment.

- JSON Schema is sent through the direct Ollama HTTP request.
- Validated output is committed; invalid output and correction instructions are not.
- Invalid syntax, field types, missing/extra fields and nested enum values fail validation.
- Retry limits, cancellation, transport failure, startup schema errors and history recovery are checked.
- Duplicate keys, non-finite numbers and trailing prose are rejected.
- Ordinary streaming chat, personas and chunking remain covered by existing tests.

Dependencies used for this run were installed in separate review folders, not shipped
inside the source archive. These tests use a fake local HTTP server, not a real model.
Both T5 examples now have user-supplied real-model evidence below; broader manual
acceptance and shared web integration remain pending.
The web UI and event contract have no dedicated automated tests in this copy.

## User-reported real-model examples: 10 October 2026

Evidence source: terminal output pasted by the user in this chat, not an independent
agent-run WSL session. Environment: WSL; reported Ollama version 0.40.2;
model argument `llama3.2:1b`.

- T5-1, `schemas/plan.json`: a Russian request for a three-step Python-functions
  study plan returned `goal` and exactly three string `steps`. CLI validation
  passed. The steps were repetitive and vague; this is a structure pass, not a
  claim of good pedagogical quality.
- T5-2, `schemas/tasks.json`: a request for exactly two tasks returned two items:
  `Исправить вход в систему с приоритетом high` with priority `high`, and
  `Обновить README с приоритетом low` with priority `low`. Both priorities and
  task meanings match the request. Priority wording is redundant in the titles
  but allowed by the schema.
- The earlier connection failure was reported without saving the turn; a later
  request succeeded. Empty input was explicitly rejected in the CLI.

These runs do not establish retry behavior on a real malformed model answer,
real-generation cancellation, broad semantic accuracy, or web integration.
Retries and cancellation remain supported by automated tests; complete the
remaining manual checklist before full feature acceptance.

## Historical bootstrap run

2026-09-21: Python 3.12.14, requests 2.34.2, 10 tests passed.
Command: `python3 -m unittest discover -s tests -v`

Verified using a local fake Ollama HTTP server plus injected connection/timeout errors:
- Separate UTF-8 content chunks and streaming request flag
- Full system/user/assistant history in the next request
- No HTTP request for empty input
- Explicit model-not-found message
- Discarded partial turn after premature stream termination
- Reported error inside a stream
- Clear command retains the system prompt
- Explicit connection and timeout errors
- Cancelled generation does not alter history

This environment has no Ollama installation/model. Real inference, model quality,
GPU/CPU performance and actual Ollama compatibility must be checked on each member's machine.
No real-model pass is claimed.

## Manual checklist for every group member

1. Install Ollama, pull the chosen model and verify `curl http://localhost:11434`.
2. Run `python3 chatbot.py --model llama3.2:1b` (or your installed model).
3. Ask for a long explanation. Observe text arriving progressively.
4. Say `My name is Mark`; then ask `What is my name?`. Inspect contextual answer.
5. Submit a blank line. Check the explanation and continued input.
6. Run with `--model definitely-missing-sensai-model`. Send a question; check the pull hint.
7. Run with `--host http://127.0.0.1:1`. Send a question; check connection error.
8. Create a separate prompt file with a distinctive instruction, pass its path via
   `--system-prompt`, and observe the changed behavior. Model compliance is not guaranteed.
9. Pass a nonexistent prompt file. Check startup fails cleanly with exit code 1.
10. Interrupt a long answer using Ctrl+C. Ask a new question and check normal recovery.
11. Try `/clear`, `/exit`, and EOF at the prompt.
12. Record your machine, model, Ollama version and real-model result in the team's notes.

## Short bootstrap demonstration

Show the prompt file and startup model argument. Ask a programming question and a
follow-up, pointing out progressive output and retained context. Demonstrate an empty
input and one connection/model error. Explain the three function responsibilities.
Finish with SCOPING.md, clearly distinguishing delivered B1 from future proposals.
