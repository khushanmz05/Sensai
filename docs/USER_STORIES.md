# User Stories — Full Sensai Scope

Preliminary backlog: two stories for each of 28 features, 56 in total.
B1 and A5 are implemented in the CLI. T5 has an initial CLI integration, with
user-reported real-model passes for both examples (see VERIFY.md). Other stories describe planned or partial behavior.
Refine wording and acceptance criteria in week 1 and verify them before acceptance.

## B1-1 — Ask a question and a follow-up

As a developer using Sensai, I want to ask a question and a follow-up, so that I can explore a task through a continuous conversation.

Acceptance criteria:
- The scenario "ask a question and a follow-up" works through the shared backend with real data, without substituting a mock result.
- Select a model and prompt without code changes; stream responses; maintain history; report errors explicitly. The CLI still works after extracting the shared backend.
- The user can distinguish success from a dependency failure; completion is verified by a test or reproducible demonstration.

Owner: A. First integration target: week 1.

## B1-2 — Select a local model for my computer

As a developer using Sensai, I want to select a local model for my computer, so that I can work within my available hardware.

Acceptance criteria:
- The scenario "select a local model for my computer" works through the shared backend with real data, without substituting a mock result.
- Select a model and prompt without code changes; stream responses; maintain history; report errors explicitly. The CLI still works after extracting the shared backend.
- The user can distinguish success from a dependency failure; completion is verified by a test or reproducible demonstration.

Owner: A. First integration target: week 1.

## M1-1 — Resume yesterday's session

As a developer using Sensai, I want to resume yesterday's session, so that I can avoid rebuilding context manually.

Acceptance criteria:
- The scenario "resume yesterday's session" works through the shared backend with real data, without substituting a mock result.
- Restore messages and user preferences after restart; automatically inject the profile into context.
- The user can distinguish success from a dependency failure; completion is verified by a test or reproducible demonstration.

Owner: A. First integration target: week 1–2.

## M1-2 — Save my preferred language and explanation level

As a developer using Sensai, I want to save my preferred language and explanation level, so that I can avoid repeating my preferences.

Acceptance criteria:
- The scenario "save my preferred language and explanation level" works through the shared backend with real data, without substituting a mock result.
- Restore messages and user preferences after restart; automatically inject the profile into context.
- The user can distinguish success from a dependency failure; completion is verified by a test or reproducible demonstration.

Owner: A. First integration target: week 1–2.

## M2-1 — Continue a long session

As a developer using Sensai, I want to continue a long session, so that I can stay within the context window.

Acceptance criteria:
- The scenario "continue a long session" works through the shared backend with real data, without substituting a mock result.
- Show actual token counts for completed requests and an estimated budget before each request; replace older turns with a semantic summary at the threshold while preserving reference facts.
- The user can distinguish success from a dependency failure; completion is verified by a test or reproducible demonstration.

Owner: A. First integration target: week 3.

## M2-2 — Preserve decisions during compression

As a developer using Sensai, I want to preserve decisions during compression, so that I can avoid losing important project context.

Acceptance criteria:
- The scenario "preserve decisions during compression" works through the shared backend with real data, without substituting a mock result.
- Show actual token counts for completed requests and an estimated budget before each request; replace older turns with a semantic summary at the threshold while preserving reference facts.
- The user can distinguish success from a dependency failure; completion is verified by a test or reproducible demonstration.

Owner: A. First integration target: week 3.

## M3-1 — Remember the selected project version

As a developer using Sensai, I want to remember the selected project version, so that I can reuse the decision in later sessions.

Acceptance criteria:
- The scenario "remember the selected project version" works through the shared backend with real data, without substituting a mock result.
- The model initiates validated CRUD operations on facts and relationships in SQLite; records survive restart and are separate from the raw transcript.
- The user can distinguish success from a dependency failure; completion is verified by a test or reproducible demonstration.

Owner: A. First integration target: week 2.

## M3-2 — Correct an outdated decision

As a developer using Sensai, I want to correct an outdated decision, so that I can avoid relying on incorrect information.

Acceptance criteria:
- The scenario "correct an outdated decision" works through the shared backend with real data, without substituting a mock result.
- The model initiates validated CRUD operations on facts and relationships in SQLite; records survive restart and are separate from the raw transcript.
- The user can distinguish success from a dependency failure; completion is verified by a test or reproducible demonstration.

