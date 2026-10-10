# SENSAI — Full Scope and Preliminary Six-Week Plan

Plan version: 21 September 2026. Team: four members. Duration: six weeks.
Weeks are relative to the actual team start date; no calendar deadline has been supplied.

## 1. Goal and boundaries

Implement **all 28 catalogue entries: B1 and 27 additional features** in one application.
This is the plan for the complete Sensai project, including its bootstrap foundation.
The full-catalogue scope follows the team's instruction and replaces the earlier M1/R1/A5-only proposal.

Proposed product: **Sensai, a local assistant for software project work**.
The user is a student or developer who reads documentation, clarifies requirements,
plans work, creates and tests code examples, records decisions and shares results.
This provides one coherent scenario for all features. The team can refine the domain
in week 1 while retaining the full catalogue.

Problem: a basic chat does not connect project files, long-term memory, code testing,
sources and a final document into one repeatable workflow. Sensai uses one shared backend.

**Current state (10 October 2026):** B1 and A5 are implemented in the CLI. T5 has
an initial CLI integration with schema validation and bounded retries. Both CLI
examples passed in user-reported real-model runs; broader acceptance remains pending. R1 has chunking only; X1 streams simulated responses using
the event contract. The other features below are planned. See VERIFY.md for tests.
T4 has a read-only CLI increment: an explicit workspace, bounded text reads and
file context. Writes/creation, model-selected file tools and shared web integration
remain planned; T4 is not fully accepted.
The current collaborator has chosen member B; other member names are unconfirmed.

Assignment constraints: Python 3.10+; all model calls must use the Ollama HTTP API directly,
including embeddings, agents, evaluation and prompt optimization. Do not use LangChain,
LlamaIndex, Haystack or equivalent LLM frameworks. Utility libraries for HTTP, databases,
web interfaces, JSON Schema, MCP transport and testing are allowed; implement orchestration ourselves.

## 2. Responsibilities

A/B/C/D are temporary labels to replace with team member names at kickoff.
The owner delivers implementation, tests, documentation and a feature demonstration.
The reviewer checks the code and must be able to explain it during the defense.

| Member | Main area | Features | Reviewer |
|---|---|---|---|
| A | Core, memory, task execution | B1, M1, M2, M3, A1, A2, X2, X5 | B |
| B | Tools, permissions, safety | T1–T5, A3, EV2 | A |
| C | Retrieval, quality, optimization | R1, R2, A6, A7, EV1, EV4 | D |
| D | Interface, documents, observability | M4, A4, A5, EV3, X1, X3, X4 | C |

D defines events with A in week 1; C defines document formats with B; B defines tool
calls with A. Reviews do not replace ownership. Integrate every week rather than
waiting until all individual implementations are complete.

## 3. Complete feature register

Week means the target for the first integrated result. EV3 and EV4 develop incrementally
from week 1. Full catalogue acceptance happens in week 5. Person-day estimates describe
preliminary owner effort, not the difficulty ratings in the assignment PDF.

