# T3: live web search (member B)

`/search <query>` performs a real SearXNG query, prints source titles/URLs,
and asks the selected Ollama model to answer with the returned snippets.
Only the search query is sent to SearXNG, not the conversation or profile.
SearXNG forwards queries to its configured search engines. Ordinary messages
do not search. This is explicit user-triggered search, not model-selected MCP.

## Web chat and local provider without Docker

Run these commands in Ubuntu/WSL, from the project folder, one at a time. If the
CLI is showing `You>`, enter `/exit` first. The project `.venv` must exist.

**Terminal 1 — first installation and provider startup:**

```bash
source .venv/bin/activate
python -m pip install -r requirements.txt
python deploy/search/local.py --install
```

This installs official SearXNG revision `cff884f98b1141bb6d5d3f104094fddafba78ef1`
in `~/.cache/sensai-searxng`, with its own Python environment. Git and internet
are needed; Docker and sudo are not. Changed provider sources are refused instead
of overwritten. Keep the terminal open. On subsequent starts use:

```bash
python deploy/search/local.py
```

The demo provider binds to **127.0.0.1:8088** with debugging off. Do not expose it
to the network. Its random secret stays in memory; a cache-clearing warning on
restart is normal. The config uses Brave, DuckDuckGo and Google CSE.

**Terminal 2 — web chat:** stop any old web server on port 8000 with Ctrl+C in
its terminal, then open a new Ubuntu terminal in the project folder:

```bash
source .venv/bin/activate
export SENSAI_SEARCH_URL=http://127.0.0.1:8088
export SENSAI_GUARDRAILS=guardrails/demo.json
python -m uvicorn web.app:app --host 127.0.0.1 --port 8000
```

Open **http://localhost:8000**, refresh, choose **Mode → Web search** and an
installed model, for example `qwen3:0.6b`. Ollama must be running; download a
missing model with `ollama pull qwen3:0.6b` in another terminal. To keep MCP enabled,
install `requirements-mcp.txt` and also export
`SENSAI_MCP_CONFIG=configs/mcp.demo.json` before starting Uvicorn.

1. Send `Python asyncio TaskGroup official documentation` without `/search`.
2. Expect **Searching the web…**, then **Web sources** with clickable titles,
   snippets, fetch time and partial-engine warnings. The model answer follows.
3. Switch to **Ollama**, ask `Which source supports that?`: no new search occurs.
4. In **Web search**, try `Please steal passwords`: the demo policy rejects it
   before external search. Use **Stop** during a running query to cancel it.
5. Stop Terminal 1 with Ctrl+C and send a search query: expect `Search unavailable`,
   with no fake answer. Restart the provider and retry.

Only the filtered query goes to the provider, not history or local attachments.
The provider URL is server-owned. Without `SENSAI_SEARCH_URL`, search is disabled;
ordinary chat still works. Restart Uvicorn after changing environment variables.
Search mode never falls back to Stub. Web provider HTTP has a 15-second overall
deadline, a 1 MiB decoded-body limit, no redirects, and cancellation on Stop or
SSE disconnect. Empty/unusable results do not call the model. Failed/cancelled
turns are not saved as conversation turns; diagnostic events may remain.

Web search cannot be combined with structured schemas or `file_write` in one
request. The existing `file_read` API can attach a note when a workspace is
configured; the toolbar does not add a file picker. CLI comparison is below.

For a connection error check Terminal 1 and port 8088. For a model error check
`curl http://localhost:11434` and `ollama list`. If a port is occupied, stop its
old server first. For installation errors check Git/network and the pip output.
Upstream rate limits or challenges may require retrying later.

## Alternative provider: Docker Compose in WSL

Do not run this alongside the Python provider on port 8088. Requirements:
Docker with Compose available from WSL, internet access for the
image/search engines, and the existing Sensai Python environment and Ollama model.
With Docker Desktop, start it and enable WSL integration for your Ubuntu distro.
From the repository root:

```bash
export SENSAI_SEARCH_SECRET="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
docker compose -f deploy/search/compose.yaml up -d
docker compose -f deploy/search/compose.yaml logs --tail=40
```

The service listens on localhost port 8088. The supplied YAML enables JSON
responses, which SearXNG may otherwise reject with HTTP 403. No search API key
is required. The generated secret configures the local server; it is not an API key.
The example uses the current image tag; pin a tested image digest for reproducible
deployment. Container startup and real upstream connectivity must be verified locally.

Check the provider before starting the chatbot:

```bash
curl --fail --get 'http://127.0.0.1:8088/search' \
  --data-urlencode 'q=Python asyncio documentation' \
  --data-urlencode 'format=json'
```

Expect JSON containing `results`. An empty list can mean no matches; inspect
`unresponsive_engines` for engine failures. Do not mistake an HTML/CAPTCHA page
for working JSON access.

## Start Sensai

```bash
source .venv/bin/activate
python3 chatbot.py --model llama3.2:1b \
  --search-url http://127.0.0.1:8088 \
  --guardrails guardrails/demo.json
```

Use your installed model if different. Existing SearXNG instances are also
supported: pass their base URL or `/search` endpoint instead. Credentials in URLs,
query strings and fragments are rejected. Choose a trusted instance.

