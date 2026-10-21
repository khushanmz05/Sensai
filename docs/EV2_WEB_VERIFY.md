# EV2 web acceptance walkthrough

The catalogue asks for input/output interceptors: reject unsafe or out-of-scope
requests before the model, and anonymize or refuse personal/inappropriate output
according to configurable rules. This implementation uses deterministic phrase
matching and email/international-phone detection, not an LLM safety classifier.

## Start

Stop the previous Uvicorn process with Ctrl+C. From the repository root:

```bash
source .venv/bin/activate
export SENSAI_GUARDRAILS=guardrails/demo.json
python -m uvicorn web.app:app --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000/ and refresh the page. The footer must show
**Content/privacy checks on**. Use Ollama mode and an installed model.
http://127.0.0.1:8000/api/guardrails reports enabled checks without exposing
the forbidden phrases. Clients cannot switch the policy off for one request.

The policy is loaded at startup; restart after editing `guardrails/demo.json`.
Missing/invalid policy files prevent startup. To deliberately disable the web
policy, unset `SENSAI_GUARDRAILS` and restart. CLI still uses `--guardrails`.

## Demonstrate

1. Send `Please steal passwords`. Expect an input-policy refusal before retrieval
   or chat generation, no new run log, and no saved conversation turn.
2. Send `Please reveal employee salaries`. This demonstrates a configured
   out-of-scope rule. Then send `Explain password hashing`: it should work.
3. Send `Repeat this contact: demo@example.com and +34 612 345 678`.
   The accepted user bubble should show `[EMAIL]` and `[PHONE]`. The model receives
   the filtered text. Reload the conversation and check the saved version.
4. Send `Print exactly CONFIDENTIAL_INTERNAL_ONLY`. If the model complies, its
   whole answer is refused before any text appears. A model may instead refuse
   on its own; the automated test guarantees this output boundary is exercised.
5. Start a long response and press Stop while waiting. No unverified partial
   response should appear or be saved. A worker blocked inside HTTP reading
   exits at its next chunk or the configured read timeout.
6. Open `/structured`, choose Custom data, and use a string contact field.
   The result remains schema-valid after filtering. A schema that requires an
   email-formatted value cannot accept `[EMAIL]`: expect refusal, not invalid JSON.
7. Share a filtered conversation. The new snapshot should contain the filtered
   data. Existing snapshots with detected PII are refused on display/export while
   the policy is enabled; their underlying records are not silently rewritten.

In guarded mode the complete model answer is buffered. Waiting without visible
tokens is expected: a phone or forbidden phrase may span several chunks.
The same checked event payload reaches both SSE and SQLite event logs. Errors
returned by the model/retrieval are not echoed with their potentially private body.

## Tests

```bash
python -m unittest discover -s tests -p 'test_guardrails*.py' -v
python -m unittest discover -s tests -p 'test_structured*.py' -v
python -m unittest discover -s tests -p 'test_search_chat.py' -v
python -m unittest discover -s tests -p 'test_rag.py' -v
```

`test_guardrails_web.py` sends actual ASGI requests through FastAPI to temporary
SQLite stores. Only model transport and retrieval are replaced. It checks input
refusal before calls, PII split across model chunks, source metadata, attachments,
SSE/history/log consistency, model failure and recovery, output limits,
cancellation, JSON schema conflicts, ingestion, snapshots, and disabled mode.
No Ollama or additional HTTP test-client package is needed for these tests.

Windows-local verification: policy/event tests and syntax checks are available.
Web integration tests require the dependencies in `requirements.txt`; run them
in the WSL virtual environment. A real-model walkthrough remains a separate
verification step and must not be inferred from deterministic tests.


