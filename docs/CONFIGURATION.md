# Configuration and daily use

Run shell commands from the repository root with `.venv` active. Commands
starting with `/` in the CLI table below belong at Sensai's `You>` prompt.
Web environment variables are read at startup: restart the server after changing them.

## Terminal commands

| Command | Purpose |
| --- | --- |
| `/exit` | Leave Sensai |
| `/clear` | Start a new persisted session and discard pending file context |
| `/session list` / `/session use <id>` | List or resume saved sessions |
| `/session new <title>` / `/session rename <title>` | Create or name a session |
| `/profile` | Show preferences; the command also explains available edits |
| `/persona` / `/persona explainer` / `/persona reviewer` | List or switch personas without clearing history |
| `/read <relative-path>` | Attach a permitted workspace file to the next question |
| `/save <new-path>` | Preview and approve creation of a file containing the last result |
| `/tools` / `/mcp <request>` | Discover configured MCP tools or ask the model to use them |
| `/search <query>` | Request live web search when a provider is configured |
| `/extract tasks <text>` / `/extract plan <goal>` | Create a validated structured result |
| `/results` / `/result <id>` | List or reopen saved structured results |
| `/complete <id> <item>` / `/uncomplete <id> <item>` | Update checklist progress; item numbering starts at 1 |
| `/result <id> json` | Display schema-valid JSON for export |

## CLI startup options

Use `python chatbot.py --help` for the complete interface.

| Option | Meaning / default |
| --- | --- |
| `--model` | Required installed Ollama model |
| `--host` | Ollama URL; `http://localhost:11434` |
| `--system-prompt` | UTF-8 prompt file; `prompts/system.txt` |
| `--persona`, `--persona-dir` | Starting persona and JSON configuration directory |
| `--timeout` | Model stream inactivity timeout; 120 seconds |
| `--docs-dir` | Ingest `.txt`/`.md` files for basic RAG; omitted means no CLI RAG |
| `--workspace`, `--allow-create` | Enable restricted reads and optionally create-only writes |
| `--json-schema`, `--json-attempts` | Schema-constrained chat; 2 attempts by default, 1–5 allowed |
| `--guardrails` | Policy JSON file; opt-in |
| `--mcp-config`, `--mcp-max-calls` | MCP server config; 4 calls by default, 1–8 allowed |
| `--search-url` | SearXNG URL; omitted means search disabled |
| `--search-timeout`, `--search-results` | Provider timeout 15 seconds; up to 5 results by default |

## Web modes and optional services

| Mode / page | Requirement | Behavior |
| --- | --- | --- |
| Ollama | Running Ollama and selected model | Ordinary chat; RAG is used when available |
| MCP | `SENSAI_MCP_CONFIG`, `requirements-mcp.txt` | Native tool calls with configured approvals |
| Web search | `SENSAI_SEARCH_URL`, running SearXNG | Search snippets and sources followed by a model answer |
| Stub | Explicit simulation mode | Fake responses for UI development; never evidence of inference |
| Structured workspace | Ollama | Validated task lists, plans and custom objects |

Explicit Ollama requests fail visibly if the model service is unavailable. API
requests that omit the mode can fall back to stub; select a real mode explicitly
for demonstrations. MCP, search and structured generation do not use that fallback.

`configs/mcp.demo.json` enables project-file and time tools.
`configs/mcp.sandbox.json` enables only Python execution. The files are alternatives,
not additive settings; an operator can combine their server entries in a local
config. Each requires a server restart when selected. See [MCP](MCP.md) and
[sandbox](SANDBOX.md) for complete commands.

## Environment variables

| Variable | Default | Use |
| --- | --- | --- |
| `SENSAI_OLLAMA_HOST` | `http://localhost:11434` | Web generation host; falls back to `OLLAMA_HOST` |
| `SENSAI_MODEL` | `llama3.2:1b` | Web default model; falls back to `OLLAMA_MODEL` |
| `SENSAI_MODE` | `ollama` | Default web mode |
| `SENSAI_MCP_CONFIG` | Disabled | Trusted local MCP config path |
| `SENSAI_SEARCH_URL` | Disabled | Fixed server-side SearXNG URL |
| `SENSAI_GUARDRAILS` | Disabled | Server-owned privacy/content policy |
| `SENSAI_WORKSPACE` | Disabled | Workspace root for web file operations |
| `SENSAI_EVAL_MODEL` | Selected run model | Judge for eligible RAG answers |
| `SENSAI_SEMANTIC_CACHE_THRESHOLD` | `0.92` | Cosine-similarity threshold for eligible cache hits |

The UI's model field changes chat generation, not every auxiliary model.
Current RAG defaults are `nomic-embed-text` for embeddings and `qwen3` for web
query rewriting/reranking. Several retrieval calls still use the local Ollama
URL directly, so a custom generation host is not a complete retrieval-host override.
There is no web RAG on/off setting yet. See [retrieval](WEB_DOCUMENT_UPLOAD.md).

## Persistent data

| Variable | Default location |
| --- | --- |
| `SENSAI_DB` | `sensai_sessions.db` |
| `SENSAI_EVENTS_DB` | `sensai_events.db` |
| `SENSAI_PROMPTS_DB` | `sensai_prompts.db` |
| `SENSAI_ARTIFACTS_DB` | `sensai_artifacts.db` |
| `SENSAI_SNAPSHOTS_DB` | `sensai_snapshots.db` |
| `SENSAI_STRUCTURED_DB` | `sensai_structured.db` |
| `SENSAI_SEMANTIC_CACHE_DB` | `retrieval/semantic_cache.sqlite3` |

Core settings resolve default database paths from the repository. The default
semantic-cache path is relative to the working directory. Optimization history
is stored alongside the prompt database as `opt_history.sqlite3`.
Web document vectors are in memory, not in these persistent databases.

Back up local data before replacing a checkout. Database files and personal
demonstration notes are excluded from Git; they are not part of the team's source
distribution. No password, token or private document belongs in a shared config.