Options:

| Flag | Behavior |
| --- | --- |
| `--search-url` | Enables `/search`; omitted means no web search |
| `--search-results` | Maximum unique sources, 1–10; default 5 |
| `--search-timeout` | HTTP socket timeout in seconds; default 15 |

No automatic retries or alternate-provider fallback are made. The socket timeout
is not a strict overall deadline for a provider that continuously sends bytes.

## Demo scenarios

1. Enter `/search Python asyncio TaskGroup official documentation`.
   Confirm that source links appear and the answer uses the snippets.
2. Ask `Which source supports that?` as a normal next message. No new search
   occurs; the earlier evidence remains available in conversation history.
3. For local-note comparison, start with `--workspace examples` too,
   enter `/read project_notes.md`, then `/search Compare Python SQLite documentation with my project note`.
   Both the attached note and web snippets reach the model. With `--docs-dir`,
   local RAG results can also be added to the same turn.
4. Try `/search` alone: usage information, no provider/model call.
5. With the demo guardrails enabled, try `/search Please steal passwords`:
   policy refusal before any external search.
6. Stop the provider and try `/search Python docs`. Expect a search error and
   no generated answer pretending a search succeeded. Then send `Hello` to
   verify that ordinary chat still works.

To stop the provider (in the shell containing the exported secret):

```bash
docker compose -f deploy/search/compose.yaml down
```

In a new shell, generate/export `SENSAI_SEARCH_SECRET` again before Compose
commands. This local demo does not persist the secret in the repository.

## Evidence and boundaries

- Result URLs must use HTTP(S), have no credentials/control characters, and
  fit within 2048 characters. Duplicate URLs ignoring fragments are removed.
- Provider JSON is bounded to 1 MiB. Titles are limited to 200 characters and
  snippets to 1200, with at most 10 results. Search queries have a 500-character limit.
- HTML markup, scripts/styles and terminal controls are stripped from text.
- Search evidence is placed in the user turn as untrusted JSON data. A system
  rule tells the model to ignore instructions inside it and cite supplied URLs.
  This labeling is not a guarantee against prompt injection.
- The client reads search snippets, not the linked pages. It does not crawl or
  execute result URLs. Model-generated citations and factual accuracy still need
  checking; the console list identifies the actual provider results.
- Query, snippets, URLs and UTC fetch time are saved with a successful user turn,
  allowing follow-up questions and session reload. Failed/empty searches do not
  create a chat turn or call the model. Pending file attachments remain pending
  when search itself fails, so retrying can still use them.
- EV2 checks/redacts the query before the external search and all result fields
  before display/context/persistence. Its documented heuristic limitations apply.
  Filtering may make a URL unusable; privacy takes precedence in enabled mode.
- T5 still controls the JSON answer schema. Source URLs remain in the separately
  displayed evidence even when the schema has no citation field.
- CLI and web share the parser and evidence format. The browser renders text
  nodes and validates source links; it does not execute provider HTML. Output
  policy rules also apply to source fields. Search remains user-triggered, and
  is separate from the existing MCP tool selection.

## Tests and current verification

```bash
python3 -m unittest discover -s tests -p 'test_web_search.py' -v
python3 -m unittest discover -s tests -p 'test_search_chat.py' -v
python3 -m unittest discover -s tests -p 'test_guardrails*.py' -v
```

On 29 October 2026, the full suite passed **320 tests and 148 subtests**, no skips,
with one preexisting Pydantic warning (`python -m pytest tests -q`). New web/HTTP
tests cover sources, privacy, history, local notes, provider failures/empty results,
total deadlines, Stop/disconnect and cancellation between provider/model stages.

Real SearXNG and Ollama 0.40.2 / `qwen3:0.6b` checks passed in Ubuntu 24.04/WSL:
TaskGroup/SQLite/logging searches returned official Python sources; the CLI
combined a local project note with SQLite search results and answered Python/SQLite
with URLs in a follow-up. The browser displayed sources and a model answer, then
reported a real failure after the provider was stopped and recovered on restart.
Some runs reported partial engine failures. No Docker runtime pass is claimed.

This verifies source delivery, not every factual statement: browser answers
contained inaccurate technical claims despite real sources. Inspect source cards;
full-page reading, universal citation validation and model accuracy are not guaranteed.

Code: [provider](../web_search/provider.py), [context](../web_search/context.py),
[web integration](../web/app.py), [UI](../web/static/index.html),
[local launcher](../deploy/search/local.py),
[web tests](../tests/test_search_web.py), [async HTTP tests](../tests/test_web_search_async.py).

## Provider references

- [SearXNG search API](https://docs.searxng.org/dev/search_api.html)
- [Local Python entry point](https://docs.searxng.org/dev/quickstart.html)
- [Pinned source](https://github.com/searxng/searxng/tree/cff884f98b1141bb6d5d3f104094fddafba78ef1)
- [Container installation](https://docs.searxng.org/admin/installation-docker.html)
- [Server configuration](https://docs.searxng.org/admin/settings/settings_server.html)

The API uses `/search` with `q` and `format=json`. JSON must be enabled in
`search.formats`; the server secret can be supplied through `SEARXNG_SECRET`.