| ID | Feature | Owner | Week | Dependencies | Person-days |
|---|---|---|---|---|---:|
| B1 | Functional CLI chatbot | A | 1 | — | 1 |
| M1 | Session Persistence & Profiles | A | 1–2 | B1 | 2 |
| M2 | Token Budgeting & Semantic Compression | A | 3 | M1; EV3 metrics | 3 |
| M3 | External Structured Memory | A | 2 | M1, T5, T4 | 3 |
| M4 | Artifact & State Document | D | 3 | T5, T4, A3 | 3 |
| T1 | MCP | B | 2 | T5; basic tool loop | 4 |
| T2 | Sandboxed Code Execution | B | 3 | T4, A3, A1 | 4 |
| T3 | Web Search | B | 2 | T5; basic tool loop | 2 |
| T4 | File Access within Permissions | B | 1–2 | B1 | 2 |
| T5 | Structured Output | B | 1 | B1 | 1 |
| R1 | Basic RAG | C | 2 | T4; Ollama embeddings | 4 |
| R2 | Advanced RAG | C | 3 | R1, T5 | 3 |
| A1 | Reasoning Loops (ReAct) | A | 2–3 | T5; T1/T2 contracts | 3 |
| A2 | Multi-Agent Orchestration | A | 4 | A1, A5, T5 | 3 |
| A3 | Human-in-the-Loop | B | 2 | T5, T4 | 2 |
| A4 | Prompt Versioning | D | 2 | M1; EV3 metrics | 2 |
| A5 | Persona | D | 1 | B1 | 1 |
| A6 | Semantic Cache | C | 4 | R1; A4 versions; M1 profile | 2 |
| A7 | Automated Prompt Optimization | C | 4 | A4, EV1, R1 | 3 |
| EV1 | Automated Eval & Hallucination Detection | C | 3–4 | R1, R2, T5; EV3 metrics | 3 |
| EV2 | Content & Privacy Guardrails | B | 4 | T4, T5; event stream | 3 |
| EV3 | Logging & Monitoring Dashboard | D | 1–4 | B1 events; extend with T1/A1 | 3 |
| EV4 | Adversarial Testing | C | 1–5 | EV2, T4, A1; develop alongside them | 3 |
| X1 | Web UI | D | 1–3 | shared backend; EV3 events; A5 | 5 |
| X2 | Branching — Resume & Interrupt | A | 4 | M1; cancel/events X1 | 3 |
| X3 | Export & Publication | D | 4 | M1, M4, X1, EV2 | 3 |
| X4 | Questions & Forms | D | 3 | T5, X1; A3 pause/resume | 2 |
| X5 | Scheduling | A | 4 | M1, A1; EV3 events | 2 |

## 4. Verifiable feature boundaries

### B1 — Functional CLI chatbot

**Done when:** Select a model and prompt without code changes; stream responses; maintain history; report errors explicitly. The CLI still works after extracting the shared backend.

**Two user scenarios:** ask a question and a follow-up; select a local model for my computer. See `USER_STORIES.md` for complete stories and acceptance criteria.

### M1 — Session Persistence & Profiles

**Done when:** Restore messages and user preferences after restart; automatically inject the profile into context.

**Two user scenarios:** resume yesterday's session; save my preferred language and explanation level. See `USER_STORIES.md` for complete stories and acceptance criteria.

### M2 — Token Budgeting & Semantic Compression

**Done when:** Show actual token counts for completed requests and an estimated budget before each request; replace older turns with a semantic summary at the threshold while preserving reference facts.

**Two user scenarios:** continue a long session; preserve decisions during compression. See `USER_STORIES.md` for complete stories and acceptance criteria.

### M3 — External Structured Memory

**Done when:** The model initiates validated CRUD operations on facts and relationships in SQLite; records survive restart and are separate from the raw transcript.

**Two user scenarios:** remember the selected project version; correct an outdated decision. See `USER_STORIES.md` for complete stories and acceptance criteria.

### M4 — Artifact & State Document

**Done when:** The model emits validated section-level document edits; apply them atomically with a version check and preserve unrelated sections.

**Two user scenarios:** maintain a project specification; update one section after a review. See `USER_STORIES.md` for complete stories and acceptance criteria.

### T1 — MCP

**Done when:** Discover and call tools through real MCP, return results to the model and continue the response; demonstrate both a custom server and a preexisting third-party server.

**Two user scenarios:** call a custom project tool; connect a preexisting MCP tool. See `USER_STORIES.md` for complete stories and acceptance criteria.

### T2 — Sandboxed Code Execution

**Done when:** Execute code in an isolated container with time and resource limits; return stdout and tracebacks to the model; demonstrate correction and another execution.

**Two user scenarios:** test a code example; fix code using a traceback. See `USER_STORIES.md` for complete stories and acceptance criteria.

### T3 — Web Search

**Done when:** Run a real search query and inject results with URLs into context; report provider failures and unavailable network access explicitly.

**Two user scenarios:** find current documentation; compare web results with a local note. See `USER_STORIES.md` for complete stories and acceptance criteria.

### T4 — File Access within Permissions

**Done when:** Check allowed roots and operation permissions before every read, create or edit; block traversal through .. and symlinks while allowing authorized operations.

**Two user scenarios:** read files from the selected project; save a result to an allowed folder. See `USER_STORIES.md` for complete stories and acceptance criteria.

### T5 — Structured Output

**Done when:** Request schema-conforming JSON and validate it; retry invalid output within a limit or reject it without side effects.

