# T5: structured results that applications can use

## User scenario

Paste meeting notes, extract tasks with priorities, mark completed tasks, reopen
the saved checklist, and download schema-valid JSON for another program. A second
workflow creates an ordered action plan. Custom extraction accepts an inline JSON
Schema and renders the validated fields as a record.

The model receives the schema through Ollama's `format` field and the prompt.
Sensai buffers the complete response, parses strict JSON, validates it against
the schema, and only then persists or renders a result. Invalid model output gets
at most two attempts by default (configurable from one to five). Transport errors
are not retried. There is no stub fallback for structured generation.

## Start and demonstrate

Run from the repository root with Ollama running and an installed model:

```bash
python3 -m pip install -r requirements.txt
python3 -m unittest discover -s tests -p 'test_structured*.py' -v
python3 -m unittest discover -s tests -p 'test_guardrails.py' -v
python3 -m unittest discover -s tests -p 'test_search_chat.py' -v
python3 -m uvicorn web.app:app --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000/structured and enter `llama3.2:1b` (or your installed
model) in the model field. The main chat navigation also links to this page.

1. Choose **Task list** and submit:
   `Fix login: high priority. Update README: low priority.`
2. Verify two task rows and their priorities; expand **Validated JSON** and
   **Schema used for this result**. Schema validity guarantees structure, not
   factual accuracy: check that the tasks match the source.
3. Mark a task complete. Reload the page, reopen the saved result, and verify
   the checkmark is retained. Restart the server and repeat.
4. Download JSON. It contains only the schema-valid model data; checklist progress
   remains separate metadata, so export does not break downstream consumers.
5. Choose **Action plan** and submit `Prepare a five-minute Sensai presentation`.
   Check that ordered steps are rendered and can be completed.
6. Choose **Custom data**, retain the example schema and submit
   `Name: Alex. Skills: Python and SQL.` Verify fields and download JSON.
7. Select a nonexistent model and submit again. Verify an error appears and no
   new result is saved. Restore the installed model. An older result may remain
   visible; it is not a new successful generation.

The automated tests use a deterministic transport to check repair, exhausted
validation, offline errors, cancellation, schema forwarding, persistence and
export. This live walkthrough checks the actual model and browser together.

## CLI

```bash
python3 chatbot.py --model llama3.2:1b
```

```text
/extract tasks Fix login: high priority. Update README: low priority.
/results
/result RESULT_ID
/complete RESULT_ID 1
/uncomplete RESULT_ID 1
/result RESULT_ID json
/extract plan Prepare a five-minute Sensai presentation
```

Replace `RESULT_ID` with the printed ID. CLI item numbers start at one. To save
the exported JSON as a file, use the existing writable workspace option and
`/save` confirmation flow after `/extract` or `/result`. For custom extraction,
start with `--json-schema path/to/schema.json`, then use `/extract custom <text>`.
Ctrl+C during CLI generation cancels without saving a result.

## API and storage

| Endpoint | Purpose |
| --- | --- |
| GET `/api/structured/schemas` | Built-in schemas and configured model |
| POST `/api/structured/generate` | `{ "kind": "tasks", "text": "...", "model": "llama3.2:1b" }` |
| GET `/api/structured/results` | Latest 100 result summaries |
| GET `/api/structured/results/{id}` | Data, schema, model and progress |
| PATCH `/api/structured/results/{id}/completion` | `{ "index": 0, "completed": true }` (zero-based) |
| GET `/api/structured/results/{id}/export` | JSON attachment matching its schema |

Custom generation adds `"kind": "custom"` and `"schema": {...}`. Client-supplied
hosts and modes are rejected. The existing chat schema path also rejects explicit
stub mode and no longer silently falls back to fake output when Ollama is offline.

Results are stored in `sensai_structured.db` separately from conversations. Set
`SENSAI_STRUCTURED_DB` before starting either process to change the path. The CLI
and web share the default database. Source text is not stored in this database.
Optional web guardrails use `SENSAI_GUARDRAILS=guardrails/demo.json`; CLI uses its
existing `--guardrails` flag.

Supported schemas declare a top-level object with inline Draft 2020-12 rules.
Nested objects, arrays, required fields, enums and supported jsonschema formats
are validated. References (`$ref`, `$dynamicRef`) and other drafts are rejected.
Source text is limited to 20,000 characters and each model response to 262,144.
The web call waits for the complete result; browser cancellation is not a server
cancellation control. These local endpoints have no authentication and should be
bound to localhost.

Teacher feedback did not specify an exact alternative interpretation. This
workflow supplies a concrete consumer of schema-constrained model output; final
acceptance still belongs to the evaluator.
