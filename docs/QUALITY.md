# Quality, prompts and evaluation

Quality claims need a fixed input set, a recorded configuration and inspectable
outputs. A mechanism working in a unit test does not show that a small local model
will answer every question correctly.

## Prompt versions (A4)

The web service stores named prompt versions with content, author, description
and timestamps. Create or activate versions through `/api/prompts`, inspect the
active version through `/api/prompts/active`, and roll back through
`/api/prompts/{version_id}/rollback`. The dashboard compares prompt text and
associated run metrics. Use the local [API explorer](http://127.0.0.1:8000/docs)
to inspect request schemas before sending changes.

CLI prompts come from `--system-prompt`; the browser uses the version store.
Editing the CLI prompt file does not automatically update an active web version.
Latency and error counts are operational evidence, not answer-quality scores.

## Semantic cache (A6)

The shared chat service embeds eligible independent questions and compares them
using cosine similarity. The default threshold is 0.92. The cache key includes
the generation host, model and system context. A matching hit skips generation
and is logged as `[A6 CACHE HIT]`; a miss proceeds to the model.

Prior conversation, incompatible attached/retrieved context, structured output
and guardrails affect eligibility. The web marks contextual requests as ineligible;
MCP and live search have their own execution paths. Verify the actual log for
the chosen scenario rather than infer a cache hit from a fast answer.
No time-to-live policy is implemented in the current cache store.

## Automated answer evaluation (EV1)

The Ollama judge reports relevance, coherence and source faithfulness on a 0–1
scale, plus unsupported claims and an explanation. It runs after eligible web
RAG answers, not every response. With guardrails enabled it is skipped; it also
does not evaluate structured output or MCP/search turns through this path.
See [EV1_EVALUATION.md](EV1_EVALUATION.md) for exact conditions and failures.

## Prompt optimization (A7)

`POST /api/prompts/optimize` generates prompt variants, evaluates answers on five
built-in questions and retains an improving candidate. The implementation is a
bounded greedy search over generated rewrites, with a plateau stopping rule and
a record of candidate scores. It uses direct Ollama calls, not DSPy.

For each question, the current objective is:

```text
score = clamp(0.3 * relevance + 0.2 * coherence + 0.5 * faithfulness
              - 0.3 * hallucination_flag, 0, 1)
objective = mean(score across the five evaluation questions)
```

The selected prompt is activated only if its score exceeds the baseline.
Candidate checks also try to retain specified requirements, but phrase matching
does not prove semantic equivalence. The same built-in questions drive selection
and reported improvement; this is not a held-out evaluation.

Before claiming the instructor's A7 requirement is satisfied:

1. Explain the candidate search, objective, stopping rule and tradeoffs.
2. Freeze the model/settings and a development set before optimizing.
3. Keep a separate holdout set out of prompt selection.
4. Evaluate baseline and selected prompt on that holdout set, preferably with
   repeated runs and manual checks of judge disagreements.
5. Report both quality and cost/latency, including regressions and uncertainty.

Suggested report columns: revision, model, prompt version, split, case ID,
reference answer, generated answer, judge scores, manual decision and duration.
No completed held-out improvement report is claimed for the current main.
The exact intended use of DSPy needs clarification against the assignment's
restriction on LLM frameworks.

## Behavior and adversarial checks

Use [PERSONA_CHECKS.md](PERSONA_CHECKS.md) for role/tone/context behavior.
The [EV4 report](ev4_adversarial_testing.md) contains attack results, including
failures and partial compliance. Retain those findings when explaining the
system; filtering and source delimiters are not universal defenses.

Record evidence using [VERIFY.md](VERIFY.md). A demonstration should show actual
tool results and supplied sources before interpreting the model's explanation.
