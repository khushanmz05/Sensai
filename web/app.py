import asyncio
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from events.contract import EventStream, to_sse

STATIC_DIR = Path(__file__).resolve().parent / 'static'

app = FastAPI(title='Sensai Web UI (stub)')
app.state.delay = 0.05  # seconds between fake chunks
app.state.runs = {}

class RunRequest(BaseModel):
    message: str

@app.get('/')
def index():
    return FileResponse(STATIC_DIR / 'index.html')

@app.post('/api/runs')
def start_run(request: RunRequest):
    message = request.message.strip()
    if not message:
        raise HTTPException(status_code=422, detail='Message cannot be empty.')
    stream = EventStream()
    app.state.runs[stream.run_id] = {'stream': stream, 'message': message}
    return {'run_id': stream.run_id}

async def fake_events(stream, message):
    words = f'Stub reply to: {message}'.split(' ')
    for index, word in enumerate(words):
        await asyncio.sleep(app.state.delay)
        yield to_sse(stream.emit('text_delta', text=word if index == 0 else ' ' + word))
    yield to_sse(stream.emit('metrics', tokens=len(words), latency_ms=0))
    yield to_sse(stream.done('completed'))

@app.get('/api/runs/{run_id}/events')
def run_events(run_id: str):
    run = app.state.runs.pop(run_id, None)
    if run is None:
        raise HTTPException(status_code=404, detail='Unknown run.')
    return StreamingResponse(fake_events(run['stream'], run['message']),
        media_type='text/event-stream', headers={'Cache-Control': 'no-cache'})
