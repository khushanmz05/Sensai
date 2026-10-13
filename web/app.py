import asyncio
from copy import deepcopy
import json
import os
from pathlib import Path
import queue
import secrets
import threading
import time
from typing import Any, Dict, List, Optional
import uuid

from fastapi import FastAPI, HTTPException, Query, Response, UploadFile, File
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse, StreamingResponse
from pydantic import BaseModel

from artifacts.service import (
    ArtifactError,
    ArtifactPatch,
    ArtifactStore,
    VersionConflictError,
)
from core.chat import (
    ChatError,
    RealtimeStreamBridge,
    assemble_turn,
    execute_turn_stream,
    make_system_message,
    persist_turn,
    stream_reply,
)
from core.config import settings
from events.contract import EventStream, to_sse
from events.store import EventStore
from export.service import ExportError, SnapshotStore, sanitize_snapshot_data
from forms.service import FormValidationError, validate_form_answers, validate_form_schema
from persona.registry import PersonaError, load_personas, persona_prompt
from prompts.versioning import PromptError, PromptVersionStore
from retrieval.store import VectorStore
from session import DatabaseError, SessionStore, build_system_message
from structured.output import JsonOutput, StructuredOutputError, strict_json

STATIC_DIR = Path(__file__).resolve().parent / 'static'
SCHEMAS_DIR = Path(__file__).resolve().parent.parent / 'schemas'

app = FastAPI(title='Sensai Shared Service')

app.state.delay = 0.03  # seconds between fake chunks in stub mode
app.state.mode = settings.mode  # 'ollama' or 'stub'
app.state.ollama_host = settings.clean_ollama_host  # Fixed server-side; client must not choose outbound URL
app.state.default_model = settings.default_model
app.state.runs: Dict[str, Dict[str, Any]] = {}

app.state.session_store = SessionStore(settings.sessions_db)
app.state.store = EventStore(str(settings.events_db))
app.state.prompts = PromptVersionStore(str(settings.prompts_db))
app.state.artifacts = ArtifactStore(str(settings.artifacts_db))
app.state.snapshots = SnapshotStore(str(settings.snapshots_db))
app.state.vector_store = VectorStore(':memory:')


from pydantic import BaseModel, Field


class RunRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    persona_id: Optional[str] = None
    model: Optional[str] = None
    mode: Optional[str] = None
    schema_: Optional[Dict[str, Any]] = Field(default=None, alias='schema')
    schema_name: Optional[str] = None

    model_config = {'populate_by_name': True}


class CreateSessionRequest(BaseModel):
    title: str = 'New session'
    persona_id: Optional[str] = None
    session_id: Optional[str] = None


class RenameSessionRequest(BaseModel):
    title: str


class SwitchPersonaRequest(BaseModel):
    persona_id: Optional[str] = None


class CreatePromptRequest(BaseModel):
    content: str
    name: str = 'system'
    author: str = 'user'
    description: str = ''
    activate: bool = True


class CreateArtifactRequest(BaseModel):
    artifact_id: str
    title: str
    sections: Optional[Dict[str, str]] = None


class PatchArtifactRequest(BaseModel):
    expected_version: int
    section_id: str
    operation: str
    value: str = ''
    title: Optional[str] = None


class FormResponseRequest(BaseModel):
    answers: Dict[str, Any]


class PublishSnapshotRequest(BaseModel):
    title: str
    type: str
    data: Dict[str, Any]
    custom_id: Optional[str] = None


@app.get('/')
def index():
    return FileResponse(STATIC_DIR / 'index.html')


@app.get('/dashboard')
def dashboard():
    return FileResponse(STATIC_DIR / 'dashboard.html')


@app.get('/api/personas')
def list_personas():
    try:
        return list(load_personas().values())
    except PersonaError as error:
        raise HTTPException(status_code=500, detail=str(error))


