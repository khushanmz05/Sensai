"""Local policy checks; not a semantic classifier or a jailbreak guarantee."""
import json
from pathlib import Path
import re
import unicodedata


class GuardrailError(ValueError):
    """Safe public error: never include matched text or personal information."""


PATTERNS = {
    'email': re.compile(r'(?<![\w.+-])[\w.+-]+@[\w-]+(?:\.[\w-]+)+'),
    # International numbers only, to avoid treating ordinary dates as phones.
    'phone': re.compile(r'(?<!\w)\+[1-9](?:[ ()-]*[0-9]){7,14}(?![0-9])'),
}


def normalized(text):
    return ' '.join(unicodedata.normalize('NFKC', text).casefold().split())


class Guardrails:
    def __init__(self, config):
        allowed = {'blocked_input', 'blocked_output', 'redact', 'max_output_chars'}
        if not isinstance(config, dict) or set(config) - allowed:
            raise GuardrailError('Invalid guardrail configuration fields.')
        for field in ('blocked_input', 'blocked_output', 'redact'):
            values = config.get(field, [])
            if not isinstance(values, list) or any(
                not isinstance(item, str) or not item.strip() for item in values
            ):
                raise GuardrailError('Guardrail rule lists must contain nonempty strings.')
        self.input_terms = tuple(normalized(x) for x in config.get('blocked_input', []))
        self.output_terms = tuple(normalized(x) for x in config.get('blocked_output', []))
        self.redactions = tuple(config.get('redact', []))
        if set(self.redactions) - set(PATTERNS):
            raise GuardrailError('Unknown personal-data category.')
        self.max_output_chars = config.get('max_output_chars', 65536)
        if type(self.max_output_chars) is not int or not 1 <= self.max_output_chars <= 1000000:
            raise GuardrailError('Output limit must be an integer between 1 and 1000000.')

    @classmethod
    def from_file(cls, path):
        try:
            config = json.loads(Path(path).read_text(encoding='utf-8'))
        except (OSError, UnicodeError, ValueError) as error:
            raise GuardrailError('Cannot read guardrail JSON configuration.') from error
        return cls(config)

    def redact(self, text):
        for category in self.redactions:
            text = PATTERNS[category].sub('[' + category.upper() + ']', text)
        return text

    def check_input(self, text):
        if any(term in normalized(text) for term in self.input_terms):
            raise GuardrailError('Input blocked by the configured content policy.')
        return self.redact(text)

    def messages(self, messages):
        # Copy rather than mutate caller history; include attachments and RAG.
        return [dict(message, content=self.check_input(message['content']))
                for message in messages]

    def output(self, text):
        if len(text) > self.max_output_chars:
            raise GuardrailError('Response exceeds the configured output limit.')
        if any(term in normalized(text) for term in self.output_terms):
            raise GuardrailError('Response blocked by the configured content policy.')
        return self.redact(text)

    def json_output(self, value):
        return self._map_strings(value, self.output)

    def json_input(self, value):
        """Check nested content before model, storage or publication boundaries."""
        return self._map_strings(value, self.check_input)

    def check_schema(self, schema):
        # Schema descriptions/enums also enter the model prompt. Never silently
        # change a schema contract to achieve redaction.
        if self.json_input(schema) != schema:
            raise GuardrailError('Schema contains personal data; use a non-personal schema.')

    def event_payload(self, event_type, payload):
        # Control events must still be deliverable when generation is refused.
        if event_type in ('error', 'done', 'metrics', 'evaluation'):
            return self._map_strings(payload, self.redact)
        return self.json_output(payload)

    def _map_strings(self, value, transform):
        if isinstance(value, str):
            return transform(value)
        if isinstance(value, list):
            return [self._map_strings(item, transform) for item in value]
        if isinstance(value, dict):
            # Renaming keys could break schemas or silently merge distinct keys.
            if any(transform(key) != key for key in value):
                raise GuardrailError('Content contains personal data in JSON keys.')
            return {key: self._map_strings(item, transform) for key, item in value.items()}
        return value
