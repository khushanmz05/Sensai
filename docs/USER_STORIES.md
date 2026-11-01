# User stories

**56 scenarios · 28 catalogue features · two scenarios per feature**

Sensai supports a software student's path from understanding a project to checking
an example and reusing the result. Each story states the user's benefit and three
observable acceptance checks. Repeated generic checklist text has been removed.

## How to use this backlog

- Search by feature tag (`T2`, `R1`, `A7`), surface (`CLI`, `web`, `API`) or owner.
- Keep story IDs stable when implementation changes.
- Criteria define the acceptance target; record the outcome of each check
  against its story ID.
- Use [FEATURES.md](FEATURES.md) as the compact feature/evidence index and
  [VERIFY.md](VERIFY.md) to record a result against a story ID.

## Coverage and navigation

| Area | Features and stories |
| --- | --- |
| Conversation | B1-1/2, M1-1/2, A5-1/2 |
| Memory and documents | M2-1/2, M3-1/2, M4-1/2 |
| Tools and structured work | T1-1/2, T2-1/2, T3-1/2, T4-1/2, T5-1/2, A3-1/2 |
| Retrieval | R1-1/2, R2-1/2 |
| Orchestration and optimization | A1-1/2, A2-1/2, A4-1/2, A6-1/2, A7-1/2 |
| Evaluation | EV1-1/2, EV2-1/2, EV3-1/2, EV4-1/2 |
| Interface and lifecycle | X1-1/2, X2-1/2, X3-1/2, X4-1/2, X5-1/2 |

## B1 — Local chat

`B1` `CLI` `owner-A` · [chat tests](../tests/test_chatbot.py)

### B1-1 — Ask a follow-up

As a programming student, I want to ask follow-up questions, so that I can learn without repeating the context.

- An installed model answers a question through the CLI.
- A follow-up includes the completed earlier exchange.
- Ordinary generation displays text progressively.

### B1-2 — Recover from a failed request

As a user, I want understandable errors, so that I can continue after a connection or model failure.

- An unavailable model produces an actionable error.
- Empty input makes no model request.
- A failed or cancelled answer is not added as a completed turn.

## M1 — Sessions and profiles

`M1` `CLI` `web` `API` `owner-A` · [session tests](../tests/test_session_store.py)

### M1-1 — Resume a study session

As a student, I want to reopen a saved conversation, so that I can continue yesterday's work.

- Save a completed question and answer.
- Restart and select the same session.
- The next request includes that session's history.

### M1-2 — Keep learning preferences

As a student, I want to save my language and explanation level, so that future answers fit my needs.

- Save preferences through the profile command or API.
- Reload them after restarting.
- The next system context includes the saved values.

## M2 — Context budgeting and compression

`M2` `CLI` `web` `owner-A` · [scope](SCOPING.md)

### M2-1 — Continue a long conversation

As a student, I want old context to be compressed, so that a long session remains usable.

- Show the estimated input budget before generation.
- Summarize older turns at a defined threshold.
- Reserve capacity for the answer without exceeding the configured budget.

### M2-2 — Retain key decisions

As a developer, I want compression to preserve decisions, so that the assistant does not contradict earlier constraints.

- Seed a long session with named decisions.
- Trigger compression and ask about those decisions.
- Compare retained facts with the reference list and record any loss.

## M3 — Structured memory

`M3` `CLI` `web` `owner-A` · [scope](SCOPING.md)

### M3-1 — Remember a project fact

As a developer, I want the assistant to store a project decision, so that it can reuse the fact in a later conversation.

- The model proposes a typed memory record.
- A validated operation persists it separately from the transcript.
- A new session retrieves the fact and its source.

### M3-2 — Correct an obsolete fact

As a developer, I want to correct stored knowledge, so that later answers use the current decision.

- Select the existing fact without duplicating it.
- Validate and persist its replacement.
- A later lookup returns the updated value and change history.

## M4 — Living artifacts

`M4` `API` `owner-D` · [artifact service](../artifacts/service.py)

### M4-1 — Update one document section

As a developer, I want the assistant to update a specification section, so that the deliverable stays current without losing other content.

- The model produces a parseable section edit.
- Apply it to the expected artifact version.
- Unrelated sections remain unchanged.

### M4-2 — Reject a conflicting edit

As a collaborator, I want outdated edits rejected, so that one update cannot silently overwrite another.

- Create two edits against the same version.
- Accept the first and reject the stale second edit.
- Show the current version and preserve the accepted content.

## T1 — MCP tools

`T1` `CLI` `web` `owner-B` · [MCP guide](MCP.md)

### T1-1 — Read through a project tool

As a developer, I want the assistant to consult a project file, so that its answer uses the file's actual contents.

- Discover the allowlisted project tool.
- Show arguments and request approval before execution.
- Return the real result to the model and display the call evidence.