**Two user scenarios:** obtain a structured plan; extract tasks in a machine-readable format. See `USER_STORIES.md` for complete stories and acceptance criteria.

### R1 — Basic RAG

**Done when:** Implement ingestion, chunking, embeddings, local vector storage, top-k retrieval and context injection; source references must identify actual documents.

**Two user scenarios:** answer a question using project documentation; find the relevant part of study material. See `USER_STORIES.md` for complete stories and acceptance criteria.

### R2 — Advanced RAG

**Done when:** Implement metadata filtering, reranking and per-chunk relevance scoring with rejection of irrelevant passages; verify these on a fixed query set.

**Two user scenarios:** retrieve information for a selected version only; exclude similar but irrelevant passages. See `USER_STORIES.md` for complete stories and acceptance criteria.

### A1 — Reasoning Loops (ReAct)

**Done when:** Bound the action-observation-next-action/final-answer loop by step limits; show brief action rationales, observations and the reason for stopping.

**Two user scenarios:** break research into actions; revise a decision after a tool result. See `USER_STORIES.md` for complete stories and acceptance criteria.

### A2 — Multi-Agent Orchestration

**Done when:** A coordinator delegates research, implementation and review to specialized agents; structured results share a task ID; enforce limits and handle an individual agent failure.

**Two user scenarios:** research and implement a task; obtain an independent implementation review. See `USER_STORIES.md` for complete stories and acceptance criteria.

### A3 — Human-in-the-Loop

**Done when:** Pause before sensitive actions and display the operation and exact arguments; rejection prevents execution; approval is bound to unchanged arguments.

**Two user scenarios:** approve a file modification; reject an unwanted action. See `USER_STORIES.md` for complete stories and acceptance criteria.

### A4 — Prompt Versioning

**Done when:** Timestamp and version prompts, compare them and support rollback; compare quality and latency on identical tasks. Git history alone is insufficient.

**Two user scenarios:** compare two prompts; restore previous assistant behavior. See `USER_STORIES.md` for complete stories and acceptance criteria.

### A5 — Persona

**Done when:** Switch between at least two configurable personas during a session without losing history; define name, tone, role and scope outside source code.

**Two user scenarios:** switch from explanation to review; customize a persona. See `USER_STORIES.md` for complete stories and acceptance criteria.

### A6 — Semantic Cache

**Done when:** Serve a semantically similar eligible query without another generation call; partition cache by user, persona, source version and prompt version; implement a threshold, TTL and invalidation.

**Two user scenarios:** receive a repeated explanation quickly; receive a fresh answer after a source changes. See `USER_STORIES.md` for complete stories and acceptance criteria.

### A7 — Automated Prompt Optimization

**Done when:** Automatically select few-shot examples or prompt variants; compare with a baseline on held-out tasks using a quality metric; record the result and prompt version.

**Two user scenarios:** select examples suited to the task automatically; measure the effect of a prompt improvement. See `USER_STORIES.md` for complete stories and acceptance criteria.

### EV1 — Automated Eval & Hallucination Detection

**Done when:** An LLM judge through Ollama scores relevance, coherence and source faithfulness; flag contradictory or unverifiable claims; compare with a small manually labelled set.

**Two user scenarios:** compare response quality across versions; identify an answer contradicting a document. See `USER_STORIES.md` for complete stories and acceptance criteria.

### EV2 — Content & Privacy Guardrails

**Done when:** Configurable input and output checks block or redact selected categories and PII; apply protection to tools, logs, cache and publication; test allowed and blocked cases.

**Two user scenarios:** prevent a prohibited request from reaching the model; redact personal information from a response. See `USER_STORIES.md` for complete stories and acceptance criteria.

### EV3 — Logging & Monitoring Dashboard

**Done when:** Store sanitized prompts, responses, tool calls, latency, tokens and errors with session/run/version IDs; show volume, latency, error rates and changes over time on a dashboard.

**Two user scenarios:** find the cause of a failure; detect deterioration after a prompt change. See `USER_STORIES.md` for complete stories and acceptance criteria.

### EV4 — Adversarial Testing

**Done when:** Maintain a reproducible suite covering jailbreaks, prompt injections and malformed inputs; report successful defenses, failures and repairs explicitly.

**Two user scenarios:** test malicious instructions in a document; test malformed tool output. See `USER_STORIES.md` for complete stories and acceptance criteria.

