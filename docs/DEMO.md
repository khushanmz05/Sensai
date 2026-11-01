# Thirty-minute defense runbook

**Scenario:** a student joins the Study Planner project, learns its context,
checks a calculation, turns findings into tasks and shares a useful result.
Every demonstration should advance this story rather than introduce an unrelated
feature just to show a button.

This is a **rehearsal plan**, not a completed defense record. The current main
does not support every catalogue workflow end to end. Use the release gates
below before claiming that all 28 features can be demonstrated.

## Before the presentation

Use the actual defense machine. Follow [START.md](../START.md) and the optional
[MCP](MCP.md), [sandbox](SANDBOX.md), [retrieval](WEB_DOCUMENT_UPLOAD.md) and
[search](WEB_SEARCH.md) setup guides in advance. Do not install dependencies or
download models during the presentation.

Prepare:

- An installed chat/tool model, `nomic-embed-text`, and the configured R2 models.
- A passing `python -m sandbox` check and real MCP discovery.
- `examples/project_notes.md`, one saved session and one structured result.
- A running local search provider, plus a clearly labeled backup recording.
- Prompt versions, quality/attack reports and selected run IDs ready to inspect.
- A separate demonstration data set; do not clear personal sessions or expose
  private documents while presenting.
- One known-good request per feature and the expected observable result.

### Use one MCP configuration

To avoid restarting the server between project, time and Python tools, create
`local-output/mcp.defense.json` locally. The `local-output` directory is ignored
by Git. Create it with `mkdir -p local-output`, then save this JSON in that file:

```json
{
  "servers": [
    {
      "name": "project",
      "command": "$PYTHON",
      "args": ["-m", "mcp_tools.project_server", "--workspace", "examples"],
      "cwd": "..",
      "allow_tools": ["read_project_file"],
      "auto_approve": [],
      "timeout": 15
    },
    {
      "name": "time",
      "command": "$PYTHON",
      "args": ["-m", "mcp_server_time"],
      "cwd": "..",
      "allow_tools": ["get_current_time", "convert_time"],
      "auto_approve": ["get_current_time", "convert_time"],
      "timeout": 15
    },
    {
      "name": "python",
      "command": "$PYTHON",
      "args": ["-m", "mcp_tools.python_server"],
      "cwd": "..",
      "allow_tools": ["execute_python"],
      "auto_approve": [],
      "timeout": 15
    }
  ]
}
```

Keep SearXNG running in its own terminal. In the presentation terminal:

```bash
source .venv/bin/activate
export SENSAI_MODEL=qwen3:0.6b
export SENSAI_MCP_CONFIG=local-output/mcp.defense.json
export SENSAI_SEARCH_URL=http://127.0.0.1:8088
export SENSAI_GUARDRAILS=guardrails/demo.json
python -m uvicorn web.app:app --host 127.0.0.1 --port 8000
```

This launch profile enables privacy checks and therefore **skips automatic EV1
judging**. For EV1/A6 evidence, prepare a separate local test run with guardrails
unset, known nonprivate documents and the appropriate eligibility conditions.
Show its recorded inputs and outputs during the quality segment; do not present
the guardrail-enabled run as proof that every feature executes simultaneously.

## Timing and handoffs