def format_session_response(session: Dict[str, Any], store: SessionStore) -> Dict[str, Any]:
    messages = store.get_messages(session['id'])
    history = [{'role': m['role'], 'content': m['content']} for m in messages]
    persona_id = session.get('persona_id') or store.get_session_persona(session['id'])
    return {
        'session_id': session['id'],
        'id': session['id'],
        'title': session['title'],
        'persona_id': persona_id,
        'turns_count': len(messages),
        'history': history,
        'messages': messages,
        'total_tokens': 0,
        'created_at': session['created_at'],
        'updated_at': session['updated_at'],
        'status': session.get('status', 'active'),
    }


@app.get('/api/sessions')
def list_sessions():
    sessions = app.state.session_store.list_sessions()
    return [format_session_response(s, app.state.session_store) for s in sessions]


@app.post('/api/sessions')
def create_session(req: CreateSessionRequest):
    sess = app.state.session_store.create_session(
        title=req.title,
        persona_id=req.persona_id,
        session_id=req.session_id,
    )
    return format_session_response(sess, app.state.session_store)


@app.get('/api/sessions/{session_id}')
def get_session(session_id: str):
    sess = app.state.session_store.get_session(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail='Session not found.')
    return format_session_response(sess, app.state.session_store)


@app.post('/api/sessions/{session_id}/clear')
def clear_session(session_id: str):
    sess = app.state.session_store.get_session(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail='Session not found.')
    app.state.session_store.clear_session_messages(session_id)
    return {'status': 'cleared', 'session_id': session_id}


@app.post('/api/sessions/{session_id}/persona')
def switch_session_persona(session_id: str, req: SwitchPersonaRequest):
    sess = app.state.session_store.get_session(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail='Session not found.')
    if req.persona_id and req.persona_id.strip():
        personas = load_personas()
        if req.persona_id.strip() not in personas:
            raise HTTPException(status_code=422, detail=f'Unknown persona {req.persona_id!r}.')
        app.state.session_store.set_session_persona(session_id, req.persona_id.strip())
    else:
        app.state.session_store.set_session_persona(session_id, None)
    updated = app.state.session_store.get_session(session_id)
    return format_session_response(updated, app.state.session_store)


@app.post('/api/sessions/{session_id}/rename')
@app.patch('/api/sessions/{session_id}')
def rename_session(session_id: str, req: RenameSessionRequest):
    sess = app.state.session_store.rename_session(session_id, req.title)
    if not sess:
        raise HTTPException(status_code=404, detail='Session not found.')
    return format_session_response(sess, app.state.session_store)


@app.post('/api/sessions/{session_id}/select')
def select_session(session_id: str, user_id: str = 'default'):
    sess = app.state.session_store.get_session(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail='Session not found.')
    app.state.session_store.set_active_session(user_id, session_id)
    return format_session_response(sess, app.state.session_store)


@app.get('/api/prompts')
def list_prompts(name: str = 'system'):
    return app.state.prompts.list_versions(name)


@app.get('/api/prompts/active')
def get_active_prompt(name: str = 'system'):
    active = app.state.prompts.get_active_version(name)
    if not active:
        raise HTTPException(status_code=404, detail=f'No active prompt for {name!r}.')
    return active


@app.post('/api/prompts')
def create_prompt(request: CreatePromptRequest):
    try:
        return app.state.prompts.create_version(
            name=request.name,
            content=request.content,
            author=request.author,
            description=request.description,
            activate=request.activate,
        )
    except PromptError as error:
        raise HTTPException(status_code=422, detail=str(error))


@app.post('/api/prompts/{version_id}/rollback')
def rollback_prompt(version_id: str, name: str = 'system'):
    try:
        return app.state.prompts.rollback(name, version_id)
    except PromptError as error:
        raise HTTPException(status_code=404, detail=str(error))


@app.get('/api/prompts/compare')
def compare_prompts(v1: str, v2: str, name: str = 'system'):
    try:
        return app.state.prompts.compare_performance(
            app.state.store, name=name, version_a=v1, version_b=v2
        )
    except PromptError as error:
        raise HTTPException(status_code=404, detail=str(error))


@app.get('/api/metrics')
def get_metrics():
    return app.state.store.get_metrics()


