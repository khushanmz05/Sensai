# Verification

Use this page for current commands and the evidence summary. Earlier outputs and
environment notes are preserved in the [historical log](archive/VERIFICATION_LOG.md).
Do not interpret an old test count or “not implemented” paragraph as current status.

## Run the automated suite

From the repository root in Ubuntu/WSL:

```bash
source .venv/bin/activate
python -m pip install -r requirements-mcp.txt
python -m pip install pytest
python -m pytest tests -q
```

To exercise the real sandbox tests, install Bubblewrap/libseccomp and run
`python -m sandbox` as described in [SANDBOX.md](SANDBOX.md). Those tests can skip
when isolation dependencies are absent. Most other tests use controlled model
or search responses; MCP tests also start real local stdio servers. No live-model
quality score should be inferred from the suite passing.

## Recorded evidence

| Date / scope | Result | What it establishes |
| --- | --- | --- |
| 1 Nov 2026 — T2 integration before Clear follow-up | 410 tests and 155 subtests passed; 48.04 s; no skips; one existing Pydantic warning. | Integrated mechanisms at the tested working-tree state later committed on `b-t2-sandbox`. |
| 1 Nov 2026 — Clear follow-up (`8c9acd8`) | 13 MCP web tests and 2 subtests passed; 8.32 s. | Clear before first message, scoped session clearing, approvals, execution and Stop. |
| 1 Nov 2026 — live T2, qwen3:0.6b | Actual NameError, corrected code, second sandbox call, stdout `20.0`. | One real model/tool correction scenario; known demo calls approved by the verification harness. |
| 29 Oct 2026 — live MCP | Project file and preexisting Time server returned real results in CLI/web checks. | MCP discovery, execution, result feedback and approval behavior for those tools. |
| 29 Oct 2026 — live search | SearXNG returned sources; browser showed results, provider failure, recovery and cancellation. | Real provider integration, not universal answer accuracy. |
| EV4 report in main | Named attacks, raw result files and manual classifications are checked in. | Known successes, partial failures and failures; see [the report](ev4_adversarial_testing.md). |

T2 and Clear were merged as `c0db73b`. The merge tree matched the tested branch;
the full suite was not rerun merely to create the merge commit. The two test rows
above are separate runs, not a claim that a 411-test full run was performed.

## Focused checks

| Area | Command |
| --- | --- |
| CLI / persona configuration | `python -m pytest tests/test_chatbot.py tests/test_persona.py -q` |
| MCP and sandbox | `python -m pytest tests/test_mcp.py tests/test_mcp_web.py tests/test_sandbox.py -q` |
| Structured results | `python -m pytest tests/test_structured.py tests/test_structured_workflow.py tests/test_structured_api.py -q` |
| Retrieval | `python -m pytest tests/test_rag.py tests/test_r2_fixed_queries.py tests/test_document_upload.py -q` |
| Cache and optimization | `python -m pytest tests/test_semantic_cache.py tests/test_optimizer.py -q` |
| Live search integration boundaries | `python -m pytest tests/test_web_search.py tests/test_web_search_async.py tests/test_search_web.py -q` |

## Real-model acceptance

Use [persona checks](PERSONA_CHECKS.md), the individual feature guides and the
[defense runbook](DEMO.md). For every result, record:

| Field | Required evidence |
| --- | --- |
| Revision | Git commit and whether uncommitted code was used |
| Environment | OS, Python/Ollama versions, model tags and relevant service versions |
| Scenario | Story/probe ID, exact request and reference result |
| Observation | Actual output, tool results, sources, error or cancellation state |
| Outcome | Pass / Partial / Fail / Skipped, with the reason |
| Reproduction | Command or UI steps, configuration and dependency setup |

Remaining acceptance work includes the persona pack, independent A7 evaluation,
RAG toggle, exact-context inspection, external publication and a timed full-team
rehearsal. See [the feature register](FEATURES.md) for other partial/planned work.

## Documentation review

For this documentation revision, validate local Markdown links and anchors,
story coverage/tags, referenced paths and agreement with CLI/API options.
Do not run installers, optimization jobs or database-changing API examples just
to proofread documentation. No fresh-install, live persona or 30-minute rehearsal
pass is claimed by editing these files.
