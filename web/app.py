import asyncio
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from events.contract import EventStream, to_sse
from events.store import EventStore
from persona.registry import PersonaError, load_personas
from prompts.versioning import PromptError, PromptVersionStore

STATIC_DIR = Path(__file__).resolve().parent / 'static'

app = FastAPI(title='Sensai Web UI (stub)')
app.state.delay = 0.05  # seconds between fake chunks
app.state.runs = {}
app.state.store = EventStore()
app.state.prompts = PromptVersionStore()

class RunRequest(BaseModel):
    message: str
    persona_id: str | None = None

class CreatePromptRequest(BaseModel):
    content: str
    name: str = 'system'
    author: str = 'user'
    description: str = ''
    activate: bool = True

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
    persona = None
    if request.persona_id and request.persona_id.strip():
        persona_id = request.persona_id.strip()
        personas = load_personas()
        if persona_id not in personas:
            raise HTTPException(status_code=422, detail=f'Unknown persona {persona_id!r}.')
        persona = personas[persona_id]
    active_prompt = app.state.prompts.get_active_version('system')
    prompt_version = active_prompt['version_id'] if active_prompt else None
    stream = EventStream(on_event=app.state.store.record_event)
    app.state.store.record_run_metadata(
        stream.run_id,
        persona_id=request.persona_id.strip() if request.persona_id and request.persona_id.strip() else None,
        prompt_version=prompt_version,
    )
    app.state.runs[stream.run_id] = {
        'stream': stream,
        'message': message,
        'persona': persona,
        'cancelled': False,
        'streaming': False,
    }
    return {'run_id': stream.run_id}

@app.post('/api/runs/{run_id}/cancel')
def cancel_run(run_id: str):
    run = app.state.runs.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail='Unknown run.')
    if run['stream'].finished:
        raise HTTPException(status_code=400, detail='Run already finished.')
    run['cancelled'] = True
    return {'run_id': run_id, 'status': 'cancelled'}

async def fake_events(run):
    stream = run['stream']
    message = run['message']
    persona = run.get('persona')
    prefix = f'[{persona["name"]}] ' if persona else ''
    words = f'{prefix}Stub reply to: {message}'.split(' ')
    try:
        for index, word in enumerate(words):
            if run.get('cancelled'):
                break
            await asyncio.sleep(app.state.delay)
            if run.get('cancelled'):
                break
            yield to_sse(stream.emit('text_delta', text=word if index == 0 else ' ' + word))
        if run.get('cancelled'):
            yield to_sse(stream.done('cancelled'))
        else:
            yield to_sse(stream.emit('metrics', tokens=len(words), latency_ms=0))
            yield to_sse(stream.done('completed'))
    finally:
        app.state.runs.pop(stream.run_id, None)

@app.get('/api/runs/{run_id}/events')
def run_events(run_id: str):
    run = app.state.runs.get(run_id)
    if run is None or run.get('streaming'):
        raise HTTPException(status_code=404, detail='Unknown run.')
    run['streaming'] = True
    return StreamingResponse(fake_events(run),
        media_type='text/event-stream', headers={'Cache-Control': 'no-cache'})