@app.get('/api/runs/{run_id}')
def get_run(run_id: str):
    run = app.state.store.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail='Unknown run.')
    return run


@app.get('/api/runs/{run_id}/history')
def get_run_history(run_id: str):
    events = app.state.store.get_events(run_id)
    if not events:
        raise HTTPException(status_code=404, detail='No events for this run.')
    return events


@app.post('/api/runs')
def start_run(request: RunRequest):
    message = request.message.strip()
    if not message:
        raise HTTPException(status_code=422, detail='Message cannot be empty.')

    p_id = None
    if request.persona_id is not None:
        p_id = request.persona_id.strip() or None
        if p_id:
            personas = load_personas()
            if p_id not in personas:
                raise HTTPException(status_code=422, detail=f'Unknown persona {p_id!r}.')

    session_id = request.session_id.strip() if request.session_id and request.session_id.strip() else None
    existing_session = app.state.session_store.get_session(session_id) if session_id else None
    if not existing_session:
        created_session = app.state.session_store.create_session(
            title='New session',
            persona_id=p_id,
            session_id=session_id,
        )
        session_id = created_session['id']
    elif p_id is not None:
        app.state.session_store.set_session_persona(session_id, p_id)

    session_persona = app.state.session_store.get_session_persona(session_id)

    active_prompt_obj = app.state.prompts.get_active_version('system')
    prompt_version = active_prompt_obj['version_id'] if active_prompt_obj else 'v1'
    base_prompt = active_prompt_obj['content'] if active_prompt_obj else 'You are Sensai.'

    personas = load_personas()
    saved_history = app.state.session_store.get_messages(session_id)

    to_send, user_content, retrieved_results, formatted_context = assemble_turn(
        system_prompt=base_prompt,
        user_text=message,
        history_messages=saved_history,
        personas=personas,
        active_persona=session_persona,
        session_store=app.state.session_store,
        user_id='default',
        retrieval_store=app.state.vector_store,
        top_k=3,
    )

    target_schema = request.schema_
    if request.schema_name:
        schema_path = SCHEMAS_DIR / f"{request.schema_name}.json"
        if not schema_path.exists():
            raise HTTPException(status_code=422, detail=f"Schema {request.schema_name!r} not found.")
        try:
            target_schema = strict_json(schema_path.read_text(encoding='utf-8'))
        except Exception as err:
            raise HTTPException(status_code=422, detail=f"Invalid schema: {err}")

    requested_mode = request.mode or app.state.mode
    effective_mode = requested_mode
    if requested_mode == 'ollama':
        is_alive = settings.check_ollama_alive()
        if not is_alive:
            if request.mode == 'ollama':
                effective_mode = 'ollama'  # Explicit request: let it attempt and raise explicit connection error
            else:
                effective_mode = 'stub'  # Auto fallback

    stream = EventStream(on_event=app.state.store.record_event)
    app.state.store.record_run_metadata(
        stream.run_id,
        persona_id=session_persona,
        prompt_version=prompt_version,
        session_id=session_id,
    )

    host = app.state.ollama_host  # Fixed server-side; client must not choose outbound URL
    model = request.model or app.state.default_model

    app.state.runs[stream.run_id] = {
        'stream': stream,
        'message': message,
        'user_content': user_content,
        'session_id': session_id,
        'persona_id': session_persona,
        'persona': personas.get(session_persona) if session_persona else None,
        'messages': to_send,
        'retrieved_results': retrieved_results,
        'formatted_context': formatted_context,
        'mode': effective_mode,
        'host': host,
        'model': model,
        'schema': target_schema,
        'timeout': 60,
        'cancelled': False,
        'streaming': False,
        'form_waiting': False,
        'form_schema': None,
        'form_response': None,
    }

    return {'run_id': stream.run_id, 'session_id': session_id}


@app.post('/api/runs/{run_id}/cancel')
def cancel_run(run_id: str):
    run = app.state.runs.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail='Unknown run.')
    if run['stream'].finished:
        raise HTTPException(status_code=400, detail='Run already finished.')
    run['cancelled'] = True
    return {'run_id': run_id, 'status': 'cancelled'}


