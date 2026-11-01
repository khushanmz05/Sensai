# Web document upload

The SensAI chat page has a **Documents** button in the top toolbar. Open it to upload a UTF-8 `.txt` or `.md` file (maximum 5 MB). Select **Upload and index** to split the document into chunks, embed them, and store them in the same vector store used by RAG. The panel shows the indexed source names and chunk counts.

The upload endpoint is `POST /api/retrieval/upload` with a multipart form field named `file`. Unsupported extensions, empty files, oversized files, and non-UTF-8 content are rejected with a user-facing error. If the embedding service is unavailable, ingestion uses the existing deterministic fallback embedding function.

After upload, ask a question whose answer appears in the document. Keep the same SensAI server running: the current web vector store is in memory, so indexed documents are not retained after the server restarts.
