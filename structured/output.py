"""Validate model JSON before making it available to callers."""
from copy import deepcopy
import json
import math
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import SchemaError, ValidationError


class StructuredOutputError(ValueError):
    """Invalid schema or exhausted output-validation attempts."""


def _reject_constant(value):
    raise ValueError('Non-finite JSON number.')


def _finite_float(value):
    number = float(value)
    if not math.isfinite(number):
        raise ValueError('JSON number is outside the supported range.')
    return number


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON object key.')
        result[key] = value
    return result


def strict_json(text):
    return json.loads(text, parse_constant=_reject_constant,
                      parse_float=_finite_float, object_pairs_hook=_unique_object)


def _check_schema_tree(value):
    # Support inline schemas only: no reference fetching.
    if isinstance(value, dict):
        if '$ref' in value or '$dynamicRef' in value:
            raise StructuredOutputError('Schema references are not supported; inline the schema.')
        for item in value.values():
            _check_schema_tree(item)
    elif isinstance(value, list):
        for item in value:
            _check_schema_tree(item)


class JsonOutput:
    """Reusable T5 service; generate(messages, schema) yields text chunks.

    Transport errors and cancellation propagate immediately. Only invalid model
    content is retried. Caller history is never changed by this service.
    """

    def __init__(self, schema):
        if not isinstance(schema, dict) or schema.get('type') != 'object':
            raise StructuredOutputError('The schema must declare a top-level object.')
        draft = schema.get('$schema', 'https://json-schema.org/draft/2020-12/schema')
        if draft != 'https://json-schema.org/draft/2020-12/schema':
            raise StructuredOutputError('Only JSON Schema draft 2020-12 is supported.')
        _check_schema_tree(schema)
        try:
            Draft202012Validator.check_schema(schema)
        except SchemaError as error:
            raise StructuredOutputError('Invalid JSON schema: ' + error.message) from error
        self.schema = deepcopy(schema)
        self.validator = Draft202012Validator(self.schema, format_checker=FormatChecker())

    def parse(self, text):
        """Consumer boundary: never accept JSON merely because it parses."""
        try:
            value = strict_json(text)
            self.validator.validate(value)
            return value
        except ValidationError as error:
            raise StructuredOutputError(f'JSON failed schema rule: {error.validator}.') from error
        except (ValueError, RecursionError) as error:
            raise StructuredOutputError('Invalid or ambiguous JSON response.') from error

    @classmethod
    def from_file(cls, path):
        try:
            schema = strict_json(Path(path).read_text(encoding='utf-8'))
        except (OSError, UnicodeError, ValueError) as error:
            raise StructuredOutputError(f'Cannot load JSON schema: {error}') from error
        return cls(schema)

    def generate(self, messages, generate, max_attempts=2, max_chars=262144):
        if type(max_attempts) is not int or not 1 <= max_attempts <= 5:
            raise StructuredOutputError('JSON attempts must be an integer from 1 to 5.')
        if type(max_chars) is not int or max_chars < 1:
            raise StructuredOutputError('JSON output limit must be a positive integer.')
        pending = deepcopy(messages)
        instruction = ('Return only a JSON object matching this schema, without Markdown: '
                       + json.dumps(self.schema, ensure_ascii=False, allow_nan=False))
        if pending and pending[0].get('role') == 'system':
            pending[0]['content'] += '\n\n' + instruction
        else:
            pending.insert(0, {'role': 'system', 'content': instruction})
        reason = ''
        for attempt in range(max_attempts):
            # Buffer until complete: unvalidated fragments never reach the UI.
            source = iter(generate(deepcopy(pending), deepcopy(self.schema)))
            chunks, size = [], 0
            try:
                for chunk in source:
                    if not isinstance(chunk, str):
                        raise StructuredOutputError('Model returned a non-text chunk.')
                    size += len(chunk)
                    if size > max_chars:
                        raise StructuredOutputError('Structured response exceeds the size limit.')
                    chunks.append(chunk)
            finally:
                close = getattr(source, 'close', None)
                if close is not None:
                    close()
            raw = ''.join(chunks)
            try:
                result = strict_json(raw)
                self.validator.validate(result)
                return result
            except ValidationError as error:
                path = '/'.join(str(part) for part in error.absolute_path) or '(root)'
                reason = f'Schema rule {error.validator} failed at {path}.'
            except (ValueError, RecursionError):
                reason = 'The response was not valid, unambiguous JSON.'
            if attempt + 1 < max_attempts:
                # Do not persist the failed response or treat it as new instructions.
                pending.append({'role': 'user', 'content':
                    f'The previous output was rejected. {reason} '
                    'Answer the original request again using the required JSON schema.'})
        raise StructuredOutputError(
            f'No valid JSON after {max_attempts} attempt(s). {reason}')
