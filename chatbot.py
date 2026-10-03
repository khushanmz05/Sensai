#!/usr/bin/env python3
"""Sensai bootstrap: a small CLI using the Ollama HTTP API directly."""
import argparse
import json
import math
from pathlib import Path
import sys

import requests

from persona.registry import PersonaError, load_personas, persona_prompt


class ChatError(Exception):
    """An error that can be explained without a traceback."""


def stream_reply(base_url, model, messages, timeout):
    """Yield NDJSON content chunks; require the final done marker."""
    try:
        with requests.post(
            base_url.rstrip('/') + '/api/chat',
            json={'model': model, 'messages': messages, 'stream': True},
            stream=True,
            timeout=(5, timeout),
        ) as response:
            if response.status_code == 404:
                raise ChatError(
                    f'Model {model!r} unavailable (HTTP 404). '
                    f'Run: ollama pull {model}. Also check --host.'
                )
            if not response.ok:
                raise ChatError(f'Ollama HTTP {response.status_code}: {response.text[:500]}')
            # Decode each complete byte line as UTF-8, not requests' guessed encoding.
            for line in response.iter_lines(chunk_size=1):
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except (ValueError, UnicodeError) as error:
                    raise ChatError('Ollama sent invalid JSON.') from error
                if not isinstance(data, dict):
                    raise ChatError('Ollama sent an invalid response object.')
                if data.get('error'):
                    raise ChatError(f'Ollama: {data["error"]}')
                message = data.get('message', {})
                if not isinstance(message, dict):
                    raise ChatError('Ollama sent an invalid message.')
                content = message.get('content', '')
                if not isinstance(content, str):
                    raise ChatError('Ollama sent non-text content.')
                if content:
                    yield content
                if data.get('done') is True:
                    return
            raise ChatError('Response ended before completion.')
    except requests.Timeout as error:
        raise ChatError('Ollama timed out. Retry or increase --timeout.') from error
    except requests.ConnectionError as error:
        raise ChatError(
            'Connection failed or was interrupted. Check --host and run: ollama serve'
        ) from error
    except requests.RequestException as error:
        raise ChatError(f'HTTP request failed: {error}') from error


def run_chat(model, system_prompt, host, timeout, personas=None, active=None):
    personas = personas or {}
    history = [{'role': 'system', 'content': system_prompt}]
    if active is not None:
        history[0]['content'] = persona_prompt(system_prompt, personas[active])
    print(f'Sensai | model: {model} | persona: {active or "none"} '
          f'| /exit to quit, /clear to reset, /persona to switch')
    while True:
        try:
            user_text = input('\nYou> ').strip()
        except (EOFError, KeyboardInterrupt):
            print('\nGoodbye.')
            return 0
        if user_text == '/exit':
            return 0
        if user_text == '/clear':
            history = history[:1]
            print('Conversation cleared; system prompt retained.')
            continue
        if user_text == '/persona' or user_text.startswith('/persona '):
            persona_id = user_text[len('/persona'):].strip()
            if not persona_id:
                print('Personas: ' + (', '.join(
                    key + (' (active)' if key == active else '') for key in personas
                ) or 'none available'))
            elif persona_id not in personas:
                print(f'Unknown persona {persona_id!r}. Type /persona to list them.')
            else:
                history[0] = {'role': 'system',
                    'content': persona_prompt(system_prompt, personas[persona_id])}
                active = persona_id
                print(f'Persona switched to {personas[persona_id]["name"]}; history kept.')
            continue
        if not user_text:
            print('Empty input: enter a message.')
            continue
        # Commit both turns only after a complete response. Failures do not
        # pollute future requests with unanswered questions or partial output.
        pending = history + [{'role': 'user', 'content': user_text}]
        parts = []
        print('Sensai> ', end='', flush=True)
        try:
            for chunk in stream_reply(host, model, pending, timeout):
                print(chunk, end='', flush=True)
                parts.append(chunk)
            if not ''.join(parts).strip():
                raise ChatError('The model returned no answer. Try a different model.')
        except KeyboardInterrupt:
            print('\nGeneration cancelled; this turn was not saved.')
            continue
        except ChatError as error:
            print(f'\nError: {error}\nThis turn was not saved.', file=sys.stderr)
            continue
        print()
        history = pending + [{'role': 'assistant', 'content': ''.join(parts)}]


def positive_timeout(value):
    try:
        number = float(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError('timeout must be a number') from error
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError('timeout must be finite and greater than zero')
    return number


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', required=True, help='installed Ollama model name')
    parser.add_argument('--system-prompt', type=Path,
                        default=Path(__file__).resolve().parent / 'prompts/system.txt')
    parser.add_argument('--host', default='http://localhost:11434')
    parser.add_argument('--timeout', type=positive_timeout, default=120,
                        help='read inactivity timeout in seconds (default: 120)')
    parser.add_argument('--persona', help='persona id to start with (see /persona)')
    parser.add_argument('--persona-dir', type=Path,
                        default=Path(__file__).resolve().parent / 'personas')
    args = parser.parse_args()
    if not args.model.strip():
        parser.error('--model cannot be empty')
    try:
        prompt = args.system_prompt.read_text(encoding='utf-8').strip()
        if not prompt:
            raise ValueError('system prompt file is empty')
    except (OSError, UnicodeError, ValueError) as error:
        print(f'Cannot load system prompt: {error}', file=sys.stderr)
        return 1
    try:
        personas = load_personas(args.persona_dir)
    except PersonaError as error:
        print(f'Cannot load personas: {error}', file=sys.stderr)
        return 1
    if args.persona is not None and args.persona not in personas:
        print(f'Unknown persona {args.persona!r}. Available: {", ".join(personas)}',
              file=sys.stderr)
        return 1
    return run_chat(args.model, prompt, args.host, args.timeout, personas, args.persona)


if __name__ == '__main__':
    sys.exit(main())