Owner: A. First integration target: week 2.

## M4-1 — Maintain a project specification

As a developer using Sensai, I want to maintain a project specification, so that I can produce an up-to-date deliverable.

Acceptance criteria:
- The scenario "maintain a project specification" works through the shared backend with real data, without substituting a mock result.
- The model emits validated section-level document edits; apply them atomically with a version check and preserve unrelated sections.
- The user can distinguish success from a dependency failure; completion is verified by a test or reproducible demonstration.

Owner: D. First integration target: week 3.

## M4-2 — Update one section after a review

As a developer using Sensai, I want to update one section after a review, so that I can preserve previously agreed sections.

Acceptance criteria:
- The scenario "update one section after a review" works through the shared backend with real data, without substituting a mock result.
- The model emits validated section-level document edits; apply them atomically with a version check and preserve unrelated sections.
- The user can distinguish success from a dependency failure; completion is verified by a test or reproducible demonstration.

Owner: D. First integration target: week 3.

## T1-1 — Call a custom project tool

As a developer using Sensai, I want to call a custom project tool, so that I can use project operations from the conversation.

Acceptance criteria:
- The scenario "call a custom project tool" works through the shared backend with real data, without substituting a mock result.
- Discover and call tools through real MCP, return results to the model and continue the response; demonstrate both a custom server and a preexisting third-party server.
- The user can distinguish success from a dependency failure; completion is verified by a test or reproducible demonstration.

Owner: B. First integration target: week 2.

## T1-2 — Connect a preexisting MCP tool

As a developer using Sensai, I want to connect a preexisting MCP tool, so that I can extend the assistant without rebuilding the integration.

Acceptance criteria:
- The scenario "connect a preexisting MCP tool" works through the shared backend with real data, without substituting a mock result.
- Discover and call tools through real MCP, return results to the model and continue the response; demonstrate both a custom server and a preexisting third-party server.
- The user can distinguish success from a dependency failure; completion is verified by a test or reproducible demonstration.

Owner: B. First integration target: week 2.

## T2-1 — Test a code example

As a developer using Sensai, I want to test a code example, so that I can verify the proposed solution works.

Acceptance criteria:
- The scenario "test a code example" works through the shared backend with real data, without substituting a mock result.
- Execute code in an isolated container with time and resource limits; return stdout and tracebacks to the model; demonstrate correction and another execution.
- The user can distinguish success from a dependency failure; completion is verified by a test or reproducible demonstration.

Owner: B. First integration target: week 3.

## T2-2 — Fix code using a traceback

As a developer using Sensai, I want to fix code using a traceback, so that I can receive a corrected and retested example.

Acceptance criteria:
- The scenario "fix code using a traceback" works through the shared backend with real data, without substituting a mock result.
- Execute code in an isolated container with time and resource limits; return stdout and tracebacks to the model; demonstrate correction and another execution.
- The user can distinguish success from a dependency failure; completion is verified by a test or reproducible demonstration.

Owner: B. First integration target: week 3.

## T3-1 — Find current documentation

As a developer using Sensai, I want to find current documentation, so that I can use recent information.

Acceptance criteria:
- The scenario "find current documentation" works through the shared backend with real data, without substituting a mock result.
- Run a real search query and inject results with URLs into context; report provider failures and unavailable network access explicitly.
- The user can distinguish success from a dependency failure; completion is verified by a test or reproducible demonstration.

Owner: B. First integration target: week 2.

## T3-2 — Compare web results with a local note

As a developer using Sensai, I want to compare web results with a local note, so that I can identify outdated material.

Acceptance criteria:
- The scenario "compare web results with a local note" works through the shared backend with real data, without substituting a mock result.
- Run a real search query and inject results with URLs into context; report provider failures and unavailable network access explicitly.
- The user can distinguish success from a dependency failure; completion is verified by a test or reproducible demonstration.

Owner: B. First integration target: week 2.

## T4-1 — Read files from the selected project

As a developer using Sensai, I want to read files from the selected project, so that I can inspect source code within permitted boundaries.