### X1 — Web UI

**Done when:** A decoupled frontend uses the same backend as the CLI; provide streaming chat, token/context usage, agent selection and configuration; expose errors and cancellation.

**Two user scenarios:** chat in a browser; change settings and monitor the budget. See `USER_STORIES.md` for complete stories and acceptance criteria.

### X2 — Branching — Resume & Interrupt

**Done when:** Editing a previous message creates a new branch while preserving the original; cancellation stops the active run and allows immediate redirection.

**Two user scenarios:** compare two versions of a question; stop a response and redirect it. See `USER_STORIES.md` for complete stories and acceptance criteria.

### X3 — Export & Publication

**Done when:** Export conversations and artifacts to JSON, Markdown and PDF; expose a selected snapshot through a real public no-auth URL; exclude internal logs and other sessions.

**Two user scenarios:** download a result for a report; share a selected result through a link. See `USER_STORIES.md` for complete stories and acceptance criteria.

### X4 — Questions & Forms

**Done when:** The model emits a schema-defined question or form; the UI renders fields, validates answers and returns them to the same run; provide a CLI text equivalent.

**Two user scenarios:** clarify requirements through a form; select task constraints without a long exchange. See `USER_STORIES.md` for complete stories and acceptance criteria.

### X5 — Scheduling

**Done when:** Persist and run interval-based tasks with an explicit timezone; expose results/errors and disabling; prevent overlapping runs and restore jobs after restart.

**Two user scenarios:** receive a daily summary; run a periodic project check. See `USER_STORIES.md` for complete stories and acceptance criteria.

## 5. Complete product architecture

| Component | Responsibility | Main contract | Owner |
|---|---|---|---|
| CLI / Web UI | Two interfaces to one backend | commands, forms, event stream | A / D |
| Application service | Start, resume and cancel runs; manage branches | session_id, branch_id, run_id | A |
| Context builder | Combine persona, profile, memory, sources, summary and question | messages and budget | A |
| Ollama gateway | Direct chat/embedding HTTP calls, errors and metrics | stream_chat(), embed() | A, C |
| Agent coordinator | Route between researcher/coder/reviewer and run action loops | task to actions/result | A |
| Tool gateway / MCP | Tool registry, argument validation, calls and results | ToolCall / ToolResult | B |
| Policy / Approval | File permissions, guardrails and action approval | allow / deny / await_approval | B |
| Sandbox runner | Execute Python under resource limits | code to stdout/stderr/exit_code | B |
| Session / Memory store | History, branches, profiles and structured facts | SQLite and record versions | A |
| Retrieval / Cache | Ingestion, search, reranking, sources and semantic cache | query to passages/cached answer | C |
| Artifact service | Section edits and document versions | validated patch and expected_version | D |
| Prompt / Persona registry | Personas, prompt versions, rollback and comparison | persona_id and prompt_version | D |
| Evaluation / Optimization | Judge, adversarial suite, example selection and comparison | dataset to scores/report | C |
| Events / Dashboard | Metrics and sanitized structured logs | events sharing a run_id | D |
| Export / Share | Export and publish a selected snapshot | snapshot_id to files/public URL | D |
| Scheduler | Persistent jobs executed through the application service | job_id, interval, timezone | A |

Proposed stack: Python and FastAPI for the shared backend, SQLite for state, a simple
React frontend, SSE for event streaming and ordinary HTTP commands for control.
The CLI remains a required working interface. For a small corpus, use locally stored
vectors and cosine similarity without a separate distributed service. Use Docker for
the sandbox and JSON Schema for tool arguments and structured results. Select and pin
specific dependency versions, models and a web-search provider after week 1 checks.
These are architectural plans, not components already added to the bootstrap.

### Request flow

1. The CLI or UI submits a request to the application service, which creates a run_id.
2. Check input, session access and privacy policy.
3. Load the branch, profile, persona and prompt version. Check the context-dependent
   semantic cache for an eligible read-only request.
4. On a cache miss, retrieve sources and assemble context. Compress old turns if
   necessary, reserving space for the answer and tool results.
5. The coordinator calls Ollama. Validate tool requests and check permissions;
   pause for human approval when required.
6. MCP, search, memory or the sandbox returns a result. Continue until a final answer
   or a step, time or token limit is reached.
