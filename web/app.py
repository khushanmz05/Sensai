import asyncio
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from events.contract import EventStream, to_sse
from persona.registry import PersonaError, load_personas

STATIC_DIR = Path(__file__).resolve().parent / 'static'

app = FastAPI(title='Sensai Web UI (stub)')
app.state.delay = 0.05  # seconds between fake chunks
app.state.runs = {}

class RunRequest(BaseModel):
    message: str
    persona_id: str | None = None

@app.get('/')
def index():
    return FileResponse(STATIC_DIR / 'index.html')

@app.get('/api/personas')
def list_personas():
    try:
        return list(load_personas().values())
    except PersonaError as error:
        raise HTTPException(status_code=500, detail=str(error))

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
    stream = EventStream()
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
