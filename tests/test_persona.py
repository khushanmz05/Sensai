import json
from pathlib import Path
import tempfile
import unittest

from persona.registry import PersonaError, load_personas, persona_prompt

def write(directory, name, data):
    Path(directory, name).write_text(json.dumps(data), encoding='utf-8')

VALID = {'id': 'x', 'name': 'X', 'tone': 't', 'role': 'r', 'scope': 's'}

class PersonaTests(unittest.TestCase):
    def test_default_personas_load(self):
        personas = load_personas()
        self.assertIn('explainer', personas)
        self.assertIn('reviewer', personas)

    def test_missing_field_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            write(directory, 'bad.json', {**VALID, 'tone': ''})
            with self.assertRaises(PersonaError):
                load_personas(directory)

    def test_invalid_json_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, 'bad.json').write_text('{oops', encoding='utf-8')
            with self.assertRaises(PersonaError):
                load_personas(directory)

    def test_duplicate_id_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            write(directory, 'a.json', VALID)
            write(directory, 'b.json', VALID)
            with self.assertRaises(PersonaError):
                load_personas(directory)

    def test_empty_directory_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(PersonaError):
                load_personas(directory)

    def test_prompt_contains_persona_fields(self):
        prompt = persona_prompt('Base.', VALID)
        self.assertTrue(prompt.startswith('Base.'))
        for field in ('X', 'Role: r', 'Tone: t', 'Scope: s'):
            self.assertIn(field, prompt)


if __name__ == '__main__':
    unittest.main()
