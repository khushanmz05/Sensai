# T3: live web search (member B)

`/search <query>` performs a real SearXNG query, prints source titles/URLs,
and asks the selected Ollama model to answer with the returned snippets.
Only the search query is sent to SearXNG, not the conversation or profile.
SearXNG forwards queries to its configured search engines. Ordinary messages
do not search. This is explicit user-triggered search, not model-selected MCP.

## Local provider in WSL

Requirements: Docker with Compose available from WSL, internet access for the
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
- This increment integrates the CLI. The existing web UI does not yet expose
  search. Automatic model tool selection is part of the remaining T1 work.

## Tests and current verification

```bash
python3 -m unittest discover -s tests -p 'test_web_search.py' -v
python3 -m unittest discover -s tests -p 'test_search_chat.py' -v
python3 -m unittest discover -s tests -p 'test_guardrails*.py' -v
```

The provider/context suite has 19 offline tests and passed on Windows on
2026-10-21. It uses the real parsing code with fake HTTP responses, not live search.
Eight CLI integration tests are included; their execution is pending in WSL
because this Windows runtime lacks the application's requests/jsonschema
dependencies. The prior EV2 increment was reported working by the user in WSL.
Real SearXNG/Ollama verification is pending; no live-search pass is claimed.
Docker Compose configuration validation and Python syntax compilation also passed.

## Provider references

- [SearXNG search API](https://docs.searxng.org/dev/search_api.html)
- [Container installation](https://docs.searxng.org/admin/installation-docker.html)
- [Server configuration](https://docs.searxng.org/admin/settings/settings_server.html)

The API uses `/search` with `q` and `format=json`. JSON must be enabled in
`search.formats`; the server secret can be supplied through `SEARXNG_SECRET`.
