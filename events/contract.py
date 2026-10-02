import json
import time
import uuid

EVENT_TYPES = (
    'text_delta', 'tool_call', 'tool_result', 'approval_request',
    'form_request', 'metrics', 'error', 'done',
)
RUN_STATUSES = (
    'running', 'awaiting_input', 'awaiting_approval',
    'completed', 'cancelled', 'failed',
)


class EventError(Exception):
    """An event that does not follow the contract."""

def new_run_id():
    return uuid.uuid4().hex

def validate_event(event):
    if not isinstance(event, dict):
        raise EventError('Event must be an object.')
    if set(event) != {'run_id', 'sequence', 'type', 'payload', 'timestamp'}:
        raise EventError('Event fields must be run_id, sequence, type, payload, timestamp.')
    if not isinstance(event['run_id'], str) or not event['run_id']:
        raise EventError('run_id must be a non-empty string.')
    if type(event['sequence']) is not int or event['sequence'] < 0:
        raise EventError('sequence must be a non-negative integer.')
    if event['type'] not in EVENT_TYPES:
        raise EventError(f'Unknown event type {event["type"]!r}.')
    if not isinstance(event['payload'], dict):
        raise EventError('payload must be an object.')
    if not isinstance(event['timestamp'], (int, float)):
        raise EventError('timestamp must be a number of seconds.')
    return event

class EventStream:
    def __init__(self, run_id=None, clock=time.time):
        self.run_id = run_id or new_run_id()
        self.sequence = 0
        self.finished = False
        self.clock = clock

    def emit(self, type, **payload):
        if self.finished:
            raise EventError(f'Run {self.run_id} already finished.')
        event = validate_event({
            'run_id': self.run_id,
            'sequence': self.sequence,
            'type': type,
            'payload': payload,
            'timestamp': self.clock(),
        })
        self.sequence += 1
        if type == 'done':
            self.finished = True
        return event

    def done(self, status):
        if status not in RUN_STATUSES or status == 'running':
            raise EventError(f'Invalid final status {status!r}.')
        return self.emit('done', status=status)


def to_sse(event):
    data = json.dumps(validate_event(event), ensure_ascii=False)
    return f'id: {event["sequence"]}\nevent: {event["type"]}\ndata: {data}\n\n'