7. Apply output guardrails before displaying text; persist completed results.
   Document edits must pass schema and version checks.
8. Correlate actions through logs and metrics. Quality evaluation may run separately
   to avoid delaying every ordinary response.

Cached answers also pass current output checks. Requests involving actions, live web
information or incompatible private context must not receive stale cached results.

### Contracts to freeze in week 1

- Message: id, parent_id, branch_id, role, content, status. Partial/cancelled output
  is not a completed answer. Each branch has its own history path.
- Run: id, status, cancellation token, limits. Statuses include running,
  awaiting_input, awaiting_approval, completed, cancelled and failed.
- Event: run_id, sequence, type, payload, timestamp. Types include text_delta,
  tool_call, tool_result, approval_request, form_request, metrics, error and done.
- ToolCall: call_id, name, validated arguments. ToolResult: call_id, status, content.
- Passage: document_id, chunk_id, text, metadata, score. Citations refer to these IDs.
- ArtifactPatch: artifact_id, expected_version, section_id, operation, value.
- EvalResult: case_id, model, prompt_version, per-metric scores, flags, latency.

### Dependencies affecting delivery

T5 → T1/A3 → A1 → A2 and T2. T4 → safe R1 ingestion and file operations.
R1 → R2 → EV1 → A7. A4 also provides reproducible prompt versions for A7.
M1 and EV3 metrics → M2; M1 and run control → X2/X5.
T5 + T4 + A3 → M4 → X3. Shared backend and events → X1 → X4/X3.
A5 defines personas; A2 additionally requires real delegation, not just a prompt switch.

Do not wait for every dependency before starting: define contracts and small stubs in
week 1. Accept a feature only after testing with its real dependencies.

## 6. Weekly plan by team member

### Week 1 — Foundation and technical risk checks

| Member | Work | End-of-week result |
|---|---|---|
| A | Check B1 on every machine; extract shared backend; define Run/Message/Event; start M1 and SQLite schema | Working CLI over shared core; basic session save/load |
| B | T5, T4 foundation, tool contract; test MCP handshake and container execution | Validated JSON; allowed reads work and paths outside the root are blocked |
| C | Small .txt/.md corpus; embedding/retrieval prototype; 20–30 evaluation cases; initial EV4 cases | A query retrieves a known passage; reproducible checks are ready |
| D | X1 skeleton with streaming; A5; basic EV3 events; A4 structure | Browser displays streamed text; persona switch retains history; requests have run IDs |

Together: assign names to A–D, agree on the use case and user stories, benchmark models
on actual hardware, select a model suitable for tools/JSON and an embedding model,
choose a real search provider and a hosting approach for X3. The small bootstrap model
is not automatically suitable for all features. Check concurrent GPU access.

**Acceptance:** all members can run B1; CLI and browser share application logic;
request/tool/event contracts are fixed; small MCP, sandbox and embedding probes work.
**Evidence:** launch commands, a short demo recording, contract tests and latency
measurements. Resolve external services and access now, not in week 6.

### Week 2 — Memory, sources and tools

| Member | Work | End-of-week result |
|---|---|---|
| A | Complete M1; implement M3 and basic A1 with step limits/tool results | Profile and facts survive restart; model calls a tool and uses its result |
| B | Complete T1, T3, T4, A3; connect custom and preexisting MCP servers; establish T2 | Real MCP/search, approval and rejection; limited code execution prototype |
| C | Complete R1; start R2 filtering/reranking; label reference answers | Ingestion → embeddings → retrieval → answer with a verifiable source |
| D | A4, extend EV3, X1 settings/agents/context, approval UI | Prompt rollback and initial comparison; browser displays tools and pending approvals |

**Acceptance:** import a document, ask about it, receive a tool result, approve an
allowed action, restart and resume. A rejected action never executes. Test T1 with
both MCP servers.

### Week 3 — Execution, context budget and working documents

| Member | Work | End-of-week result |
|---|---|---|
| A | M2; complete A1; connect the loop to sandbox; start X2 branches | Long history compresses; code failure triggers a bounded correction attempt |
| B | Complete T2 and isolation; start EV2; check tool timeouts/cancellation | Code respects limits; stdout/traceback returns to the loop |
| C | Complete R2; initial working EV1; relevance and injection checks | Filtering, reranking and rejection work; judge flags an intentionally inserted contradiction |
| D | M4, X4; finish core X1; live metrics and document view | Form answers resume the waiting run; a section edit preserves other sections |

