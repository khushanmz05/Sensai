# EV1: Automated evaluation and hallucination detection

SensAI can run an Ollama-based judge after a completed, non-structured answer when
retrieval supplied source context and guardrails are not active. The original answer
is streamed first; the judge result is then sent as an `evaluation` server-sent event.
The web UI displays the faithfulness score or warns when unsupported claims are flagged.

The judge returns:

- `relevance`: how directly the answer addresses the question, from 0 to 1.
- `coherence`: clarity and internal consistency, from 0 to 1.
- `faithfulness`: how well the answer is supported by the retrieved evidence, from 0 to 1.
- `hallucination_detected`: whether the judge flags a material unsupported or contradictory claim.
- `unsupported_claims`: short descriptions of claims that could not be verified from the evidence.
- `explanation`: a short reason for the evaluation.

Configure the judge model with `SENSAI_EVAL_MODEL`. If unset, the chat model selected for
the run is used. The judge uses the server's configured Ollama host.

Evaluation is skipped for stub responses, structured JSON runs, runs without retrieved
context, and runs where guardrails are active. If the judge is unavailable or returns an
invalid result, the answer still completes and the event reports `status: failed` with a
safe reason. Scores are LLM-judge estimates, not proof of correctness; review flagged
claims and compare the judge against a manually labelled evaluation set before relying
on it for high-stakes decisions.

Run unit tests with:

```bash
PYTHONPATH=. pytest -q tests/test_evaluation.py
```
