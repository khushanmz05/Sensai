import asyncio
from pathlib import Path
import time
from typing import Any, Dict, List, Optional
import uuid

from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse, StreamingResponse
from pydantic import BaseModel

from artifacts.service import (
    ArtifactError,
    ArtifactPatch,
    ArtifactStore,
    VersionConflictError,
)
from chatbot import ChatError, stream_reply
from events.contract import EventStream, to_sse
from events.store import EventStore
from export.service import ExportError, SnapshotStore
from forms.service import FormValidationError, validate_form_answers, validate_form_schema
from persona.registry import PersonaError, load_personas, persona_prompt
from prompts.versioning import PromptError, PromptVersionStore

STATIC_DIR = Path(__file__).resolve().parent / 'static'

app = FastAPI(title='Sensai Shared Service')
app.state.delay = 0.03  # seconds between fake chunks in stub mode
app.state.mode = 'stub'  # 'stub' or 'ollama'
app.state.ollama_host = 'http://localhost:11434'
app.state.default_model = 'llama3.2:1b'
app.state.runs = {}
app.state.store = EventStore()
app.state.prompts = PromptVersionStore()
app.state.artifacts = ArtifactStore()
app.state.snapshots = SnapshotStore()


class Session:
    def __init__(self, session_id: str, persona_id: Optional[str] = None):
        self.session_id = session_id
        self.persona_id = persona_id
        self.history: List[Dict[str, str]] = []
        self.total_tokens = 0
        self.created_at = time.time()

    def clear(self):
        self.history.clear()

    def switch_persona(self, persona_id: Optional[str]):
        self.persona_id = persona_id

    def to_dict(self):
        return {
            'session_id': self.session_id,
            'persona_id': self.persona_id,
            'turns_count': len(self.history),
            'history': list(self.history),
            'total_tokens': self.total_tokens,
            'created_at': self.created_at,
        }


app.state.sessions: Dict[str, Session] = {}

class RunRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    persona_id: Optional[str] = None
    model: Optional[str] = None
    mode: Optional[str] = None


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


# --- Sessions (Multi-turn & Persona switches) ---

@app.get('/api/sessions/{session_id}')
def get_session(session_id: str):
    sess = app.state.sessions.get(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail='Session not found.')
    return sess.to_dict()


@app.post('/api/sessions/{session_id}/clear')
def clear_session(session_id: str):
    sess = app.state.sessions.get(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail='Session not found.')
    sess.clear()
    return {'status': 'cleared', 'session_id': session_id}


@app.post('/api/sessions/{session_id}/persona')
def switch_session_persona(session_id: str, req: SwitchPersonaRequest):
    sess = app.state.sessions.get(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail='Session not found.')
    if req.persona_id and req.persona_id.strip():
        personas = load_personas()
        if req.persona_id.strip() not in personas:
            raise HTTPException(status_code=422, detail=f'Unknown persona {req.persona_id!r}.')
        sess.switch_persona(req.persona_id.strip())
    else:
        sess.switch_persona(None)
    return sess.to_dict()


# --- Prompts Versioning (A4) ---

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
    session_id = request.session_id.strip() if request.session_id and request.session_id.strip() else uuid.uuid4().hex
    if session_id not in app.state.sessions:
        app.state.sessions[session_id] = Session(session_id)
    session = app.state.sessions[session_id]

    if request.persona_id is not None:
        p_id = request.persona_id.strip() or None
        if p_id:
            personas = load_personas()
            if p_id not in personas:
                raise HTTPException(status_code=422, detail=f'Unknown persona {p_id!r}.')
        session.switch_persona(p_id)

    persona_info = None
    if session.persona_id:
        personas = load_personas()
        persona_info = personas.get(session.persona_id)

    active_prompt_obj = app.state.prompts.get_active_version('system')
    prompt_version = active_prompt_obj['version_id'] if active_prompt_obj else None
    base_prompt = active_prompt_obj['content'] if active_prompt_obj else 'You are Sensai.'

    if persona_info:
        effective_system_prompt = persona_prompt(base_prompt, persona_info)
    else:
        effective_system_prompt = base_prompt

    messages = [{'role': 'system', 'content': effective_system_prompt}]
    messages.extend(session.history)
    messages.append({'role': 'user', 'content': message})

    stream = EventStream(on_event=app.state.store.record_event)
    app.state.store.record_run_metadata(
        stream.run_id,
        persona_id=session.persona_id,
        prompt_version=prompt_version,
        session_id=session_id,
    )

    mode = request.mode or app.state.mode
    host = app.state.ollama_host  # fixed server-side; client must not pick the outbound URL
    model = request.model or app.state.default_model

    app.state.runs[stream.run_id] = {
        'stream': stream,
        'message': message,
        'session': session,
        'persona': persona_info,
        'messages': messages,
        'mode': mode,
        'host': host,
        'model': model,
        'cancelled': False,
        'streaming': False,
        'form_waiting': False,
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
    session: Session = run['session']
    message: str = run['message']
    persona = run.get('persona')
    mode = run['mode']
    parts: List[str] = []

    start_time = time.time()
    try:
        if mode == 'ollama':
            loop = asyncio.get_running_loop()

            def sync_stream():
                return list(stream_reply(run['host'], run['model'], run['messages'], timeout=60))

            try:
                chunks = await loop.run_in_executor(None, sync_stream)
                for chunk in chunks:
                    if run.get('cancelled'):
                        break
                    parts.append(chunk)
                    yield to_sse(stream.emit('text_delta', text=chunk))
                    await asyncio.sleep(0.001)
            except ChatError as err:
                yield to_sse(stream.emit('error', message=str(err)))
                yield to_sse(stream.done('failed'))
                return

        else:
            prefix = f'[{persona["name"]}] ' if persona else ''
            words = f'{prefix}Stub reply to: {message}'.split(' ')
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
            session.history.append({'role': 'user', 'content': message})
            session.history.append({'role': 'assistant', 'content': full_reply})
            tokens = max(1, len(full_reply.split()))
            session.total_tokens += tokens
            latency_ms = (time.time() - start_time) * 1000

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
