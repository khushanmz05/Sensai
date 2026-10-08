from typing import Any, Dict, List, Optional


class FormError(Exception):
    """Base error for forms."""


class FormValidationError(FormError):
    """Validation failed for form fields or answers."""


VALID_FIELD_TYPES = ('text', 'number', 'boolean', 'select')


def validate_form_schema(schema: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(schema, dict):
        raise FormValidationError('Form schema must be a dictionary.')
    if not schema.get('form_id') or not isinstance(schema['form_id'], str):
        raise FormValidationError('Form schema must include a non-empty string "form_id".')
    if not schema.get('title') or not isinstance(schema['title'], str):
        raise FormValidationError('Form schema must include a non-empty string "title".')
    fields = schema.get('fields')
    if not isinstance(fields, list) or len(fields) == 0:
        raise FormValidationError('Form schema must include a non-empty list of "fields".')

    seen_names = set()
    for f in fields:
        if not isinstance(f, dict):
            raise FormValidationError('Each field in schema must be a dictionary.')
        name = f.get('name')
        if not name or not isinstance(name, str):
            raise FormValidationError('Each field must have a non-empty string "name".')
        if name in seen_names:
            raise FormValidationError(f'Duplicate field name {name!r} in form schema.')
        seen_names.add(name)

        ftype = f.get('type', 'text')
        if ftype not in VALID_FIELD_TYPES:
            raise FormValidationError(f'Invalid field type {ftype!r}. Must be one of {VALID_FIELD_TYPES}.')

        if ftype == 'select':
            options = f.get('options')
            if not isinstance(options, list) or len(options) == 0:
                raise FormValidationError(f'Select field {name!r} must have non-empty "options" list.')

    return schema


def validate_form_answers(schema: Dict[str, Any], answers: Dict[str, Any]) -> Dict[str, Any]:
    validate_form_schema(schema)
    if not isinstance(answers, dict):
        raise FormValidationError('Answers must be a dictionary.')

    validated: Dict[str, Any] = {}
    for f in schema['fields']:
        name = f['name']
        ftype = f.get('type', 'text')
        required = f.get('required', True)
        default = f.get('default')

        val = answers.get(name)
        if val is None or (isinstance(val, str) and not val.strip()):
            if required:
                if default is not None:
                    val = default
                else:
                    raise FormValidationError(f'Missing required field {name!r}.')
            else:
                validated[name] = default
                continue

        if ftype == 'number':
            try:
                num = float(val)
                validated[name] = int(num) if num.is_integer() else num
            except (ValueError, TypeError):
                raise FormValidationError(f'Field {name!r} must be a number, got {val!r}.')

        elif ftype == 'boolean':
            if isinstance(val, bool):
                validated[name] = val
            elif str(val).lower() in ('true', 'yes', '1', 'y'):
                validated[name] = True
            elif str(val).lower() in ('false', 'no', '0', 'n'):
                validated[name] = False
            else:
                raise FormValidationError(f'Field {name!r} must be a boolean (yes/no), got {val!r}.')

        elif ftype == 'select':
            options = [str(opt) for opt in f.get('options', [])]
            str_val = str(val).strip()
            if str_val not in options:
                raise FormValidationError(
                    f'Invalid choice {str_val!r} for {name!r}. Allowed: {", ".join(options)}.'
                )
            validated[name] = str_val

        else:  # text
            validated[name] = str(val).strip()

    return validated


def prompt_form_cli(schema: Dict[str, Any], input_func=input, output_func=print) -> Dict[str, Any]:
    validate_form_schema(schema)
    output_func(f"\n=== {schema['title']} ===")
    if schema.get('description'):
        output_func(schema['description'])

    answers: Dict[str, Any] = {}
    for f in schema['fields']:
        name = f['name']
        label = f.get('label', name)
        ftype = f.get('type', 'text')
        required = f.get('required', True)
        default = f.get('default')

        while True:
            hint = f" ({ftype})"
            if ftype == 'select':
                hint = f" [{'/'.join(map(str, f.get('options', [])))}]"
            if default is not None:
                hint += f" [default: {default}]"

            prompt_str = f"{label}{hint}: "
            try:
                raw_input = input_func(prompt_str).strip()
            except (EOFError, KeyboardInterrupt):
                raise FormError('Form input cancelled.')

            if not raw_input and default is not None:
                raw_input = default

            try:
                temp_answers = {name: raw_input}
                single_field_schema = {**schema, 'fields': [f]}
                validated_single = validate_form_answers(single_field_schema, temp_answers)
                answers[name] = validated_single[name]
                break
            except FormValidationError as err:
                output_func(f"  Error: {err}")

    return answers