Acceptance criteria:
- The scenario "read files from the selected project" works through the shared backend with real data, without substituting a mock result.
- Check allowed roots and operation permissions before every read, create or edit; block traversal through .. and symlinks while allowing authorized operations.
- The user can distinguish success from a dependency failure; completion is verified by a test or reproducible demonstration.

Owner: B. First integration target: week 1–2.

## T4-2 — Save a result to an allowed folder

As a developer using Sensai, I want to save a result to an allowed folder, so that I can obtain a file without changing unrelated data.

Acceptance criteria:
- The scenario "save a result to an allowed folder" works through the shared backend with real data, without substituting a mock result.
- Check allowed roots and operation permissions before every read, create or edit; block traversal through .. and symlinks while allowing authorized operations.
- The user can distinguish success from a dependency failure; completion is verified by a test or reproducible demonstration.

Owner: B. First integration target: week 1–2.

## T5-1 — Obtain a structured plan

As a developer using Sensai, I want to obtain a structured plan, so that I can pass it to another component without manual parsing.

Acceptance criteria:
- With `--json-schema schemas/plan.json`, a plan contains a nonempty `goal` and a nonempty list of nonempty `steps`, with no extra properties.
- Invalid output is withheld and retried within `--json-attempts`; exhaustion reports an error and leaves history unchanged.
- A real local Ollama demonstration produces a valid plan; HTTP tests alone do not establish model quality.

Status: integrated into CLI on 10 October 2026; the user supplied a successful
real-model run for this example. Broader manual checks and shared web integration remain pending.

Owner: B. First integration target: week 1.

## T5-2 — Extract tasks in a machine-readable format

As a developer using Sensai, I want to extract tasks in a machine-readable format, so that I can import them into another tool.

Acceptance criteria:
- With `--json-schema schemas/tasks.json`, every extracted task has a nonempty `title` and a `priority` of low, medium or high; extra properties are rejected.
- Only validated JSON is displayed and committed to history; malformed JSON, missing fields and invalid priorities are rejected.
- A real local Ollama demonstration extracts the requested tasks; a connection failure is reported without retrying or changing history.

Status: integrated into CLI on 10 October 2026; the user supplied a successful
real-model run for this example. Broader manual checks and shared web integration remain pending.

Owner: B. First integration target: week 1.

## R1-1 — Answer a question using project documentation

As a developer using Sensai, I want to answer a question using project documentation, so that I can check the basis of the answer.

Acceptance criteria:
- The scenario "answer a question using project documentation" works through the shared backend with real data, without substituting a mock result.
- Implement ingestion, chunking, embeddings, local vector storage, top-k retrieval and context injection; source references must identify actual documents.
- The user can distinguish success from a dependency failure; completion is verified by a test or reproducible demonstration.

Owner: C. First integration target: week 2.

## R1-2 — Find the relevant part of study material

As a developer using Sensai, I want to find the relevant part of study material, so that I can avoid reviewing the entire corpus manually.

Acceptance criteria:
- The scenario "find the relevant part of study material" works through the shared backend with real data, without substituting a mock result.
- Implement ingestion, chunking, embeddings, local vector storage, top-k retrieval and context injection; source references must identify actual documents.
- The user can distinguish success from a dependency failure; completion is verified by a test or reproducible demonstration.

Owner: C. First integration target: week 2.

## R2-1 — Retrieve information for a selected version only

As a developer using Sensai, I want to retrieve information for a selected version only, so that I can avoid mixing incompatible versions.

Acceptance criteria:
- The scenario "retrieve information for a selected version only" works through the shared backend with real data, without substituting a mock result.
- Implement metadata filtering, reranking and per-chunk relevance scoring with rejection of irrelevant passages; verify these on a fixed query set.
- The user can distinguish success from a dependency failure; completion is verified by a test or reproducible demonstration.

Owner: C. First integration target: week 3.

## R2-2 — Exclude similar but irrelevant passages

As a developer using Sensai, I want to exclude similar but irrelevant passages, so that I can base answers on appropriate sources.

Acceptance criteria:
- The scenario "exclude similar but irrelevant passages" works through the shared backend with real data, without substituting a mock result.
- Implement metadata filtering, reranking and per-chunk relevance scoring with rejection of irrelevant passages; verify these on a fixed query set.
- The user can distinguish success from a dependency failure; completion is verified by a test or reproducible demonstration.

