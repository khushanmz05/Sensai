# EV2: configurable CLI content and privacy checks

Owner: member B (Mark Charadnik). This increment implements a deterministic
policy for ordinary CLI chat turns, with a reusable shared-generation boundary.
It is not full project-wide EV2 acceptance.

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

Local Windows verification on 2026-10-21: five dependency-free policy tests passed.
Integration tests and full regression execution are pending in WSL: the available
Windows interpreter lacked requests/jsonschema, and dependency downloads were denied.
Real-model checks are pending. Do not report those checks as passed.

## Remaining EV2 scope

- The web app does not yet pass a policy to the shared generator. Web chat,
  artifacts, direct endpoints, event logs and public snapshots remain outside
  this increment; configuring CLI guardrails does not protect the web service.
- CLI management commands (`/profile`, session names, file paths, etc.) are not
  filtered. Existing database records and original files are not rewritten.
- Document ingestion/index storage is not sanitized; outbound chat context is.
- There is no guarantee against paraphrases, obfuscation, prompt injection,
  multilingual bypasses, or unknown PII. Permissions and action approvals remain
  independent controls and must not be replaced by these checks.
- Model tools, cache and publication need explicit integration before claiming
  the broader acceptance criteria in SCOPING.md.