### T1-2 — Use an existing server

As a distributed teammate, I want timezone information from a time tool, so that I can coordinate using a real result.

- Discover the preexisting time server through MCP.
- Call the requested timezone tool according to configured approval policy.
- Show its actual response before the model's final explanation.

## T2 — Sandboxed Python

`T2` `CLI` `web` `owner-B` · [sandbox guide](SANDBOX.md)

### T2-1 — Check a calculation

As a student, I want the assistant to execute a short Python program, so that I can check its numerical answer.

- Preview and approve the generated source.
- Execute it in the isolated runtime with time and memory limits.
- Show actual stdout, stderr and exit code.

### T2-2 — Verify a correction

As a student, I want the assistant to use a traceback, so that it fixes and reruns failing code.

- The first program returns a real error.
- The traceback reaches the model, which proposes a corrected program for approval.
- A successful rerun verifies the fix; the call limit prevents endless retries.

## T3 — Live web search

`T3` `CLI` `web` `owner-B` · [search guide](WEB_SEARCH.md)

### T3-1 — Find current documentation

As a developer, I want live documentation search, so that I can inspect sources beyond the model's training data.

- Send the current search query to the configured provider.
- Parse and display result URLs, snippets and retrieval time.
- Provide those same sources to the model as reference material.

### T3-2 — Understand search failure

As a user, I want search failures distinguished from evidence, so that I do not mistake an unsupported answer for research.

- Show partial-provider warnings when usable results remain.
- Report empty or failed searches without inventing results.
- Stop cancels the request and prevents saving a completed search answer.

## T4 — Permitted file access

`T4` `CLI` `MCP` `API` `owner-B` · [file guide](FILE_ACCESS.md)

### T4-1 — Attach a project note

As a developer, I want to attach an allowed file, so that the assistant answers from project-specific information.

- Read a supported UTF-8 file below the selected workspace.
- Attach its real contents to the next question.
- Reject traversal, links and unsupported or oversized input.

### T4-2 — Save a new answer file

As a student, I want to save a useful answer, so that I can keep it with my study materials.

- Preview the destination and exact content.
- Create the file only after explicit approval.
- Reject existing destinations and paths outside the permitted workspace.

## T5 — Structured results

`T5` `CLI` `web` `owner-B` · [structured workflow](STRUCTURED_WORKSPACE.md)

### T5-1 — Turn notes into a checklist

As a team member, I want tasks extracted from meeting notes, so that I can track priorities and completion.

- Validate task titles and priorities against the schema before display.
- Render a checklist and persist its completion state.
- Reopen the result and export schema-valid task data.

### T5-2 — Reuse an action plan

As a student, I want a structured plan, so that another interface can use its ordered steps without parsing prose.

- Generate an object containing a goal and ordered steps.
- Retry invalid model output within a fixed limit; save no invalid result.
- Render, reopen and export the validated plan.

## R1 — Document retrieval

`R1` `CLI` `web` `owner-C` · [retrieval guide](WEB_DOCUMENT_UPLOAD.md)

### R1-1 — Answer from a document

As a student, I want to ask about a local note, so that the answer uses the material I supplied.

- Ingest a supported document into chunks and embeddings.
- Retrieve relevant chunks for the question.
- Include those chunks with source references in the generation context.

### R1-2 — Keep indexing failures visible

As a user, I want invalid documents rejected clearly, so that I know which material the assistant can actually use.

- Reject empty, unsupported or invalid UTF-8 uploads.
- List successfully indexed sources and chunk counts.
- Report indexing failure instead of claiming the document is available.

## R2 — Advanced retrieval

`R2` `web` `Python API` `owner-C` · [retrieval implementation](../retrieval/rag.py)

### R2-1 — Rank useful passages first

As a developer, I want irrelevant matches removed, so that the model receives stronger evidence.

- Compare a fixed query set against basic retrieval.
- Rerank candidates and discard scores below the chosen threshold.
- Record source rankings and retained relevance scores.

### R2-2 — Restrict the source set

As a developer, I want to filter document metadata, so that an answer uses the intended project sources.

- Select a supported metadata filter.
- Exclude nonmatching chunks before final context assembly.
- Display the active filter and the selected sources for verification.

## A1 — Reasoning and action loops

`A1` `CLI` `web` `owner-A` · [MCP loop](../mcp_tools/runner.py)

### A1-1 — Use an observation to continue

As a developer, I want the assistant to act on tool feedback, so that a multi-step task progresses from actual results.

- The model chooses a tool action.
- Return its observation before requesting the next decision.
- Expose the action sequence and final outcome without fabricating results.

### A1-2 — Bound an unsuccessful loop

As a user, I want repeated attempts to stop, so that an unsolved task cannot run indefinitely.