Owner: C. First integration target: week 3.

## A1-1 — Break research into actions

As a developer using Sensai, I want to break research into actions, so that I can solve tasks requiring several steps.

Acceptance criteria:
- The scenario "break research into actions" works through the shared backend with real data, without substituting a mock result.
- Bound the action-observation-next-action/final-answer loop by step limits; show brief action rationales, observations and the reason for stopping.
- The user can distinguish success from a dependency failure; completion is verified by a test or reproducible demonstration.

Owner: A. First integration target: week 2–3.

## A1-2 — Revise a decision after a tool result

As a developer using Sensai, I want to revise a decision after a tool result, so that I can adapt to verifiable observations.

Acceptance criteria:
- The scenario "revise a decision after a tool result" works through the shared backend with real data, without substituting a mock result.
- Bound the action-observation-next-action/final-answer loop by step limits; show brief action rationales, observations and the reason for stopping.
- The user can distinguish success from a dependency failure; completion is verified by a test or reproducible demonstration.

Owner: A. First integration target: week 2–3.

## A2-1 — Research and implement a task

As a developer using Sensai, I want to research and implement a task, so that I can combine specialized assistance.

Acceptance criteria:
- The scenario "research and implement a task" works through the shared backend with real data, without substituting a mock result.
- A coordinator delegates research, implementation and review to specialized agents; structured results share a task ID; enforce limits and handle an individual agent failure.
- The user can distinguish success from a dependency failure; completion is verified by a test or reproducible demonstration.

Owner: A. First integration target: week 4.

## A2-2 — Obtain an independent implementation review

As a developer using Sensai, I want to obtain an independent implementation review, so that I can find errors before accepting the result.

Acceptance criteria:
- The scenario "obtain an independent implementation review" works through the shared backend with real data, without substituting a mock result.
- A coordinator delegates research, implementation and review to specialized agents; structured results share a task ID; enforce limits and handle an individual agent failure.
- The user can distinguish success from a dependency failure; completion is verified by a test or reproducible demonstration.

Owner: A. First integration target: week 4.

## A3-1 — Approve a file modification

As a developer using Sensai, I want to approve a file modification, so that I can control changes to my project.

Acceptance criteria:
- The scenario "approve a file modification" works through the shared backend with real data, without substituting a mock result.
- Pause before sensitive actions and display the operation and exact arguments; rejection prevents execution; approval is bound to unchanged arguments.
- The user can distinguish success from a dependency failure; completion is verified by a test or reproducible demonstration.

Owner: B. First integration target: week 2.

## A3-2 — Reject an unwanted action

As a developer using Sensai, I want to reject an unwanted action, so that I can preserve the original project state.

Acceptance criteria:
- The scenario "reject an unwanted action" works through the shared backend with real data, without substituting a mock result.
- Pause before sensitive actions and display the operation and exact arguments; rejection prevents execution; approval is bound to unchanged arguments.
- The user can distinguish success from a dependency failure; completion is verified by a test or reproducible demonstration.

Owner: B. First integration target: week 2.

## A4-1 — Compare two prompts

As a developer using Sensai, I want to compare two prompts, so that I can choose using measured results.

Acceptance criteria:
- The scenario "compare two prompts" works through the shared backend with real data, without substituting a mock result.
- Timestamp and version prompts, compare them and support rollback; compare quality and latency on identical tasks. Git history alone is insufficient.
- The user can distinguish success from a dependency failure; completion is verified by a test or reproducible demonstration.

Owner: D. First integration target: week 2.

## A4-2 — Restore previous assistant behavior

As a developer using Sensai, I want to restore previous assistant behavior, so that I can recover from a poor prompt change.

Acceptance criteria:
- The scenario "restore previous assistant behavior" works through the shared backend with real data, without substituting a mock result.
- Timestamp and version prompts, compare them and support rollback; compare quality and latency on identical tasks. Git history alone is insufficient.
- The user can distinguish success from a dependency failure; completion is verified by a test or reproducible demonstration.

Owner: D. First integration target: week 2.

## A5-1 — Switch from explanation to review

