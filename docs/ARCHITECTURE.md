# Architecture

## Component map

| Component | Responsibility | Source |
| --- | --- | --- |
| CLI | Commands, sessions, attachments and terminal interaction | [chatbot.py](../chatbot.py) |
| Web service | HTTP endpoints, run state, SSE and browser pages | [web/app.py](../web/app.py) |
| Shared chat | Context assembly, streaming, persistence and cache eligibility | [core/chat.py](../core/chat.py) |
| Sessions and profiles | Persistent conversation and user preferences | [session/](../session/) |
| Personas and prompts | Configurable roles and stored prompt versions | [persona/](../persona/), [prompts/](../prompts/) |
| Retrieval | Chunking, embeddings, vector/BM25 search and reranking | [retrieval/](../retrieval/) |
| Tool execution | MCP discovery, argument validation, approval and feedback loop | [mcp_tools/](../mcp_tools/) |
| Python runtime | Namespace isolation, syscall restrictions and execution limits | [sandbox/](../sandbox/) |
| Structured results | Schema validation, task/plan workflows and progress | [structured/](../structured/) |
| Content policy | Input/output rules and privacy filtering | [guardrails/](../guardrails/) |
| Quality | Answer evaluation, adversarial cases and prompt optimization | [evaluation/](../evaluation/), [optimization/](../optimization/) |
| Events and deliverables | Run records, sectioned artifacts, forms and snapshots | [events/](../events/), [artifacts/](../artifacts/), [forms/](../forms/), [export/](../export/) |

## A web turn today

1. `POST /api/runs` validates input, mode and enabled services. It loads the
   session, profile, persona and active prompt version.
2. The context builder combines the question, history, optional file and
   retrieved passages. Retrieved material is reference data, not instructions.
3. The selected mode generates a response: ordinary Ollama chat, live search
   followed by generation, or a bounded MCP tool loop. Structured generation
   validates a schema before releasing a result.
4. MCP actions may pause for one-use human approval. Tool observations return
   to the model; Python failures can trigger corrected, separately approved runs.
5. SSE carries response text and tool/approval events. Guardrails buffer model
   output when enabled. Completed turns are stored; failures and cancellations
   are not saved as successful answers.
6. Eligible RAG answers receive an advisory judge result. Run events, duration
   and token information feed the dashboard.

The CLI reuses chat, policy, tool and structured services, but still has its own
command loop and basic retrieval path. Do not assume perfect parity: `/clear`
starts a new persisted CLI session; web Clear removes the current session's
messages. The web RAG path uses advanced retrieval, while CLI document questions
use basic retrieval.

## What a message contains

| Context component | Current handling | Visibility |
| --- | --- | --- |
| System prompt | CLI file; web active prompt version or default | File/API and prompt comparison |
| Persona and profile | Added to the system context | Persona selector and profile API/CLI |
| Earlier messages | Loaded from the selected session | Chat history |
| User question | Validated input | Chat |
| File attachment | Added as untrusted content when supplied | CLI attachment notice / request data |
| RAG passages | Selected chunk text enters generation context | Events expose source/line/score metadata, not full chunk text |
| Web search evidence | Snippets, URLs and retrieval time | Source cards |
| MCP observations | Actual tool arguments and results | Tool cards and run events |

**Missing:** one inspectable, persisted snapshot of the exact assembled request
and all selected chunks for each turn. Dashboard events and prompt versions
provide pieces of this information; they are not a complete context inspector.
The instructor's pipeline/visibility requirement remains open.

## Storage and lifetime

Sessions, profiles, structured results, prompt versions, artifacts, snapshots and
events use SQLite. Their locations are listed in [configuration](CONFIGURATION.md).
Active runs and the web document index live in memory. Restarting the web process
loses active approvals and uploaded document vectors; saved conversations remain.
Sandbox files exist only for one execution and are cleaned up afterward.

## Deliberate boundaries

External results and documents are untrusted. Workspace paths and MCP arguments
are checked independently of model instructions. The sandbox has no project
mount or network. Approvals are per action, not blanket permission.

The local web service has no authentication or tenant isolation. Sharing a
localhost snapshot creates a local link, not an internet publication service.
General multi-agent delegation, scheduling, conversation branching and complete
artifact/form orchestration are not established by the current component map;
consult the [feature register](FEATURES.md).
