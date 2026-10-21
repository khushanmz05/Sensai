"""One server-owned policy for web chat and structured workflows."""
import os

from fastapi import HTTPException
from guardrails import GuardrailError, Guardrails


def install_policy(app):
    if not hasattr(app.state, 'guardrails'):
        path = os.getenv('SENSAI_GUARDRAILS')
        app.state.guardrails = Guardrails.from_file(path) if path else None


def input_value(app, value):
    policy = app.state.guardrails
    try:
        return policy.json_input(value) if policy else value
    except GuardrailError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


def output_value(app, value):
    policy = app.state.guardrails
    try:
        return policy.json_output(value) if policy else value
    except GuardrailError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


def require_safe_export(app, value):
    """Legacy records are not rewritten: refuse exports requiring modification.

    Rendering bytes first (PDF/HTML) and then regex-redacting them would corrupt
    documents or miss encoded personal data. Check the source record instead.
    """
    if output_value(app, value) != value:
        raise HTTPException(status_code=422, detail='Export contains personal data. Create a filtered copy first.')
