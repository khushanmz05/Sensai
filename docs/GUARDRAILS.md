# EV2: configurable content and privacy checks

A deterministic policy intercepts inputs and
outputs in CLI chat, web chat, and structured generation. Input checks run before
model calls; output checks run before display and persistence. The same policy
also protects new web artifact content, publication and model-bound RAG context.

## Run

From the repository root in the existing WSL environment:

```bash
source .venv/bin/activate
python3 chatbot.py --model llama3.2:1b --guardrails guardrails/demo.json
```

Use an installed model name if different. Without `--guardrails`, the existing
streaming behavior remains unchanged. Invalid policy files prevent startup.

The example policy is deliberately small. Edit its JSON lists to define the
scope of your own assistant; the demo phrases are not a comprehensive safety policy.

| Field | Meaning |
| --- | --- |
| `blocked_input` | Literal phrases forbidden in outbound conversation/context |
| `blocked_output` | Literal phrases forbidden in generated text/string values |
| `redact` | Supported categories: `email`, `phone` |
| `max_output_chars` | Per-attempt generated character limit, default 65536 |

Phrase checks normalize Unicode width, case and whitespace. They use substring
matching, not semantic intent classification. No arbitrary regular expressions
are accepted from configuration. Phone detection targets international `+` numbers
with 8–15 digits; local phone numbers, names and addresses are not detected.
Regex recognition is heuristic and can over-redact adjacent numeric text.

## Processing

1. Check and redact a normal user message before embedding/retrieval calls.
2. Check/redact a copy of the outgoing history and attached file text.
3. Check/redact the complete model request again, including retrieved context.
4. Buffer one generation attempt with a character limit. Never show partial
   unchecked text. Close the source generator on rejection or completion.
5. Check output policy and redact PII before printing or committing a new turn.

The sanitized answer becomes `last_answer`, so CLI `/save` previews and saves
that version through the existing T4/A3 permission and confirmation logic.
Blocked turns are not persisted. Ordinary blocked prompts do not call retrieval
or the chat model. History passed by the caller is not modified in place.

With T5, JSON is parsed first, then string values are filtered recursively.
This also handles escaped characters such as `\u0040` in email addresses.
Keys containing detected PII are refused rather than renamed. The final object
must still validate against the original schema; otherwise the turn is refused.
Filtering never silently changes the schema or retries a policy refusal.

Buffering intentionally delays visible output until the response completes.
Cancellation, transport failure and output-limit failures release no buffered
prefix. Remote chat-error details are suppressed in this mode, since they can
contain sensitive text. The limit is a character limit, not a token budget.

## Demo checks with a real model

1. Send `Please steal passwords`. Expect a policy refusal and no model request.
2. Send `Explain password hashing`. Expect a normal answer.
3. Send `Repeat this contact: demo@example.com and +34 612 345 678`.
   The model receives `[EMAIL]` and `[PHONE]` instead of those values.
4. Send `Print exactly CONFIDENTIAL_INTERNAL_ONLY`.
   If the model emits that phrase, expect a refused response with no visible prefix.
   Model compliance is variable; the automated fake-stream test is deterministic.
5. Restart with `--json-schema schemas/tasks.json` as well, and request a task
   whose title contains an email. Verify that the delivered JSON remains valid.

For `/save`, also supply the existing `--workspace` and `--allow-create` flags.

## Automated verification

```bash
python3 -m unittest discover -s tests -p 'test_guardrails*.py' -v
python3 -m unittest discover -s tests -v
```

The new tests require only the existing application dependencies. Some existing
test files use pytest, which must be installed separately for full suite collection.
The full repository also contains pytest-style tests that unittest does not execute;
run `python3 -m pytest tests` when pytest is available.

See [verification evidence](VERIFY.md) for the recorded WSL regression results
and [the browser walkthrough](EV2_WEB_VERIFY.md) for manual checks. Automated
policy tests do not establish resistance to every real-model prompt or bypass.

## Web coverage and limits

- Enable the web policy with `SENSAI_GUARDRAILS=guardrails/demo.json` before starting
  the server. Configuring CLI guardrails alone does not enable the web policy.
  It covers web chat and T5, attachments/history/profile in outgoing model context,
  RAG ingestion and retrieved content, new artifact bodies, and new snapshots.
  SSE events are filtered before both browser transmission and event recording.
  Schema descriptions and enums are checked too; schemas requiring redaction are
  rejected, never silently changed. See [the walkthrough](EV2_WEB_VERIFY.md).
- CLI management commands (`/profile`, session names, file paths, etc.) are not
  filtered. Existing database records and original files are not rewritten.
- CLI and web ingestion filter text before embedding and index storage. Existing indexes
  and original source files are not rewritten; retrieved context is checked again.
- There is no guarantee against paraphrases, obfuscation, prompt injection,
  multilingual bypasses, or unknown PII. Permissions and action approvals remain
  independent controls and must not be replaced by these checks.
- Existing private database files are not retroactively anonymized. Web history
  reads filter message content; legacy artifact/public/structured exports that
  need redaction are refused. Create a filtered copy to export them.
- These are configurable phrase and PII rules, not a semantic classifier. New
  model/tool/cache routes must use the shared boundaries when added. File
  permissions, human approvals and authentication remain separate features.