As a developer using Sensai, I want to switch from explanation to review, so that I can test my understanding in the same conversation.

Acceptance criteria:
- The scenario "switch from explanation to review" works through the shared backend with real data, without substituting a mock result.
- Switch between at least two configurable personas during a session without losing history; define name, tone, role and scope outside source code.
- The user can distinguish success from a dependency failure; completion is verified by a test or reproducible demonstration.

Owner: D. First integration target: week 1.

## A5-2 — Customize a persona

As a developer using Sensai, I want to customize a persona, so that I can receive an appropriate tone and response scope.

Acceptance criteria:
- The scenario "customize a persona" works through the shared backend with real data, without substituting a mock result.
- Switch between at least two configurable personas during a session without losing history; define name, tone, role and scope outside source code.
- The user can distinguish success from a dependency failure; completion is verified by a test or reproducible demonstration.

Owner: D. First integration target: week 1.

## A6-1 — Receive a repeated explanation quickly

As a developer using Sensai, I want to receive a repeated explanation quickly, so that I can reduce waiting time and model load.

Acceptance criteria:
- The scenario "receive a repeated explanation quickly" works through the shared backend with real data, without substituting a mock result.
- Serve a semantically similar eligible query without another generation call; partition cache by user, persona, source version and prompt version; implement a threshold, TTL and invalidation.
- The user can distinguish success from a dependency failure; completion is verified by a test or reproducible demonstration.

Owner: C. First integration target: week 4.

## A6-2 — Receive a fresh answer after a source changes

As a developer using Sensai, I want to receive a fresh answer after a source changes, so that I can avoid stale information.

Acceptance criteria:
- The scenario "receive a fresh answer after a source changes" works through the shared backend with real data, without substituting a mock result.
- Serve a semantically similar eligible query without another generation call; partition cache by user, persona, source version and prompt version; implement a threshold, TTL and invalidation.
- The user can distinguish success from a dependency failure; completion is verified by a test or reproducible demonstration.

Owner: C. First integration target: week 4.

## A7-1 — Select examples suited to the task automatically

As a developer using Sensai, I want to select examples suited to the task automatically, so that I can receive more appropriate model behavior.

Acceptance criteria:
- The scenario "select examples suited to the task automatically" works through the shared backend with real data, without substituting a mock result.
- Automatically select few-shot examples or prompt variants; compare with a baseline on held-out tasks using a quality metric; record the result and prompt version.
- The user can distinguish success from a dependency failure; completion is verified by a test or reproducible demonstration.

Owner: C. First integration target: week 4.

## A7-2 — Measure the effect of a prompt improvement

As a developer using Sensai, I want to measure the effect of a prompt improvement, so that I can avoid adopting unverified changes.

Acceptance criteria:
- The scenario "measure the effect of a prompt improvement" works through the shared backend with real data, without substituting a mock result.
- Automatically select few-shot examples or prompt variants; compare with a baseline on held-out tasks using a quality metric; record the result and prompt version.
- The user can distinguish success from a dependency failure; completion is verified by a test or reproducible demonstration.

Owner: C. First integration target: week 4.

## EV1-1 — Compare response quality across versions

As a developer using Sensai, I want to compare response quality across versions, so that I can choose using reproducible scores.

Acceptance criteria:
- The scenario "compare response quality across versions" works through the shared backend with real data, without substituting a mock result.
- An LLM judge through Ollama scores relevance, coherence and source faithfulness; flag contradictory or unverifiable claims; compare with a small manually labelled set.
- The user can distinguish success from a dependency failure; completion is verified by a test or reproducible demonstration.

Owner: C. First integration target: week 3–4.

## EV1-2 — Identify an answer contradicting a document

As a developer using Sensai, I want to identify an answer contradicting a document, so that I can avoid treating an unsupported claim as fact.

Acceptance criteria:
- The scenario "identify an answer contradicting a document" works through the shared backend with real data, without substituting a mock result.
- An LLM judge through Ollama scores relevance, coherence and source faithfulness; flag contradictory or unverifiable claims; compare with a small manually labelled set.
- The user can distinguish success from a dependency failure; completion is verified by a test or reproducible demonstration.

Owner: C. First integration target: week 3–4.

