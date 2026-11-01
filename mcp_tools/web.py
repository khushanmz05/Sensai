"""Web adapter for the shared MCP loop; no browser-supplied process configuration."""
import asyncio
from contextlib import suppress
import secrets

from fastapi import HTTPException
from pydantic import BaseModel, StrictBool, Field

from guardrails import GuardrailError
from .config import McpError, load_config


class Decision(BaseModel):
    approval_id: str = Field(min_length=1, max_length=128)
    approved: StrictBool
    model_config = {'extra': 'forbid'}


def install_routes(app, config_path=None):
    app.state.mcp_servers = load_config(config_path) if config_path else None
    if app.state.mcp_servers:
        # Fail at startup with an actionable message when configured but not installed.
        try:
            from . import runner  # noqa: F401
        except ImportError as error:
            raise RuntimeError('Install requirements-mcp.txt before enabling web MCP.') from error

    @app.get('/api/mcp')
    async def status():
        return {'enabled': bool(app.state.mcp_servers), 'max_calls': 4,
                'approval_timeout_seconds': 120}

    @app.get('/api/mcp/tools')
    async def tools():
        if not app.state.mcp_servers:
            raise HTTPException(503, 'MCP is disabled. Set SENSAI_MCP_CONFIG on the server.')
        from .runner import list_tools
        try:
            return await list_tools(app.state.mcp_servers, app.state.guardrails)
        except McpError as error:
            raise HTTPException(502, str(error)) from error

    @app.post('/api/runs/{run_id}/mcp/decision')
    async def decide(run_id: str, decision: Decision):
        run = app.state.runs.get(run_id)
        pending = run.get('mcp_pending') if run else None
        if (not pending or run.get('cancelled') or pending['future'].done()
                or not secrets.compare_digest(pending['id'], decision.approval_id)):
            raise HTTPException(409, 'MCP approval is unknown, expired or already decided.')
        # This endpoint and the future live on the same event loop. No await between
        # checking and deciding: duplicate and cross-run decisions cannot race.
        pending['future'].set_result(decision.approved)
        return {'status': 'approved' if decision.approved else 'rejected'}


async def turn_events(run):
    """Own one SDK task until completion, cancellation or SSE disconnect.

    The shared loop allows at most four calls, so the queue has a fixed upper
    bound on event count (approval, call and result per call, plus final event).
    SDK contexts must be entered and exited inside the same worker task.
    """
    from .runner import run_turn
    events = asyncio.Queue()

    async def approve(name, arguments):
        future = asyncio.get_running_loop().create_future()
        pending = {'id': secrets.token_hex(24), 'future': future}
        run['mcp_pending'] = pending
        events.put_nowait(('approval_request', {
            'kind': 'mcp', 'tool': name, 'arguments': arguments,
            'approval_id': pending['id'], 'timeout_seconds': 120,
        }))
        try:
            return await asyncio.wait_for(future, run.get('mcp_approval_timeout', 120))
        except asyncio.TimeoutError as error:
            raise McpError('MCP approval expired; no further actions executed.') from error
        finally:
            run['mcp_pending'] = None

    def notify(kind, payload):
        events.put_nowait(('tool_' + kind, {'kind': 'mcp', **payload}))

    async def worker():
        try:
            result = await run_turn(run['mcp_servers'], run['messages'], run['host'],
                                    run['model'], run['timeout'], max_calls=4,
                                    approve=approve, notify=notify, policy=run.get('guardrails'))
            events.put_nowait(('answer', result))
        except asyncio.CancelledError:
            events.put_nowait(('cancelled', None))
            raise
        except (McpError, GuardrailError) as error:
            events.put_nowait(('failure', error))
        except Exception:
            events.put_nowait(('failure', McpError('MCP request failed; check the server configuration.')))

    task = asyncio.create_task(worker())
    # Cancellation can happen before the coroutine starts and reaches its handler.
    task.add_done_callback(lambda completed: events.put_nowait(('cancelled', None))
                           if completed.cancelled() else None)
    run['mcp_task'] = task
    try:
        while True:
            kind, payload = await events.get()
            if kind == 'failure':
                raise payload
            if kind == 'cancelled':
                return
            yield kind, payload
            if kind == 'answer':
                return
    finally:
        if not task.done():
            task.cancel()
        with suppress(asyncio.CancelledError):
            await task
        run['mcp_pending'] = None
        run['mcp_task'] = None
