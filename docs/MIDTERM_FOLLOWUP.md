# Mid-term follow-up

This checklist translates the instructor's notes into observable deliverables.
Runtime status refers to main `c0db73b`; the documentation changes described here
do not implement missing application behavior.

| Instructor feedback | Response / evidence | Remaining acceptance | State |
| --- | --- | --- | --- |
| Use a question set to test personas. | [Ten fixed probes](PERSONA_CHECKS.md) cover style, scope, switching and honesty; configuration/history tests exist. | Run the probes on the chosen real model and record expected versus actual behavior. | Documentation ready; live evidence pending |
| T5 was misinterpreted and was not yet a useful feature. | [Structured workspace](STRUCTURED_WORKSPACE.md) consumes schema-valid data as saved task lists/plans with progress and JSON export; stories T5-1/2 now describe user outcomes. | Demonstrate the full workflow and confirm that it resolves the instructor's intended objection. | Implemented; interpretation to confirm |
| A7 needs substantive techniques; DSPy was mentioned. | [Quality guide](QUALITY.md) states the current search method, scoring equation, stopping rule and limitations. | Independent holdout evaluation and measured results; clarify the expected role of DSPy under the framework restriction. | Partial |
| RAG must be switchable off. | CLI can omit `--docs-dir`; [MT-2](USER_STORIES.md#mid-term-acceptance-additions) defines the web requirement. | A browser control must stop retrieval/chunk injection while retaining the index, with comparison evidence. | Web change pending |
| Every turn is composed of prompt, chunks and other pipeline inputs; show them. | [Architecture](ARCHITECTURE.md#what-a-message-contains) identifies current components and visibility. | Persist and expose the exact assembled context, including full selected chunks, for each run. | Runtime inspector pending |
| Summarize user stories with tags. | [Tagged stories](USER_STORIES.md) retain stable IDs, observable checks and two scenarios per feature; [feature register](FEATURES.md) provides a compact index. | Keep status and evidence current as features merge. | Documentation updated |
| Demonstrate all features within 30 minutes. | [Timed runbook](DEMO.md) connects the story, speakers, evidence and fallback material. | Finish missing integrations, map every claimed feature to a real demonstration and rehearse twice. | Runbook ready; release/rehearsal pending |

## Closure rule

Close an item only with a reproducible result and a revision reference. A new
document, UI label or passing configuration test is not evidence that missing
runtime behavior exists. Use [VERIFY.md](VERIFY.md) to record checks and
[FEATURES.md](FEATURES.md) to update what the team can actually demonstrate.