## EV2-1 — Prevent a prohibited request from reaching the model

As a developer using Sensai, I want to prevent a prohibited request from reaching the model, so that I can follow the configured usage policy.

Acceptance criteria:
- The scenario "prevent a prohibited request from reaching the model" works through the shared backend with real data, without substituting a mock result.
- Configurable input and output checks block or redact selected categories and PII; apply protection to tools, logs, cache and publication; test allowed and blocked cases.
- The user can distinguish success from a dependency failure; completion is verified by a test or reproducible demonstration.

Owner: B. First integration target: week 4.

## EV2-2 — Redact personal information from a response

As a developer using Sensai, I want to redact personal information from a response, so that I can avoid disclosing protected categories of data.

Acceptance criteria:
- The scenario "redact personal information from a response" works through the shared backend with real data, without substituting a mock result.
- Configurable input and output checks block or redact selected categories and PII; apply protection to tools, logs, cache and publication; test allowed and blocked cases.
- The user can distinguish success from a dependency failure; completion is verified by a test or reproducible demonstration.

Owner: B. First integration target: week 4.

## EV3-1 — Find the cause of a failure

As a developer using Sensai, I want to find the cause of a failure, so that I can reproduce the problematic run.

Acceptance criteria:
- The scenario "find the cause of a failure" works through the shared backend with real data, without substituting a mock result.
- Store sanitized prompts, responses, tool calls, latency, tokens and errors with session/run/version IDs; show volume, latency, error rates and changes over time on a dashboard.
- The user can distinguish success from a dependency failure; completion is verified by a test or reproducible demonstration.

Owner: D. First integration target: week 1–4.

## EV3-2 — Detect deterioration after a prompt change

As a developer using Sensai, I want to detect deterioration after a prompt change, so that I can identify quality or performance regressions.

Acceptance criteria:
- The scenario "detect deterioration after a prompt change" works through the shared backend with real data, without substituting a mock result.
- Store sanitized prompts, responses, tool calls, latency, tokens and errors with session/run/version IDs; show volume, latency, error rates and changes over time on a dashboard.
- The user can distinguish success from a dependency failure; completion is verified by a test or reproducible demonstration.

Owner: D. First integration target: week 1–4.

## EV4-1 — Test malicious instructions in a document

As a developer using Sensai, I want to test malicious instructions in a document, so that I can discover attempts to bypass rules through sources.

Acceptance criteria:
- The scenario "test malicious instructions in a document" works through the shared backend with real data, without substituting a mock result.
- Maintain a reproducible suite covering jailbreaks, prompt injections and malformed inputs; report successful defenses, failures and repairs explicitly.
- The user can distinguish success from a dependency failure; completion is verified by a test or reproducible demonstration.

Owner: C. First integration target: week 1–5.

## EV4-2 — Test malformed tool output

As a developer using Sensai, I want to test malformed tool output, so that I can check robustness against invalid data.

Acceptance criteria:
- The scenario "test malformed tool output" works through the shared backend with real data, without substituting a mock result.
- Maintain a reproducible suite covering jailbreaks, prompt injections and malformed inputs; report successful defenses, failures and repairs explicitly.
- The user can distinguish success from a dependency failure; completion is verified by a test or reproducible demonstration.

Owner: C. First integration target: week 1–5.

## X1-1 — Chat in a browser

As a developer using Sensai, I want to chat in a browser, so that I can work without a terminal.

Acceptance criteria:
- The scenario "chat in a browser" works through the shared backend with real data, without substituting a mock result.
- A decoupled frontend uses the same backend as the CLI; provide streaming chat, token/context usage, agent selection and configuration; expose errors and cancellation.
- The user can distinguish success from a dependency failure; completion is verified by a test or reproducible demonstration.

Owner: D. First integration target: week 1–3.

## X1-2 — Change settings and monitor the budget

As a developer using Sensai, I want to change settings and monitor the budget, so that I can understand the limits of the current request.

Acceptance criteria:
- The scenario "change settings and monitor the budget" works through the shared backend with real data, without substituting a mock result.
- A decoupled frontend uses the same backend as the CLI; provide streaming chat, token/context usage, agent selection and configuration; expose errors and cancellation.
- The user can distinguish success from a dependency failure; completion is verified by a test or reproducible demonstration.

