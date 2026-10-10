# Verification

## T4 read-only increment: 10 October 2026

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

## Current working copy: 10 October 2026

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