| Time | Lead | Story beat | Feature evidence | Current release gate |
| --- | --- | --- | --- | --- |
| 00:00–02:00 | A | Introduce the student, project and architecture. | One diagram/code map and a clear goal. | Ready to prepare. |
| 02:00–05:00 | A → D | Resume the project session; explain a function, then switch to Reviewer. | B1, M1, A5, X1: real answer, retained facts, visibly different role. | Record persona probes first. |
| 05:00–09:00 | C | Read project knowledge, then search current documentation. | R1, R2, T3: relevant source, ranking evidence, real web URLs. | R2 comparison and filters; RAG toggle/context inspector remain incomplete. |
| 09:00–14:00 | B | Read through MCP, inspect time, execute a deliberately broken calculation and verify its correction. | T1, T2, A1, A3, T4: two MCP server types, approval/rejection, actual traceback and successful rerun. | General A1 coverage exceeds the narrower working MCP loop. |
| 14:00–18:00 | B → D | Turn notes into tasks and update the project deliverable. | T5, M3, M4, X4: persisted checklist, fact update, section edit, clarification form. | M3 is planned; model-driven M4/X4 flows are incomplete. |
| 18:00–21:00 | A | Continue a long task, explore an alternative and schedule a follow-up. | M2, A2, X2, X5: preserved compressed facts, agent handoffs, separate branch and scheduled result. | These complete workflows are not integrated in main; interruption alone is available. |
| 21:00–25:00 | C → D | Explain how the team measures quality and diagnoses failure. | A4, A6, A7, EV1–EV4: prompt diff, eligible cache hit, optimization report, judge, guardrail check, run events and attack findings. | A7 holdout report and full EV3 context evidence are missing. |
| 25:00–28:00 | D | Export the chosen outcome and open its shared snapshot. | X3: selected export and unauthenticated access from another machine. | Local export exists; external publication is unverified. |
| 28:00–30:00 | All | State limitations and answer questions. | Explain actual tradeoffs and unresolved failures. | Keep this buffer; do not consume it with setup. |

The table allocates **30 minutes**. It maps every catalogue ID, but allocation is
not proof of implementation. Pending blocks must be finished and rehearsed to
meet the instructor's full-feature goal. In an interim rehearsal, identify them
as pending; a slide about a planned feature does not count as its demonstration.

## Short requests for the live sequence

Enter each separately, wait for completion, and expand the relevant evidence.
Do not paste a future `yes` together with a request.

| Step | Request / action | Expected observation |
| --- | --- | --- |
| Persona | Use P05, then P07–P08 from [persona checks](PERSONA_CHECKS.md). | Role difference with Python/SQLite facts retained. |
| Project tool | `Read project_notes.md using the project tool. Which programming language and database are used?` | Approved MCP call; Python and SQLite in the actual file result. |
| Existing tool | `Use the time tool to get the current time in Europe/Madrid.` | A real time-server result; do not hardcode a timestamp. |
| Search | In Web search mode: `Python sqlite3 official documentation`. | Usable sources, URLs and retrieval time; inspect partial-provider warnings. |
| Python repair | `Use python__execute_python. First run exactly: values = [10, 20, 30]; print(sum(values) / len(value)). After receiving the traceback, fix the typo and execute again.` | Separate approvals; NameError, then actual stdout `20.0`. |
| Tasks | In Structured workspace: `Fix login: high priority. Update README: low priority.` | Two validated tasks; complete one, reload and export JSON. |
| File permission | CLI `/read ../README.md` with workspace `examples`. | A path-policy error before file content reaches the model. |
| Approval | Reject one proposed MCP action. | No tool call for that action and no completed answer saved. |

For create-only file access, use the [CLI save walkthrough](FILE_ACCESS.md).
For partial API components, use the API explorer only if the chosen path was
actually rehearsed; describe an API-level demonstration as such.

## Evidence and fallback

Keep a small evidence folder outside versioned private data: screenshots of
tool results, a brief search recording, exported sample results, report versions
and a table of tested story IDs. Label every recording and controlled test.
If a live dependency fails, state the failure, show the prepared evidence and
continue within the time slot. Never present a stub or predicted output as a live result.

## Rehearsal record

Run the complete scenario twice on the defense machine. Record actual duration
per segment and include approvals, model loading and transitions in the timing.

| Rehearsal | Revision / models | Total duration | Missing or failed steps | Follow-up owner |
| --- | --- | --- | --- | --- |
| 1 | Not run | — | Pending | Team |
| 2 | Not run | — | Pending | Team |

Release only the claims supported by the [feature register](FEATURES.md),
[story acceptance checks](USER_STORIES.md) and [verification record](VERIFY.md).
