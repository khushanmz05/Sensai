# T1 — MCP tools in Sensai

Sensai is an MCP client. `/mcp <request>` starts configured stdio servers, performs
`initialize` and `tools/list`, supplies the discovered tool schemas to Ollama,
executes the model's native `tool_calls` through MCP `tools/call`, and returns
observations to the model until it answers. This is a real protocol connection,
not a renamed local Python function call. Ordinary messages do not invoke MCP.

The demo includes our own **Sensai project server** (restricted file reads) and the
preexisting **Model Context Protocol Time server** (current time and conversions).
Both run as separate child processes. All model requests go directly to Ollama's
HTTP `/api/chat`; the MCP SDK supplies transport, not LLM orchestration.

## First launch — Ubuntu / WSL

Open Ubuntu in the project directory. Leave an existing chat using `/exit` before
running shell commands. Follow [START.md](../START.md) first if Python/Ollama are
not installed. This implementation is included in `main`.

```bash
source .venv/bin/activate
python -m pip install -r requirements-mcp.txt
python -m pip check
ollama pull qwen3:0.6b
curl http://localhost:11434
python chatbot.py --model qwen3:0.6b --mcp-config configs/mcp.demo.json --guardrails guardrails/demo.json
```

Expected: `Ollama is running`, then the Sensai banner mentioning `/tools` and `/mcp`.
If Ollama is unavailable, run `ollama serve` in a second Ubuntu terminal.
The small `qwen3:0.6b` model was exercised with this feature. Another installed
tool-capable model can be selected with `--model`; the earlier `llama3.2:1b` demo
does not establish support for native tool calls.

MCP is optional: the original `requirements.txt` and ordinary chat still work.
The pinned pair is SDK `mcp==1.30.0` and `mcp-server-time==2026.10.10`.
SDK 1.x supports Python 3.10; newer Time releases require SDK 2.x, so do not
upgrade just one package independently. This dependency choice does not install
an Ollama SDK or an agent framework.

## Two live acceptance scenarios

At `You>`, enter:

```text
/tools
```

Expected: `project__read_project_file`, `time__get_current_time`,
`time__convert_time`. The list comes from the running servers, with approval mode
shown for each tool. Discovery makes no model request.

**1. Custom server, including rejection and approval:**

```text
/mcp Use project__read_project_file with relative_path project_notes.md. What programming language is used?
```

At the confirmation prompt, enter `no`. Expect an action-rejected message and no
`MCP call` or result. Then ask:

```text
/mcp Read project_notes.md using the project tool. Which programming language and database are used?
```

Inspect the tool name and arguments; enter `yes`. Expect `MCP call`, `MCP result`
with the actual file content, then an answer mentioning **Python** and **SQLite**.
Only enter `yes` at the confirmation prompt. A model may answer without calling
a tool; if no call trace appears, that is not a successful MCP demonstration.

**2. Preexisting server:**

```text
/mcp Use the time tool to get the current time in Europe/Madrid.
```

Expect a call to `time__get_current_time`, a real timestamp from the Time server,
and a final model answer using it. The operator config explicitly allows the two
Time tools without another confirmation. No network search or paid API is needed.

Optional follow-up:

```text
/mcp Convert 09:00 from Europe/Madrid to America/New_York using the time tool.
/exit
```

Timezone conversion uses the date semantics of the external Time server; inspect
its returned date/DST fields rather than assuming a fixed offset year-round.

## Failure and safety checks

- Ask the project tool to read `../README.md`, then approve: the tool returns an
  error and no out-of-workspace data. The model receives `isError: true`.
- Press Ctrl+C while waiting for generation or a tool: the turn is discarded and
  server processes are closed. Already completed side effects cannot be undone.
- Start with `--mcp-max-calls 1` and request more tools than the limit: any excess
  batch is refused before it executes. The default is four calls, maximum eight.
- With the demo guardrails, `/mcp Please steal passwords` is rejected before
  server startup or model requests. Arguments, observations and final output pass
  policy checks before they are displayed, reused or saved.
