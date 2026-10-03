import json
from pathlib import Path

FIELDS = ('id', 'name', 'tone', 'role', 'scope')
DEFAULT_DIR = Path(__file__).resolve().parent.parent / 'personas'

class PersonaError(Exception):
    """A persona file is missing, unreadable or invalid."""

def load_persona(path):
    path = Path(path)
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, UnicodeError, ValueError) as error:
        raise PersonaError(f'Cannot load persona {path.name}: {error}') from error
    if not isinstance(data, dict):
        raise PersonaError(f'Persona {path.name} must be a JSON object.')
    for field in FIELDS:
        value = data.get(field)
        if not isinstance(value, str) or not value.strip():
            raise PersonaError(f'Persona {path.name}: field {field!r} must be a non-empty string.')
    return {field: data[field].strip() for field in FIELDS}


def load_personas(directory=DEFAULT_DIR):
    personas = {}
    for path in sorted(Path(directory).glob('*.json')):
        persona = load_persona(path)
        if persona['id'] in personas:
            raise PersonaError(f'Duplicate persona id {persona["id"]!r}.')
        personas[persona['id']] = persona
    if not personas:
        raise PersonaError(f'No personas found in {directory}.')
    return personas


def persona_prompt(base_prompt, persona):
    return (
        f'{base_prompt}\n\n'
        f'Persona: {persona["name"]}\n'
        f'Role: {persona["role"]}\n'
        f'Tone: {persona["tone"]}\n'
        f'Scope: {persona["scope"]}'
    )
