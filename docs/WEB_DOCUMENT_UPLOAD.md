# Document retrieval

Use local notes as evidence for a question. Sensai splits documents into chunks,
embeds them through Ollama, retrieves relevant passages and supplies their text
to the model. This is different from attaching one file directly with `/read`.

## Prepare the embedding model

After [basic setup](../START.md), run in Ubuntu:

```bash
ollama pull nomic-embed-text
```

The chat model and embedding model have different jobs. Selecting `qwen3:0.6b`
in the browser does not replace `nomic-embed-text`. Web advanced retrieval also
defaults to `qwen3` for rewriting and reranking. To exercise those exact defaults,
install that model separately with `ollama pull qwen3`. It is a different model
tag and may require more resources; benchmark it before the defense. If those
auxiliary calls fail, retrieval can fall back to the original query/hybrid results,
which is not evidence that rewriting or reranking ran successfully.

## Browser walkthrough

1. Start the web server as described in [START.md](../START.md).
2. Open **Documents** in the chat toolbar.
3. Choose `examples/project_notes.md`, then **Upload and index**.
4. Check that the source name and a nonzero chunk count appear.
5. Select **Ollama** mode and ask: `Which programming language and database does this project use?`
6. Compare the answer with the file: **Python** and **SQLite**.

Upload accepts nonempty UTF-8 `.txt` and `.md` files up to 5 MB. The API is
`POST /api/retrieval/upload` with multipart field `file`; indexed sources are
listed by `GET /api/retrieval/sources`. Unsupported, invalid and oversized inputs
are rejected. Upload only material intended for the current local instance.

## Terminal walkthrough

```bash
python chatbot.py --model qwen3:0.6b --docs-dir examples
```

Ask the same project question. The directory is ingested for that CLI process.
To start without RAG, leave the chat and run it again **without `--docs-dir`**.
This startup choice is not a runtime on/off switch.

## Current boundaries

| Area | Current behavior |
| --- | --- |
| Persistence | The web vector store is in memory; restart clears it. Saved chat sessions are separate. |
| RAG control | No browser toggle to disable retrieval while retaining the index. |
| Context inspection | Source/line/score metadata is emitted, but there is no complete per-turn view of chunk text and the assembled prompt. |
| Advanced retrieval | Web uses rewriting, vector/BM25 combination and reranking; metadata filters exist at library level rather than as a complete UI flow. CLI uses basic retrieval. |
| Embedding failure | The upload code references a fallback helper that is absent from the current retrieval module. Do not rely on fallback indexing; install/check the real embedding model and retry. |
| Quality | Source inclusion does not guarantee that the model uses it correctly. Compare the answer with the actual note. |

These gaps are tracked in [mid-term follow-up](MIDTERM_FOLLOWUP.md), not treated as
resolved by this guide. See [evaluation](EV1_EVALUATION.md) for the conditions under
which the web service judges an answer against its retrieved context.