async def generate_events(run: Dict[str, Any]):
    stream: EventStream = run['stream']
    session_id: str = run['session_id']
    user_content: str = run['user_content']
    persona = run.get('persona')
    mode = run['mode']
    retrieved = run.get('retrieved_results', [])
    parts: List[str] = []
    stats: Dict[str, Any] = {}

    start_time = time.time()
    try:
        if retrieved:
            yield to_sse(stream.emit('tool_call', tool='retrieval', query=run['message']))
            sources = [
                {
                    'source_file': r.get('source_file'),
                    'start_line': r.get('start_line'),
                    'end_line': r.get('end_line'),
                    'score': r.get('score', 0),
                }
                for r in retrieved
            ]
            yield to_sse(stream.emit('tool_result', tool='retrieval', sources=sources))

        if run.get('cancelled'):
            yield to_sse(stream.done('cancelled'))
            return

        if mode == 'ollama':
            bridge = RealtimeStreamBridge(
                lambda stop_event, q: [
                    q.put(('chunk', chunk))
                    for chunk in execute_turn_stream(
                        host=run['host'],
                        model=run['model'],
                        to_send=run['messages'],
                        timeout=run['timeout'],
                        json_output=JsonOutput(run['schema']) if run.get('schema') else None,
                        stats_collector=stats,
                        stop_event=stop_event,
                    )
                ]
            )

            try:
                async for event_kind, val in bridge.iter_events():
                    if run.get('cancelled'):
                        bridge.cancel()
                        break
                    if event_kind == 'chunk':
                        parts.append(val)
                        yield to_sse(stream.emit('text_delta', text=val))
                    elif event_kind == 'error':
                        raise val
            except ChatError as err:
                yield to_sse(stream.emit('error', message=str(err)))
                yield to_sse(stream.done('failed'))
                return
            except StructuredOutputError as err:
                yield to_sse(stream.emit('error', message=str(err)))
                yield to_sse(stream.done('failed'))
                return

        else:
            prefix = f"[{persona['name']}] " if persona else ''
            reply_text = f"{prefix}Stub reply to: {run['message']}"
            if run.get('schema'):
                if 'goal' in run['schema'].get('properties', {}):
                    reply_text = json.dumps({'goal': run['message'], 'steps': ['Step 1', 'Step 2']})
                elif 'tasks' in run['schema'].get('properties', {}):
                    reply_text = json.dumps({'tasks': [{'title': run['message'], 'priority': 'medium'}]})
                else:
                    reply_text = json.dumps({'result': run['message']})

            words = reply_text.split(' ')
            for index, word in enumerate(words):
                if run.get('cancelled'):
                    break
                await asyncio.sleep(app.state.delay)
                if run.get('cancelled'):
                    break
                token = word if index == 0 else ' ' + word
                parts.append(token)
                yield to_sse(stream.emit('text_delta', text=token))

        if run.get('cancelled'):
            yield to_sse(stream.done('cancelled'))
        else:
            full_reply = ''.join(parts)
            eval_tokens = (stats.get('prompt_eval_count') or 0) + (stats.get('eval_count') or 0)
            tokens = eval_tokens if eval_tokens > 0 else max(1, len(full_reply.split()))
            latency_ms = (time.time() - start_time) * 1000

            persist_turn(app.state.session_store, session_id, user_content, full_reply)

            yield to_sse(stream.emit('metrics', tokens=tokens, latency_ms=latency_ms))
            yield to_sse(stream.done('completed'))

    except Exception as exc:
        yield to_sse(stream.emit('error', message=str(exc)))
        yield to_sse(stream.done('failed'))
    finally:
        app.state.runs.pop(stream.run_id, None)


@app.get('/api/runs/{run_id}/events')
def run_events(run_id: str):
    run = app.state.runs.get(run_id)
    if run is None or run.get('streaming'):
        raise HTTPException(status_code=404, detail='Unknown run.')
    run['streaming'] = True
    return StreamingResponse(
        generate_events(run),
        media_type='text/event-stream',
        headers={'Cache-Control': 'no-cache'},
    )