**Acceptance:** clarify a task through a form, find sources, generate and execute an
example, correct an error and update one document section. Separately demonstrate
history compression with preserved facts and a document version conflict.

### Week 4 — Full feature coverage

| Member | Work | End-of-week result |
|---|---|---|
| A | A2; complete X2; X5 with job recovery and no overlapping runs | Agent handoffs, two branches, cancellation and periodic execution after restart |
| B | Complete EV2; check permissions, approvals and cancellation across the system | Input/output rules cover chat, tools, logs and public exports |
| C | Complete EV1; A6; A7; expand EV4 to all connected paths | Cache hit without generation; measured baseline/optimized prompt comparison |
| D | X3: JSON/Markdown/PDF and real public URL; finish EV3; refine versions/forms | Externally accessible no-auth snapshot; dashboard compares versions and periods |

**Acceptance:** all 28 entries have a working integrated path and initial evidence.
Open a published snapshot in a separate browser without authentication. Run the full
demo scenario for the first time. Freeze new scenarios and extensions; unfinished
catalogue requirements remain mandatory.

### Week 5 — Integration and full acceptance

| Member | Work | End-of-week result |
|---|---|---|
| A | Test memory/branches/cancellation/scheduling after restart; loop limits and Ollama queue | No lost approvals, mixed branches or unbounded runs |
| B | Repair tools, sandbox, permissions and guardrails; retest both MCP servers | Allowed operations work; negative cases fail in a controlled way |
| C | Complete EV4 suite; manually cross-check EV1; measure retrieval/cache/optimization on holdout data | Versioned quality report with failures and repairs |
| D | End-to-end UI tests, cancellation/forms, exports/public URL, installation guide | Reproducible setup and readable documents; UI reflects actual state |

**Acceptance:** close every feature criterion and exercise at least two stories per
feature. Check catalogue requirements and error cases, not only successful paths.
Another member performs a clean installation from the README. Fix critical defects;
record remaining issues with impact and owner. Produce a release candidate.

### Week 6 — Stabilization and defense

| Member | Work | End-of-week result |
|---|---|---|
| A | Core fixes; explain architecture/memory; assemble release | Repeatable build and demo without manual database edits |
| B | Check demo environment, MCP, network and sandbox; prepare safe-action demonstration | Tool demo includes rejection, approval and error handling |
| C | Final evaluation report and reproducible metrics; explain RAG and limitations | Verifiable findings and an honest limitations list |
| D | README, evidence index and slides; check exports; record backup demo | Presentation materials, screenshots/video and a working public link |

Everyone: rehearse at least twice; each member explains at least one subsystem they
did not own. Finish outstanding mandatory-feature fixes early in the week, then focus
on regressions and blockers. Repeat the full run on the defense machine and pin models,
prompts and dependencies.

**Final acceptance:** source code, requirements, README, at least 56 user stories,
test instructions, reports, architecture and keynote agree with the current code.
The demonstration presents one connected system rather than unrelated scripts.

## 7. Capacity estimates and reserve

Working assumption: each member is available for approximately five full days per
week. This gives **120 person-days**, or 24 person-weeks, across the team. If classes
or other work reduce availability, recalculate available hours at kickoff; team size
alone does not establish feasibility. Refine estimates after week 1 prototypes.

| Work | A | B | C | D | Total person-days |
|---|---:|---:|---:|---:|---:|
| Feature implementation, including local checks | 20 | 18 | 18 | 19 | 75 |
| Contracts, reviews, integration and end-to-end checks | 5 | 7 | 7 | 5 | 24 |
| Documentation, clean setup and defense preparation/rehearsals | 3 | 3 | 3 | 3 | 12 |
| Reserve for discovered issues | 2 | 2 | 2 | 3 | 9 |
| **Total** | **30** | **30** | **30** | **30** | **120** |

The 75 implementation days nearly fill the first four weeks' capacity of 80 days.
Run integration checks from the start; concentrate full acceptance in week 5.
The reserve is small. This is an ambitious plan for an educational application with
a complete minimum implementation of every feature, not a promise of production reliability.

