# Feature register

Reviewed against **main `c0db73b` on 1 November 2026**. This is a delivery map,
not a grade prediction or a substitute for live acceptance.

| Status | Meaning |
| --- | --- |
| Available | A usable path exists in main for the stated scope; see limits and evidence. |
| Partial | Components or a subset of behavior exist, but the complete workflow has gaps. |
| Planned | No integrated implementation was found in this main revision. |

Every entry has two [user stories](USER_STORIES.md). A status describes the
implementation; passing all story criteria requires recorded evidence. In
particular, persona behavior and some live retrieval/quality checks still need
fresh validation even where the underlying workflow is available.

| ID | Capability | Status | Owner | Entry point / evidence |
| --- | --- | --- | --- | --- |
| B1 | Local chat | Available | A | [chat tests](../tests/test_chatbot.py) |
| M1 | Sessions and profiles | Available | A | [session tests](../tests/test_session_store.py) |
| M2 | Context budgeting and compression | Planned | A | [scope](SCOPING.md) |
| M3 | Structured memory | Planned | A | [scope](SCOPING.md) |
| M4 | Living artifacts | Partial | D | [artifact service](../artifacts/service.py) |
| T1 | MCP tools | Available | B | [MCP guide](MCP.md) |
| T2 | Sandboxed Python | Available | B | [sandbox guide](SANDBOX.md) |
| T3 | Live web search | Available | B | [search guide](WEB_SEARCH.md) |
| T4 | Permitted file access | Available | B | [file guide](FILE_ACCESS.md) |
| T5 | Structured results | Available | B | [structured workflow](STRUCTURED_WORKSPACE.md) |
| R1 | Document retrieval | Available | C | [retrieval guide](WEB_DOCUMENT_UPLOAD.md) |
| R2 | Advanced retrieval | Partial | C | [retrieval implementation](../retrieval/rag.py) |
| A1 | Reasoning and action loops | Partial | A | [MCP loop](../mcp_tools/runner.py) |
| A2 | Multiple agents | Planned | A | [scope](SCOPING.md) |
| A3 | Human approval | Available | B | [MCP approvals](MCP.md) |
| A4 | Prompt versions | Available | D | [version store](../prompts/versioning.py) |
| A5 | Personas | Available | D | [persona question set](PERSONA_CHECKS.md) |
| A6 | Semantic cache | Available | C | [cache tests](../tests/test_semantic_cache.py) |
| A7 | Prompt optimization | Partial | C | [quality guide](QUALITY.md) |
| EV1 | Answer evaluation | Available | C | [evaluation guide](EV1_EVALUATION.md) |
| EV2 | Content and privacy rules | Available | B | [guardrails](GUARDRAILS.md) |
| EV3 | Run monitoring | Partial | D | [event store](../events/store.py) |
| EV4 | Adversarial testing | Available | C | [attack report](ev4_adversarial_testing.md) |
| X1 | Browser interface | Available | D | [web service](../web/app.py) |
| X2 | Branching and interruption | Partial | A | [web run control](../web/app.py) |
| X3 | Export and sharing | Partial | D | [export service](../export/service.py) |
| X4 | Questions and forms | Partial | D | [form validation](../forms/service.py) |
| X5 | Scheduling | Planned | A | [scope](SCOPING.md) |

## Scope and remaining gaps