@app.post('/api/forms/validate')
def validate_form(payload: Dict[str, Any]):
    schema = payload.get('schema')
    answers = payload.get('answers')
    if not schema or answers is None:
        raise HTTPException(status_code=422, detail='Must provide both schema and answers.')
    try:
        validated_answers = validate_form_answers(schema, answers)
        return {'status': 'valid', 'answers': validated_answers}
    except FormValidationError as err:
        raise HTTPException(status_code=422, detail=str(err))


@app.post('/api/runs/{run_id}/form_response')
def submit_form_response(run_id: str, req: FormResponseRequest):
    run = app.state.runs.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail='Run not found.')
    run['form_response'] = req.answers
    run['form_waiting'] = False
    return {'run_id': run_id, 'status': 'resumed', 'received': req.answers}


@app.get('/api/artifacts')
def list_artifacts():
    return app.state.artifacts.list_artifacts()


@app.post('/api/artifacts')
def create_artifact(req: CreateArtifactRequest):
    try:
        return app.state.artifacts.create_artifact(
            artifact_id=req.artifact_id,
            title=req.title,
            initial_sections=req.sections,
        )
    except ArtifactError as err:
        raise HTTPException(status_code=422, detail=str(err))


@app.get('/api/artifacts/{artifact_id}')
def get_artifact(artifact_id: str):
    art = app.state.artifacts.get_artifact(artifact_id)
    if not art:
        raise HTTPException(status_code=404, detail='Artifact not found.')
    return art


@app.post('/api/artifacts/{artifact_id}/patch')
def patch_artifact(artifact_id: str, req: PatchArtifactRequest):
    patch = ArtifactPatch(
        artifact_id=artifact_id,
        expected_version=req.expected_version,
        section_id=req.section_id,
        operation=req.operation,
        value=req.value,
        title=req.title,
    )
    try:
        return app.state.artifacts.apply_patch(patch)
    except VersionConflictError as conflict:
        raise HTTPException(status_code=409, detail=str(conflict))
    except ArtifactError as err:
        raise HTTPException(status_code=422, detail=str(err))


@app.get('/api/artifacts/{artifact_id}/history')
def get_artifact_history(artifact_id: str):
    return app.state.artifacts.get_history(artifact_id)


@app.get('/api/artifacts/{artifact_id}/export')
def export_artifact(artifact_id: str):
    try:
        content = app.state.artifacts.render_markdown(artifact_id)
        return PlainTextResponse(content, media_type='text/markdown')
    except ArtifactError as err:
        raise HTTPException(status_code=404, detail=str(err))


@app.post('/api/snapshots')
def create_snapshot(req: PublishSnapshotRequest):
    try:
        return app.state.snapshots.publish_snapshot(
            title=req.title,
            snapshot_type=req.type,
            data=req.data,
            custom_id=req.custom_id,
        )
    except ExportError as err:
        raise HTTPException(status_code=422, detail=str(err))


@app.get('/p/{snapshot_id}')
def view_public_snapshot(snapshot_id: str):
    try:
        html_page = app.state.snapshots.export_as_html(snapshot_id)
        return HTMLResponse(html_page)
    except ExportError as err:
        raise HTTPException(status_code=404, detail=str(err))


@app.get('/p/{snapshot_id}/export')
def export_public_snapshot(snapshot_id: str, format: str = Query('json')):
    try:
        if format == 'md':
            return PlainTextResponse(
                app.state.snapshots.export_as_markdown(snapshot_id),
                media_type='text/markdown',
            )
        elif format == 'html':
            return HTMLResponse(app.state.snapshots.export_as_html(snapshot_id))
        else:
            return Response(
                app.state.snapshots.export_as_json(snapshot_id),
                media_type='application/json',
            )
    except ExportError as err:
        raise HTTPException(status_code=404, detail=str(err))
