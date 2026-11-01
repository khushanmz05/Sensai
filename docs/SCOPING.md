# Scope and ownership

## Product scenario

A software student uses Sensai to understand a project, research a question,
test a short Python example and turn the findings into a reusable task list or
document. Terminal and browser access support the same learning workflow.

The team targets the full 28-entry feature catalogue. Delivery is tracked in
[FEATURES.md](FEATURES.md); a target does not become complete because it appears
in a plan, API schema or interface. The original six-week estimates are retained
in the [historical plan](archive/INITIAL_SCOPE.md).

## Responsibilities

| Member | Area | Catalogue features | Review partner |
| --- | --- | --- | --- |
| A | Core, memory and task execution | B1, M1, M2, M3, A1, A2, X2, X5 | B |
| B | Tools, permissions and safety | T1–T5, A3, EV2 | A |
| C | Retrieval, quality and optimization | R1, R2, A6, A7, EV1, EV4 | D |
| D | Interface, documents and observability | M4, A4, A5, EV3, X1, X3, X4 | C |

Owners deliver implementation, integration, tests and demonstration evidence.
Review partners check behavior and should be able to explain the subsystem.
Shared contracts and end-to-end demonstrations are team responsibilities.

## Technical boundaries

- Python 3.10 or newer; direct Ollama HTTP calls for generation and embeddings.
- No LangChain, LlamaIndex, Haystack or equivalent LLM framework. Utility
  libraries for HTTP, storage, web serving, schema validation and MCP are used.
- Ubuntu/WSL is the documented environment. T2 uses an isolated subprocess
  with Bubblewrap and seccomp; the catalogue allows this alternative to Docker.
- Features are connected through shared services where implemented. An endpoint
  alone does not establish a complete model-driven workflow.
- Supported formats and restrictions are explicit: for example text documents
  for RAG, create-only workspace writes and standard-library Python execution.

DSPy appears in the instructor's A7 feedback as well as an example in the
catalogue. Its exact intended role needs clarification against the framework
restriction. The current optimizer is implemented directly; installing a named
library is not itself evidence of prompt-quality improvement.

## Definition of done

1. Two credible [user stories](USER_STORIES.md) have observable acceptance criteria.
2. The intended CLI, web or API path works with its real dependencies.
3. Failure, permission and cancellation behavior is tested where applicable.
4. The implementation and its documented limits agree.
5. Evidence identifies the revision, model, environment, input and actual result.
6. The team can demonstrate the feature within the [defense runbook](DEMO.md).

Automated tests validate mechanisms. Real-model probes validate a particular
model and scenario. Neither alone proves general response accuracy. Feature
acceptance should record both, rather than infer success from the model's prose.

## Next integration priorities

Use the [mid-term checklist](MIDTERM_FOLLOWUP.md) for the instructor's specific
requests: persona behavior evidence, useful structured results, measured prompt
optimization, a RAG toggle, per-turn context inspection and a timed demonstration.
Also close the planned and partial catalogue entries in the feature register.
This documentation update changes no runtime behavior.