- Configure a finite action budget.
- Stop further tool calls when the budget is exhausted.
- Report the unresolved outcome and preserve the visible action evidence.

## A2 — Multiple agents

`A2` `CLI` `web` `owner-A` · [scope](SCOPING.md)

### A2-1 — Delegate research and review

As a developer, I want specialized agents to share a task, so that research, implementation and review have distinct responsibilities.

- Assign distinct roles and inputs.
- Pass one agent's actual output to the next.
- Show handoffs and identify each contribution.

### A2-2 — Resolve conflicting suggestions

As a developer, I want a coordinator to reconcile agent feedback, so that I receive one justified result.

- Produce independently attributable suggestions.
- Expose a disagreement and the coordinator's resolution.
- Stop on task/time limits and report incomplete work.

## A3 — Human approval

`A3` `CLI` `web` `owner-B` · [MCP approvals](MCP.md)

### A3-1 — Review before acting

As a user, I want to see an action before it runs, so that I can decide whether its scope is appropriate.

- Show the tool arguments or file preview.
- Wait for explicit approval.
- Execute only the approved action and report its result.

### A3-2 — Refuse an action

As a user, I want to reject or cancel an action, so that an unwanted operation does not execute.

- Reject before execution and verify no tool call or file creation.
- Reject expired or reused web approval IDs.
- Cancel the turn without saving a successful answer.

## A4 — Prompt versions

`A4` `API` `dashboard` `owner-D` · [version store](../prompts/versioning.py)

### A4-1 — Compare prompt versions

As a maintainer, I want versioned prompts, so that I can inspect what changed between two configurations.

- Store content, author, description and timestamp.
- Select two versions and display their textual difference.
- Associate new runs with the active prompt version.

### A4-2 — Restore a known prompt

As a maintainer, I want to roll back a prompt, so that a poor edit does not affect future conversations.

- Activate an earlier stored version.
- The next request uses that version.
- Keep newer versions and prior run records for comparison.

## A5 — Personas

`A5` `CLI` `web` `owner-D` · [persona question set](PERSONA_CHECKS.md)

### A5-1 — Switch from tutoring to review

As a student, I want to change the assistant's role, so that I can first learn and then test my understanding.

- Use Explainer for an explanation and Reviewer for code feedback.
- Switch without discarding prior conversation.
- Check role/tone differences using the fixed persona question set.

### A5-2 — Configure a new persona

As a maintainer, I want persona settings outside source code, so that I can adapt the assistant for a different teaching style.

- Define name, role, tone and scope in JSON.
- Reject malformed or duplicate configurations.
- Select the valid persona and verify its behavior on the same questions.

## A6 — Semantic cache

`A6` `shared chat` `owner-C` · [cache tests](../tests/test_semantic_cache.py)

### A6-1 — Reuse a similar answer

As a frequent user, I want repeated independent questions answered from cache, so that I avoid unnecessary generation.

- Complete and cache an eligible first question.
- Ask a sufficiently similar question with compatible model/system context.
- Observe a cache hit and no new generation call.

### A6-2 — Avoid reusing incompatible context

As a user, I want contextual questions to bypass the cache, so that earlier project details cannot be ignored.

- Start a follow-up or provide context that makes reuse ineligible.
- Verify the cache is bypassed for that request.
- Changing model or system context prevents use of the old entry.

## A7 — Prompt optimization

`A7` `API` `owner-C` · [quality guide](QUALITY.md)

### A7-1 — Measure a better prompt

As a maintainer, I want prompt variants compared against a quality signal, so that changes are supported by evidence.

- Generate candidates from a recorded baseline.
- Score answers on a fixed development set using a stated objective.
- Save the selected candidate and its score history; do not activate a worse one.

### A7-2 — Check generalization

As a maintainer, I want an independent evaluation set, so that a higher optimization score is not mistaken for general improvement.

- Keep test questions out of candidate selection.
- Compare baseline and selected prompt on those held-out questions.
- Report failures, quality differences, latency and model/settings.

## EV1 — Answer evaluation

`EV1` `web` `Python API` `owner-C` · [evaluation guide](EV1_EVALUATION.md)

### EV1-1 — Check source faithfulness

As a student, I want unsupported claims highlighted, so that I know which parts of an answer need checking.

- Evaluate a completed answer against its supplied context.
- Return relevance, coherence and faithfulness scores.
- Expose unsupported claims or contradictions with an explanation.

### EV1-2 — Handle judge failure honestly

As a user, I want evaluation status separate from the answer, so that a missing judge is not reported as a pass.

- Report an explicit skipped or failed evaluation status.
- Preserve the completed answer if the judge is unavailable.
- Distinguish a judge score from proof of factual correctness.

## EV2 — Content and privacy rules

`EV2` `CLI` `web` `API` `owner-B` · [guardrails](GUARDRAILS.md)