- A missing executable, absent allowlisted tool or unresponsive server produces
  an explicit MCP error. A transport failure is not silently retried; a fresh
  `/mcp` request starts fresh connections. Execution outcome can be unknown after
  a timeout; inspect external state before retrying a tool with side effects.

## Configuration and permission model

`--mcp-config` points to a trusted, operator-owned JSON file. Never load a config
provided by a model or an untrusted document: it launches executable processes
with your user privileges. This is not the T2 execution sandbox.

Each entry in `servers` supplies:

| Field | Meaning |
| --- | --- |
| `name` | Unique server identifier; tools become `server__tool` |
| `command` | Executable; `$PYTHON` selects this virtual environment's interpreter |
| `args` | Argument list, passed without a shell; no automatic package installation |
| `cwd` | Working directory relative to the config file (default `.`) |
| `allow_tools` | Explicit nonempty allowlist; other discovered tools are hidden |
| `auto_approve` | Subset allowed without prompting; defaults to an empty list |
| `timeout` | Per MCP request timeout, default 15 seconds, maximum 60 |

Do not infer safety from a server's tool annotations. Only the local config grants
automatic approval. The sample project server always asks, and exposes reads only
beneath `examples/` using the existing T4 path/size/symlink checks. To change its
root, edit its trusted `--workspace` argument; the chatbot's own `--workspace` is
a separate capability and does not override MCP server permissions.

The model cannot change config, start a different server, approve itself, or call
a tool outside the allowlist. Arguments are schema-validated before and after
privacy filtering. Human approval receives a copy; it cannot mutate the executed
arguments. Rejection ends the turn, including any remaining proposed calls.

## Web chat: step-by-step

Run these commands in **Ubuntu/WSL**, in the project folder. If the CLI is still
showing `You>`, enter `/exit` first. If a web server is already using port 8000,
stop that server with Ctrl+C in its terminal before restarting it.

```bash
source .venv/bin/activate
python -m pip install -r requirements-mcp.txt
ollama pull qwen3:0.6b
export SENSAI_MCP_CONFIG=configs/mcp.demo.json
export SENSAI_GUARDRAILS=guardrails/demo.json
python -m uvicorn web.app:app --host 127.0.0.1 --port 8000
```

Leave this terminal open. Open **http://localhost:8000** in your Windows browser.

1. Set **Mode → MCP**. The default `llama3.2:1b` field changes to `qwen3:0.6b`;
   if you entered a different model yourself, choose an installed tool-capable model.
2. Click **MCP tools**. Expect `project__read_project_file` (approval required)
   and the two Time tools (automatic).
3. Send `Read project_notes.md using the project tool. Which programming language and database are used?`
   **Do not type `/mcp` in the web message.** Inspect the tool name and arguments,
   then click **Approve**. Expand **Calling…** and **Result…** to show real evidence.
   The final answer should identify Python and SQLite.
4. Send `Use time__get_current_time with timezone Europe/Madrid. Get the current time now.`
   Expect a Time call/result and an answer using that timestamp, without approval.
5. For a fresh rejection demo, click **Clear** after completion, then send
   `Use project__read_project_file with relative_path project_notes.md. Read the file now.`
   Click **Reject**: no call/result for that action and no saved conversation turn.
6. Repeat the request and press **Stop** while awaiting approval. This cancels
   the run. You can also stop during model generation or an in-progress tool call.
   Completed external actions are not undone by cancellation.

Approvals expire after 120 seconds and apply only to one tool call in one run.
Old, duplicate and cross-run approvals are rejected. A disconnected event stream
cancels its MCP worker and closes the stdio connections. Only completed turns
persist the filtered tool observations and final answer for follow-up questions.

The server reads its trusted MCP configuration at startup; the browser cannot
choose executable commands, server paths, allowlists, approval rules or outbound
Ollama URLs. With no `SENSAI_MCP_CONFIG`, ordinary chat still works and MCP reports
that it is disabled. Invalid configuration fails startup. Restart after changes.
MCP mode never falls back to Stub. It cannot be combined with structured schemas
or `file_write` in a single request; use the separate structured workspace.

