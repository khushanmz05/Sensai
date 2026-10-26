"""Tests for the web UI document-upload and RAG ingestion endpoint."""
import asyncio
from io import BytesIO
import unittest
from unittest.mock import patch

from fastapi import HTTPException
from starlette.datastructures import UploadFile

from retrieval.store import VectorStore
from web import app as web_module


class DocumentUploadTests(unittest.TestCase):
    def setUp(self):
        self.app = web_module.app
        self.old_store = self.app.state.vector_store
        self.old_guardrails = self.app.state.guardrails
        self.store = VectorStore(":memory:")
        self.app.state.vector_store = self.store
        self.app.state.guardrails = None
        self.addCleanup(self._restore_state)

    def _restore_state(self):
        self.app.state.vector_store = self.old_store
        self.app.state.guardrails = self.old_guardrails
        self.store.close()

    @staticmethod
    def upload(filename, content):
        return UploadFile(filename=filename, file=BytesIO(content))

    def test_uploads_and_indexes_markdown(self):
        document = self.upload(
            "guide.md",
            b"SensAI uses retrieval augmented generation.\nDocuments are split into chunks.",
        )
        with patch("web.app.embed", return_value=[[1.0, 0.0]]):
            result = asyncio.run(web_module.upload_retrieval_document(document))

        self.assertEqual(result["status"], "ingested")
        self.assertEqual(result["filename"], "guide.md")
        self.assertEqual(result["chunks_count"], 1)
        chunks = self.store.get_all()
        self.assertEqual(len(chunks), 1)
        self.assertIn("retrieval augmented generation", chunks[0]["content"])

    def test_rejects_unsupported_extension(self):
        with self.assertRaises(HTTPException) as raised:
            asyncio.run(web_module.upload_retrieval_document(
                self.upload("secret.pdf", b"not supported")
            ))
        self.assertEqual(raised.exception.status_code, 415)

    def test_rejects_empty_document(self):
        with self.assertRaises(HTTPException) as raised:
            asyncio.run(web_module.upload_retrieval_document(
                self.upload("empty.txt", b"  \n\t")
            ))
        self.assertEqual(raised.exception.status_code, 422)

    def test_rejects_non_utf8_document(self):
        with self.assertRaises(HTTPException) as raised:
            asyncio.run(web_module.upload_retrieval_document(
                self.upload("bad.txt", b"\xff\xfe\xfa")
            ))
        self.assertEqual(raised.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main()