### EV2-1 — Block a prohibited request

As an operator, I want input rules applied before generation, so that configured prohibited content is not sent to the model.

- Load an explicit policy file.
- Reject a matching request before its model call.
- Show a clear refusal without saving a completed answer.

### EV2-2 — Remove configured personal data

As a user, I want sensitive fields filtered from released output, so that supported personal data is not exposed in the result.

- Buffer and inspect model output when policy is enabled.
- Redact or refuse matching data before supported display/persistence paths.
- Validate structured data again after filtering.

## EV3 — Run monitoring

`EV3` `dashboard` `API` `owner-D` · [event store](../events/store.py)

### EV3-1 — Inspect a run

As a maintainer, I want to inspect one request, so that I can explain its tools, output and failure state.

- Identify events by run ID and order.
- Display tool calls/results, completion status and timing.
- Inspect the exact assembled prompt and selected chunks for that turn.

### EV3-2 — Compare operational behavior

As a maintainer, I want a metrics view, so that I can spot changes in latency or failure rate.

- Aggregate completed, failed and cancelled runs.
- Compare runs associated with prompt versions.
- Distinguish measured token counts from estimates and missing values.

## EV4 — Adversarial testing

`EV4` `test suite` `reports` `owner-C` · [attack report](ev4_adversarial_testing.md)

### EV4-1 — Probe malicious source text

As a maintainer, I want injection cases tested, so that I understand how retrieved content can redirect the assistant.

- Run named attacks with recorded model/settings.
- Capture actual responses and the source context.
- Classify successes, partial failures and failures against explicit criteria.

### EV4-2 — Compare a mitigation

As a maintainer, I want before/after attack results, so that I can judge whether a defense helped.

- Use the same attack set for both variants.
- Retain raw results and explain changed classifications.
- Report regressions as well as improvements.

## X1 — Browser interface

`X1` `web` `owner-D` · [web service](../web/app.py)

### X1-1 — Work from a browser

As a student, I want a browser chat, so that I can use Sensai without terminal commands for each question.

- Select a real mode, model and persona.
- Send a question and display its result or explicit error.
- Retain completed history and show active run status.

### X1-2 — Control a tool action

As a user, I want visible tool controls, so that I can inspect and control model actions.

- Show the proposed arguments and approval card.
- Approve or reject using the matching run/action ID.
- Display actual results and allow cancellation while the run is active.

## X2 — Branching and interruption

`X2` `web` `CLI` `owner-A` · [web run control](../web/app.py)

### X2-1 — Explore an alternative message

As a student, I want to edit an earlier question into a branch, so that I can compare different approaches without losing the original.

- Select a past user message.
- Create a distinct branch with the edited message.
- Switch between branches and preserve their separate histories.

### X2-2 — Stop and redirect a response

As a user, I want to interrupt a run, so that I can change direction without waiting for it to finish.

- Cancel an active generation or tool wait.
- Do not persist the incomplete turn as a successful answer.
- Accept a new instruction and continue normally.

## X3 — Export and sharing

`X3` `web` `API` `owner-D` · [export service](../export/service.py)

### X3-1 — Download a deliverable

As a student, I want exportable results, so that I can use them in a report outside Sensai.

- Select a conversation snapshot or artifact.
- Export the supported JSON, Markdown or PDF representation.
- Preserve selected content while excluding unrelated session data.

### X3-2 — Share outside the machine

As a team member, I want a public snapshot link, so that a reviewer can read the result without access to my working session.

- Publish only the selected snapshot.
- Open its URL on another machine without signing in.
- Keep other conversations, private records and internal logs inaccessible.

## X4 — Questions and forms

`X4` `API` `owner-D` · [form validation](../forms/service.py)

### X4-1 — Clarify a missing requirement

As a developer, I want a focused clarification form, so that I can supply required details before execution.

- The model produces a supported form schema.
- Render the requested fields and validate the answers.
- Return validated answers to the waiting model run.

### X4-2 — Recover from invalid input

As a user, I want field-level feedback, so that I can correct a form without restarting the task.

- Reject answers that violate the declared schema.
- Preserve valid answers and display what needs fixing.
- Resume the same run only after valid submission, or cancel it explicitly.

## X5 — Scheduling

`X5` `CLI` `web` `owner-A` · [scope](SCOPING.md)

### X5-1 — Schedule a project summary

As a developer, I want recurring summaries, so that I can review changes without starting each request manually.

- Save a task, interval and timezone.
- Execute it at the scheduled time and expose the result or error.
- Prevent overlapping executions of the same job.

### X5-2 — Manage a recurring task

As a user, I want to disable and resume scheduled work, so that it runs only when useful.

- Persist enabled/disabled state.
- Restore schedules correctly after restart.
- Show the next run and recent outcomes without duplicating jobs.
