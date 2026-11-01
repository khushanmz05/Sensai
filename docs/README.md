# Documentation

Choose the guide for the task you want to perform. Setup commands belong in
guides; current delivery status belongs in the feature register; past results
belong in the verification record.

## Run Sensai

| Guide | What it covers |
| --- | --- |
| [Start from scratch](../START.md) | Ubuntu/WSL, Python environment, Ollama, terminal and browser |
| [Configuration](CONFIGURATION.md) | CLI commands, environment variables, databases and optional services |
| [Document retrieval](WEB_DOCUMENT_UPLOAD.md) | Upload, indexing, questions and retrieval limitations |
| [MCP tools](MCP.md) | Project and time servers, discovery, approval and cancellation |
| [Python sandbox](SANDBOX.md) | Isolated execution, error feedback and corrected runs |
| [Web search](WEB_SEARCH.md) | SearXNG setup, sources and failure handling |
| [File access](FILE_ACCESS.md) | Workspace reads and approved creation of new files |
| [Structured workspace](STRUCTURED_WORKSPACE.md) | Tasks, plans, schemas, saved progress and JSON export |
| [Guardrails](GUARDRAILS.md) | Input/output rules and privacy filtering |

## Understand and validate

| Guide | What it covers |
| --- | --- |
| [Architecture](ARCHITECTURE.md) | Request flow, components, storage and context visibility |
| [Quality and evaluation](QUALITY.md) | Prompt versions, cache, optimizer and judge |
| [Automated evaluation](EV1_EVALUATION.md) | Scores, source faithfulness and skip conditions |
| [Adversarial testing report](ev4_adversarial_testing.md) | Recorded attack results, including failures |
| [Guardrail web checks](EV2_WEB_VERIFY.md) | Reproducible browser/API checks |
| [Verification](VERIFY.md) | Test commands, evidence and remaining validation |

## Track and present

| Guide | What it covers |
| --- | --- |
| [Feature register](FEATURES.md) | All 28 catalogue entries, current status and evidence |
| [User stories](USER_STORIES.md) | Two concrete scenarios per feature, tags and acceptance criteria |
| [Scope and ownership](SCOPING.md) | Team responsibilities and definition of done |
| [Persona checks](PERSONA_CHECKS.md) | Repeatable questions, expectations and result template |
| [30-minute defense](DEMO.md) | One connected scenario, timing and fallback material |

Historical material: [initial scope](archive/INITIAL_SCOPE.md) and
[verification log](archive/VERIFICATION_LOG.md). These are retained for traceability;
their old status paragraphs are not current product documentation.