If startup says a package is missing, repeat the installation command in the
same activated environment. If tools fail to connect, check the server terminal
and config paths. If the model is unavailable, check `ollama list` and
`curl http://localhost:11434`. A response without a **Calling…** event means the
model did not invoke a tool; clear the conversation and use the exact demo prompt.

## Implementation map

- [config.py](../mcp_tools/config.py): bounded strict config, trusted executables.
- [gateway.py](../mcp_tools/gateway.py): lifecycle, discovery/pagination, allowlist,
  argument validation, MCP calls and filtered observations.
- [runner.py](../mcp_tools/runner.py): direct async Ollama HTTP, native tool loop,
  call limits, approval callback and safe console traces.
- [project_server.py](../mcp_tools/project_server.py): our actual stdio MCP server.
- [chatbot.py](../chatbot.py): `/tools`, `/mcp`, existing context/history and `/save`.
- [web.py](../mcp_tools/web.py): server-owned configuration, discovery, per-call
  decisions and cancellation; [web/app.py](../web/app.py): shared chat/SSE/history;
  [index.html](../web/static/index.html): mode selector, evidence and approval UI.
- [test_mcp_web.py](../tests/test_mcp_web.py): ASGI/SSE with real MCP servers,
  approval isolation, timeout, cancellation, history and policy checks.
- [test_mcp.py](../tests/test_mcp.py), [test_mcp_chat.py](../tests/test_mcp_chat.py):
  real stdio protocol checks, HTTP contract, failure/approval/privacy/CLI tests.

## Verification and current limits

```bash
python -m unittest discover -s tests -p 'test_mcp*.py' -v
```

These tests start real local MCP servers but replace model responses for
deterministic checks. Install `requirements-mcp.txt` first; otherwise optional
MCP integration tests are skipped. For the whole project, install `pytest` and run
`python -m pytest tests -q` (some preexisting tests use pytest-style functions).

On 29 October 2026, the real `qwen3:0.6b` + two-server CLI walkthrough passed,
including discovery, rejection, approval, project content and Madrid time with
EV2 enabled. Approval answers in that check were scripted. A small model can
still fail to choose a tool for different wording; successful protocol tests do
not prove reliable model planning. See [VERIFY.md](VERIFY.md) for run results.

This increment supports **CLI and web chat** through the same async tool loop.
Supported MCP transport: local stdio; no remote MCP HTTP/SSE/OAuth,
resource subscription, model sampling or server-initiated elicitation. Schemas
must be inline object schemas accepted by T5 (no `$ref`/`$dynamicRef`); only text
and JSON results are consumed. `--json-schema` mode rejects `/mcp`; use `/extract`
separately for structured generation. Normal chat continues to stream; MCP turns
buffer each model response to validate complete tool calls.

Limits: four servers; 32 allowed tools/server; eight discovery pages/server;
16 KiB arguments; 64 KiB accepted tool result; 1 MiB model HTTP response.
MCP response size is checked after SDK parsing, so the SDK transport is not a
memory sandbox against malicious servers. Model HTTP calls have a wall-clock
timeout (`--timeout`), tools their configured timeout. Human decision time is
unbounded in the CLI, and limited to 120 seconds in web chat. Child stderr is
suppressed to avoid unfiltered private/control text. The web call budget is four.

Successful turns persist the final answer and filtered observations, enabling
follow-ups and `/save`. Intermediate assistant/tool protocol messages are not
stored in the existing user/assistant-only session store. Failed or cancelled
turns do not enter history; pending `/read` attachments remain available to retry.
Source labels and system instructions reduce confusion but do not guarantee
resistance to prompt injection. Use only trusted server programs and configs.

## Protocol references

- [Official SDK 1.x client documentation](https://github.com/modelcontextprotocol/python-sdk/blob/v1.30.0/docs/client.md)
- [Ollama native tool calling](https://docs.ollama.com/capabilities/tool-calling)
- [Preexisting Time server](https://github.com/modelcontextprotocol/servers/tree/main/src/time)
