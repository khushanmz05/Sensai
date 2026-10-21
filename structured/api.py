"""Real-model structured workflows and persisted JSON/checklist consumers."""
import os
from pathlib import Path
import sqlite3
from typing import Any, Dict, Literal, Optional

from fastapi import HTTPException, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, StrictBool, StrictInt

from core.chat import ChatError
from guardrails import GuardrailError, Guardrails
from structured.output import StructuredOutputError
from structured.results import ResultError, ResultStore
from structured.workflow import generate_result, select_output


class GenerateRequest(BaseModel):
    text: str = Field(min_length=1, max_length=20000)
    kind: Literal['tasks', 'plan', 'custom']
    model: Optional[str] = None
    schema_: Optional[Dict[str, Any]] = Field(default=None, alias='schema')
    attempts: int = Field(default=2, ge=1, le=5)

    class Config:
        extra = 'forbid'  # No client-supplied host, mode or fake result.


class CompletionRequest(BaseModel):
    index: StrictInt
    completed: StrictBool


def install_routes(app, settings):
    app.state.structured_store = ResultStore()
    policy_path = os.getenv('SENSAI_GUARDRAILS')
    app.state.structured_policy = Guardrails.from_file(policy_path) if policy_path else None

    @app.get('/structured')
    def structured_page():
        return FileResponse(Path(__file__).resolve().parent.parent / 'web/static/structured.html')

    @app.get('/api/structured/schemas')
    def schemas():
        return {'model': settings.default_model,
                'schemas': {kind: select_output(kind).schema for kind in ('tasks', 'plan')}}

    @app.post('/api/structured/generate')
    def generate(request: GenerateRequest):
        try:
            return generate_result(request.text, request.kind,
                                   request.model or settings.default_model,
                                   settings.clean_ollama_host, 120,
                                   app.state.structured_store, schema=request.schema_,
                                   attempts=request.attempts, guardrails=app.state.structured_policy)
        except (StructuredOutputError, GuardrailError) as error:
            raise HTTPException(status_code=422, detail=str(error))
        except ChatError as error:
            raise HTTPException(status_code=502, detail=str(error))
        except (sqlite3.Error, OSError):
            raise HTTPException(status_code=503, detail='Structured result storage is unavailable.')

    @app.get('/api/structured/results')
    def list_results():
        return app.state.structured_store.list()

    @app.get('/api/structured/results/{result_id}')
    def get_result(result_id: str):
        try:
            return app.state.structured_store.get(result_id)
        except ResultError as error:
            raise HTTPException(status_code=404, detail=str(error))

    @app.patch('/api/structured/results/{result_id}/completion')
    def completion(result_id: str, request: CompletionRequest):
        try:
            return app.state.structured_store.set_completed(result_id, request.index, request.completed)
        except ResultError as error:
            raise HTTPException(status_code=422, detail=str(error))

    @app.get('/api/structured/results/{result_id}/export')
    def export_result(result_id: str):
        try:
            raw = app.state.structured_store.export(result_id)
        except ResultError as error:
            raise HTTPException(status_code=404, detail=str(error))
        return Response(raw, media_type='application/json', headers={
            'Content-Disposition': 'attachment; filename="sensai-result.json"'})