## 8. Risks and responses without dropping features

| Risk | Checkpoint | Response |
|---|---|---|
| Model struggles with tools or JSON | Week 1 | Compare candidates on identical probes; select and pin a working model |
| GPU cannot run agents, embeddings and judge concurrently | Weeks 1 and 3 | Queue calls, limit concurrency, run batch evaluations separately; A2 may execute sequentially |
| MCP or external search is unavailable | Week 1 | Make real calls early and select a provider/server; use test doubles only for automated tests |
| Prompt injection through files or web pages | From week 1 | Treat sources as data, validate tool actions independently, include attacks in EV4 |
| Private data leaks through streaming or logs | Before EV2/publication | Buffer output when a rule requires full-text inspection; check cache/exports and never log secrets |
| Inaccurate token estimates cause overflow | Week 3 | Use actual Ollama metrics, conservative pre-request estimates and reserved space; label estimates |
| UI cancellation does not stop an action | Weeks 3–5 | Propagate cancellation through all layers, stop processes/HTTP where possible and prevent subsequent actions |
| Conflicting edits or concurrent runs | Weeks 3–5 | Artifact versions, transactions and one active writer per branch |
| Prompt optimization overfits the tests | Week 4 | Separate development/holdout data and pin the model; claim improvement only when supported |
| Share link works only on localhost | Prepare week 2; accept week 4 | Use an externally accessible snapshot service and test without an account |
| Schedule slips | Every Friday | Reassign tasks, use reserve and simplify implementations while preserving complete criteria |

Do not silently remove catalogue features. Under pressure, limit supported formats
and variants: begin RAG with .txt/.md, support Python in the sandbox, use three fixed
A2 roles, a small set of X4 fields, interval-based X5 jobs and one search provider.
R2 must still include all three mechanisms; X3 must include export and real publication;
T1 must support custom and preexisting MCP; X2 must include branching and interruption.
Simpler visual styling is acceptable; replacing functionality with a static demo is not.

## 9. Coherent demonstration scenario

1. A developer opens a saved project and profile in CLI or web (B1, M1, X1, A5).
2. Clarify the task through a form; research local documentation and the web, filtering
   relevant sources (X4, R1, R2, T3).
3. Delegate researcher → coder → reviewer; call an MCP tool, test code in the sandbox
   and correct an error using its output (A1, A2, T1, T2, T5).
4. An allowed file change waits for approval, a forbidden path is rejected, a document
   section is updated and a decision enters structured memory (A3, T4, M3, M4).
5. Use a prepared long session to show budget/compression, then branching/cancellation
   (M2, X2). Repeat an eligible question to show a cache hit (A6).
6. Show prompt versions, optimization results, judge scores, adversarial report,
   guardrails and dashboard (A4, A7, EV1–EV4).
7. Schedule a regular check, export the result and open its public URL without signing
   in (X5, X3).

For long computations, prepare completed reports and a short live example. Label
backup video as a recording and simulated responses as test data; never present them
as live search or MCP. Confirm keynote duration with the instructor; the supplied
assignment does not specify it.

## 10. Working rules and definition of Done

- Start each week by confirming goals, owners, dependencies and actual availability.
- Daily update: result, next step and blocker. Discuss blockers lasting over one day
  with the whole team.
- Use small branches and reviewed pull requests; merge working code regularly.
  Rotate the weekly integration owner: A → B → C → D → A → B.
- Each Friday, run the system together and update a matrix linking feature, stories,
  test/demo evidence and status.
- A feature has at least two stories with observable acceptance criteria; both pass.
- It has implementation, shared-backend integration, relevant error/cancellation
  handling, tests and documentation.
- Evidence identifies a specific test, run result or demonstration step.
- Statuses: Planned → In progress → Integrated → Accepted. A feature name in the UI
  or a stub does not qualify as Accepted.

At kickoff, each member independently reads the catalogue and records interests,
concerns and suggestions. Then agree on architecture and ownership while preserving
the full required scope. This is a preliminary plan, not a fabricated record of a
completed team discussion.

Requirement sources: supplied Sensai_project.pdf, Sensai_bootstrap.pdf and
features_catalog.pdf; the user's instruction specifying four members, six weeks
and the full catalogue.