Owner: D. First integration target: week 1–3.

## X2-1 — Compare two versions of a question

As a developer using Sensai, I want to compare two versions of a question, so that I can preserve both conversation alternatives.

Acceptance criteria:
- The scenario "compare two versions of a question" works through the shared backend with real data, without substituting a mock result.
- Editing a previous message creates a new branch while preserving the original; cancellation stops the active run and allows immediate redirection.
- The user can distinguish success from a dependency failure; completion is verified by a test or reproducible demonstration.

Owner: A. First integration target: week 4.

## X2-2 — Stop a response and redirect it

As a developer using Sensai, I want to stop a response and redirect it, so that I can avoid waiting for unwanted generation.

Acceptance criteria:
- The scenario "stop a response and redirect it" works through the shared backend with real data, without substituting a mock result.
- Editing a previous message creates a new branch while preserving the original; cancellation stops the active run and allows immediate redirection.
- The user can distinguish success from a dependency failure; completion is verified by a test or reproducible demonstration.

Owner: A. First integration target: week 4.

## X3-1 — Download a result for a report

As a developer using Sensai, I want to download a result for a report, so that I can use the output outside the application.

Acceptance criteria:
- The scenario "download a result for a report" works through the shared backend with real data, without substituting a mock result.
- Export conversations and artifacts to JSON, Markdown and PDF; expose a selected snapshot through a real public no-auth URL; exclude internal logs and other sessions.
- The user can distinguish success from a dependency failure; completion is verified by a test or reproducible demonstration.

Owner: D. First integration target: week 4.

## X3-2 — Share a selected result through a link

As a developer using Sensai, I want to share a selected result through a link, so that I can show it without exposing the working session.

Acceptance criteria:
- The scenario "share a selected result through a link" works through the shared backend with real data, without substituting a mock result.
- Export conversations and artifacts to JSON, Markdown and PDF; expose a selected snapshot through a real public no-auth URL; exclude internal logs and other sessions.
- The user can distinguish success from a dependency failure; completion is verified by a test or reproducible demonstration.

Owner: D. First integration target: week 4.

## X4-1 — Clarify requirements through a form

As a developer using Sensai, I want to clarify requirements through a form, so that I can provide all required parameters.

Acceptance criteria:
- The scenario "clarify requirements through a form" works through the shared backend with real data, without substituting a mock result.
- The model emits a schema-defined question or form; the UI renders fields, validates answers and returns them to the same run; provide a CLI text equivalent.
- The user can distinguish success from a dependency failure; completion is verified by a test or reproducible demonstration.

Owner: D. First integration target: week 3.

## X4-2 — Select task constraints without a long exchange

As a developer using Sensai, I want to select task constraints without a long exchange, so that I can clarify the request and resume execution quickly.

Acceptance criteria:
- The scenario "select task constraints without a long exchange" works through the shared backend with real data, without substituting a mock result.
- The model emits a schema-defined question or form; the UI renders fields, validates answers and returns them to the same run; provide a CLI text equivalent.
- The user can distinguish success from a dependency failure; completion is verified by a test or reproducible demonstration.

Owner: D. First integration target: week 3.

## X5-1 — Receive a daily summary

As a developer using Sensai, I want to receive a daily summary, so that I can avoid starting a repetitive task manually.

Acceptance criteria:
- The scenario "receive a daily summary" works through the shared backend with real data, without substituting a mock result.
- Persist and run interval-based tasks with an explicit timezone; expose results/errors and disabling; prevent overlapping runs and restore jobs after restart.
- The user can distinguish success from a dependency failure; completion is verified by a test or reproducible demonstration.

Owner: A. First integration target: week 4.

## X5-2 — Run a periodic project check

As a developer using Sensai, I want to run a periodic project check, so that I can receive scheduled results on time.

Acceptance criteria:
- The scenario "run a periodic project check" works through the shared backend with real data, without substituting a mock result.
- Persist and run interval-based tasks with an explicit timezone; expose results/errors and disabling; prevent overlapping runs and restore jobs after restart.
- The user can distinguish success from a dependency failure; completion is verified by a test or reproducible demonstration.

Owner: A. First integration target: week 4.