- **B1 — Local chat:** Direct Ollama chat with history and streaming. Guardrails and JSON modes intentionally buffer output.
- **M1 — Sessions and profiles:** SQLite sessions and profiles persist across restarts. They are distinct from autonomous fact memory.
- **M2 — Context budgeting and compression:** No integrated budget/compression path in the reviewed main revision. Work in another branch is not a released feature.
- **M3 — Structured memory:** Session/profile databases exist; model-driven CRUD of separate facts and relationships is not integrated.
- **M4 — Living artifacts:** Versioned section edits and exports exist through the API; autonomous model edits and a complete authoring UI remain incomplete.
- **T1 — MCP tools:** Real stdio MCP with a custom project server and an existing time server; model-selected calls, not merely text descriptions.
- **T2 — Sandboxed Python:** Linux/WSL, standard library, read-only filesystem and no network/process creation. Each run is bounded and separately approved.
- **T3 — Live web search:** User-triggered SearXNG queries provide snippets and URLs, not downloaded full pages. Search results do not guarantee answer accuracy.
- **T4 — Permitted file access:** Restricted workspace reads and approved create-only writes. Existing-file editing is not supported; the full save walkthrough is in CLI.
- **T5 — Structured results:** Tasks, plans and custom objects have real consumers: saved records, checklist progress and schema-valid JSON export. Instructor acceptance is still to confirm.
- **R1 — Document retrieval:** Text ingestion, real embeddings, vector retrieval and context injection exist. The web index is in memory; real embedding setup is required.
- **R2 — Advanced retrieval:** Hybrid search, rewriting, reranking, score rejection and library-level filters exist; user-facing filters and live comparative evidence remain incomplete.
- **A1 — Reasoning and action loops:** Bounded MCP action/observation loops and Python repair work. A separate general ReAct workflow is not merged into this main snapshot.
- **A2 — Multiple agents:** Persona switching is available; actual delegation among specialized agents is not integrated.
- **A3 — Human approval:** File creation and configured MCP actions pause for approval. Web approvals use one-use IDs and expire; rejection stops the turn.
- **A4 — Prompt versions:** Prompt creation, activation, rollback and comparison exist. Dashboard performance data is descriptive, not a controlled quality experiment.
- **A5 — Personas:** JSON-defined tutor/reviewer profiles and history-preserving switching exist. The new behavioral question pack still needs a recorded live run.
- **A6 — Semantic cache:** Eligible context-independent requests use similarity-based caching. Context-sensitive and guardrail-enabled requests bypass it; no TTL policy is implemented.
- **A7 — Prompt optimization:** Candidate generation, numerical scoring and selection exist. No held-out improvement report; instructor expectations concerning DSPy remain to clarify.
- **EV1 — Answer evaluation:** An Ollama judge evaluates eligible RAG answers. Scores are advisory; structured, non-RAG and guardrail-enabled runs are skipped.
- **EV2 — Content and privacy rules:** Configurable phrase rules and email/phone redaction cover supported boundaries. This is not universal moderation or prompt-injection protection.
- **EV3 — Run monitoring:** Events, latency, errors and token information are visible. Complete exact-context snapshots and uniformly exact token accounting are missing.
- **EV4 — Adversarial testing:** Attack scripts, result files and a report exist. Recorded failures remain visible; tests do not establish universal resistance.
- **X1 — Browser interface:** Chat, modes, personas, document upload, tool approvals, source cards and separate structured/dashboard pages exist. The full context inspector is pending.
- **X2 — Branching and interruption:** Interruption exists. Editing an earlier message into a separate preserved conversation branch is not integrated.
- **X3 — Export and sharing:** Local snapshots and JSON/Markdown/PDF export paths exist. An externally reachable no-auth publication link has not been demonstrated.
- **X4 — Questions and forms:** Form validation and response endpoints exist; model-generated forms, rendered interaction and a complete resume loop are not connected.
- **X5 — Scheduling:** No persistent job scheduler or recurring model-task execution is integrated in main.

## Cross-feature acceptance gaps

The web RAG toggle, full per-turn context inspector, held-out A7 report and
recorded persona behavior run remain open. The 30-minute demonstration is a
prepared runbook, not a completed rehearsal. See [mid-term follow-up](MIDTERM_FOLLOWUP.md).

Unmerged branches may contain additional work. Do not mark a feature released
until its integration and verification are visible in main. Update this register,
the linked stories and the verification record together when that happens.
