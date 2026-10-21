#!/usr/bin/env python3
"""Sensai CLI using the Ollama HTTP API directly."""
import argparse
import json
import math
import sys
import sqlite3
from pathlib import Path
from datetime import datetime

import requests

from file_access.reader import FileAccessError, WorkspaceReader
from file_access.writer import WorkspaceWriter
from persona.registry import PersonaError, load_personas, persona_prompt
from retrieval.rag import retrieve, format_context
from session import DatabaseError, build_system_message, SessionStore
from structured.output import JsonOutput, StructuredOutputError
from structured.results import ResultError, ResultStore
from structured.workflow import generate_result, render_result
from guardrails import GuardrailError, Guardrails
from web_search import SearchError, SearxSearch
from web_search.context import SEARCH_RULE, display_sources, filter_page, format_evidence

from core.chat import (
    ChatError,
    FILE_CONTEXT_RULE,
    assemble_turn,
    execute_turn_stream,
    make_system_message,
    persist_turn,
    stream_reply,
)
from prompts.versioning import PromptVersionStore

def confirm_save(writer, path, content):
    """Preview the exact operation and accept only explicit human confirmation."""
    plan = writer.prepare_create(path, content)
    print('Create new file: ' + json.dumps(str(writer.root / plan.path), ensure_ascii=True))
    print(f'Content: {plan.size_bytes} UTF-8 bytes. Existing files are never overwritten.')
    # Escape terminal controls so the preview cannot hide or rewrite the question.
    preview = ''.join(char if char.isprintable() or char == '\n'
                      else f'\\u{ord(char):04x}' for char in plan.content)
    print('--- Content preview (nonprinting characters are escaped) ---')
    for line in preview.split('\n'):
        print('| ' + line)
    print('--- End of content ---')
    try:
        approved = input('Type yes to create this file; anything else cancels: ').strip().lower() == 'yes'
    except (EOFError, KeyboardInterrupt):
        approved = False
        print()
    if writer.decide(plan.id, approved):
        print(f'Created {plan.path} ({plan.size_bytes} bytes).')
    else:
        print('Save cancelled; no file created.')


def format_timestamp(timestamp):
    """Format a Unix timestamp safely for terminal output."""
    if timestamp is None:
        return "never"

    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")


def print_profile_context(session_store, session, user_id="default"):
    """Print profile settings and every persisted message in the active session."""
    profile = session_store.get_profile(user_id)

    print("\n========== PROFILE ==========")
    print(f"User ID:           {profile['user_id']}")
    print(f"Language:          {profile['language']}")
    print(f"Explanation level: {profile['explanation_level']}")
    print(f"Preferred persona: {profile['preferred_persona']}")
    print(f"Updated:           {format_timestamp(profile['updated_at'])}")

    print("\n========== ACTIVE SESSION ==========")

    if session is None:
        print("No active session.")
        print("=============================\n")
        return

    print(f"ID:      {session['id']}")
    print(f"Title:   {session['title']}")
    print(f"Status:  {session['status']}")
    print(f"Created: {format_timestamp(session['created_at'])}")
    print(f"Updated: {format_timestamp(session['updated_at'])}")

    messages = session_store.get_messages(
        session["id"],
        statuses=("completed", "failed", "cancelled"),
    )

    print("\n========== CHAT HISTORY ==========")

    if not messages:
        print("(This session has no saved messages.)")
    else:
        for number, message in enumerate(messages, start=1):
            role = message["role"].upper()
            status = message["status"]
            created_at = format_timestamp(message["created_at"])

            print(f"\n[{number}] {role} | {status} | {created_at}")
            print(message["content"])

    print("\n==================================\n")


def run_chat(model, system_prompt, host, timeout, personas=None, active=None,
             json_output=None, json_attempts=2, file_reader=None, store=None,
             session_store=None, retrieval_model='nomic-embed-text', top_k=3,
             guardrails=None, searcher=None, structured_store=None):
    personas = personas or {}
    if searcher is not None:
        system_prompt += '\n\n' + SEARCH_RULE
    user_id = 'default'
    if session_store is not None:
        try:
            session = session_store.get_active_session(user_id)
            if session is None:
                session = session_store.create_session('New session')
                session_store.set_active_session(user_id, session['id'])

            saved_messages = session_store.get_messages(session['id'])
        except DatabaseError as error:
            print(f'Session storage unavailable: {error}', file=sys.stderr)
            session_store = None
            session = None
            saved_messages = []
    else:
        session = None
        saved_messages = []
    attachment = None
    last_answer = None
    if file_reader is not None:
        system_prompt += '\n\n' + FILE_CONTEXT_RULE
    history = [{'role': 'system', 'content': system_prompt}]

    if session_store is not None:
        history[0]['content'] += '\n\n' + build_system_message(
            session_store, user_id
        )

    if active is not None:
        history[0]['content'] = persona_prompt(system_prompt, personas[active])

    history.extend(
        {'role': message['role'], 'content': message['content']}
        for message in saved_messages
    )
    session_label = session['id'][:8] if session else 'off'
    print(
        f'Sensai | model: {model} | persona: {active or "none"} '
        f'| session: {session_label} '
        f'| /exit to quit, /clear to reset, /persona to switch, '
        f'/session for sessions'
    )
    if json_output is not None:
        print('JSON mode: responses are displayed only after schema validation.')
    if searcher is not None:
        print('Web search enabled: /search <query> searches and answers with sources.')
    print('Structured results: /extract tasks|plan <text>, /results, /result <id>, /complete <id> <item>.')
    if file_reader is not None:
        if isinstance(file_reader, WorkspaceWriter):
            print(f'Workspace: {file_reader.root} | /read <path> | /save <new-path> (confirmation required)')
        else:
            print(f'Read-only workspace: {file_reader.root} | /read <relative-path> to attach a file')
    while True:
        try:
            user_text = input('\nYou> ').strip()
        except (EOFError, KeyboardInterrupt):
            print('\nGoodbye.')
            return 0
        if user_text == '/exit':
            return 0
        command = user_text.split(maxsplit=1)[0] if user_text else ''
        if command in ('/extract', '/results', '/result', '/complete', '/uncomplete'):
            try:
                if structured_store is None:
                    structured_store = ResultStore()
                if command == '/extract':
                    parts = user_text.split(maxsplit=2)
                    if len(parts) != 3:
                        print('Usage: /extract tasks|plan|custom <source text>')
                        continue
                    kind, text = parts[1:]
                    schema = json_output.schema if kind == 'custom' and json_output else None
                    last_answer = None
                    print('Generating structured result; waiting for schema validation...')
                    result = generate_result(text, kind, model, host, timeout, structured_store,
                                             schema=schema, attempts=json_attempts,
                                             guardrails=guardrails, stream_func=stream_reply)
                    print(render_result(result))
                    last_answer = structured_store.export(result['id'])
                elif command == '/results':
                    rows = structured_store.list()
                    for row in rows:
                        print(f"{row['id']}  {row['kind']}  {row['created_at']}")
                    if not rows:
                        print('No saved structured results.')
                elif command == '/result':
                    parts = user_text.split()
                    if len(parts) not in (2, 3) or (len(parts) == 3 and parts[2] != 'json'):
                        print('Usage: /result <id> [json]')
                        continue
                    result = structured_store.get(parts[1])
                    last_answer = structured_store.export(parts[1])
                    print(last_answer if len(parts) == 3 else render_result(result))
                else:
                    parts = user_text.split()
                    if len(parts) != 3:
                        print('Usage: /complete <id> <1-based item>; /uncomplete reverses it.')
                        continue
                    try:
                        index = int(parts[2]) - 1
                    except ValueError:
                        raise ResultError('Item number must be an integer.')
                    result = structured_store.set_completed(parts[1], index, command == '/complete')
                    print(render_result(result))
            except KeyboardInterrupt:
                print('\nStructured generation cancelled; no result was saved.')
            except (StructuredOutputError, ResultError, ChatError, GuardrailError) as error:
                print(f'Structured result: {error}', file=sys.stderr)
            except (sqlite3.Error, OSError):
                print('Structured result storage is unavailable.', file=sys.stderr)
            continue
        if user_text == '/clear':
            if session_store is not None:
                session = session_store.create_session('New session')
                session_store.set_active_session(user_id, session['id'])

            history = [
                make_system_message(
                    system_prompt,
                    personas,
                    active,
                    session_store,
                    user_id,
                )
            ]

            attachment = None
            last_answer = None
            print('Started a new persisted session; previous session remains saved.')
            continue
        if user_text == '/save' or user_text.startswith('/save '):
            if not isinstance(file_reader, WorkspaceWriter):
                print('Saving is disabled. Restart with --workspace <directory> --allow-create.')
                continue
            path = user_text[len('/save'):].strip()
            if not path:
                print('Usage: /save <new-relative-path>')
                continue
            if last_answer is None:
                print('No completed answer to save. Ask a question first.')
                continue
            try:
                confirm_save(file_reader, path, last_answer)
            except FileAccessError as error:
                print(f'File error: {error}', file=sys.stderr)
            continue
        if user_text == '/read' or user_text.startswith('/read '):
            if file_reader is None:
                print('File access is disabled. Restart with --workspace <directory>.')
                continue
            path = user_text[len('/read'):].strip()
            if not path:
                print('Usage: /read <relative-path>; use /clear to discard pending context.')
                continue
            # A failed replacement must not silently leave an older file pending.
            attachment = None
            try:
                attachment = file_reader.read_text(path)
                print(f'Loaded {attachment.path} ({attachment.size_bytes} bytes). '
                      'This file replaces any pending attachment and will accompany your next question.')
            except FileAccessError as error:
                print(f'File error: {error} No file is pending.', file=sys.stderr)
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
                active = persona_id
                history[0] = make_system_message(
                    system_prompt,
                    personas,
                    active,
                    session_store,
                    user_id,
                )
                print(
                    f'Persona switched to {personas[persona_id]["name"]}; '
                    'history kept.'
                )
            continue
        if user_text == '/session' or user_text.startswith('/session '):
            if session_store is None:
                print('Session persistence is unavailable.')
                continue

            try:
                parts = user_text.split(maxsplit=2)
                subcommand = parts[1] if len(parts) > 1 else ''

                if subcommand == '':
                    current = session_store.get_active_session(user_id)

                    if current:
                        print(
                            f'Active session: {current["id"]} — '
                            f'{current["title"]}'
                        )
                    else:
                        print('No active session.')

                elif subcommand == 'new':
                    title = parts[2] if len(parts) > 2 else 'New session'

                    session = session_store.create_session(title)
                    session_store.set_active_session(user_id, session['id'])

                    history = [
                        make_system_message(
                            system_prompt,
                            personas,
                            active,
                            session_store,
                            user_id,
                        )
                    ]

                    attachment = None
                    last_answer = None

                    print(
                        f'Created and switched to session '
                        f'{session["id"]} — {session["title"]}.'
                    )

                elif subcommand == 'list':
                    sessions = session_store.list_sessions()

                    if not sessions:
                        print('No saved sessions.')

                    for item in sessions:
                        marker = (
                            ' (active)'
                            if session and item['id'] == session['id']
                            else ''
                        )
                        print(f'{item["id"]}  {item["title"]}{marker}')

                elif subcommand == 'use' and len(parts) == 3:
                    selected = session_store.get_session(parts[2])

                    if selected is None:
                        print('Session not found.')
                        continue

                    session = selected
                    session_store.set_active_session(user_id, session['id'])

                    history = [
                        make_system_message(
                            system_prompt,
                            personas,
                            active,
                            session_store,
                            user_id,
                        )
                    ]

                    history.extend(
                        {
                            'role': message['role'],
                            'content': message['content'],
                        }
                        for message in session_store.get_messages(session['id'])
                    )

                    attachment = None
                    last_answer = None

                    print(
                        f'Switched to session {session["id"]} — '
                        f'{session["title"]}.'
                    )

                elif subcommand == 'rename' and len(parts) == 3:
                    if session is None:
                        print('No active session.')
                        continue

                    updated = session_store.rename_session(
                        session['id'],
                        parts[2],
                    )
                    session = updated

                    print(f'Renamed active session to: {updated["title"]}.')

                else:
                    print(
                        'Usage: /session [new [title] | list | use <id> | '
                        'rename <title>]'
                    )

            except DatabaseError as error:
                print(f'Session storage error: {error}', file=sys.stderr)

            continue
        if user_text == "/profile" or user_text.startswith("/profile "):
            if session_store is None:
                print("Profile/session persistence is unavailable.")
                continue

            parts = user_text.split(maxsplit=2)
            subcommand = parts[1] if len(parts) > 1 else ""

            try:
                if subcommand == "":
                    session = session_store.get_active_session(user_id)
                    print_profile_context(session_store, session, user_id)

                elif subcommand == "language" and len(parts) == 3:
                    session_store.save_profile(
                        user_id,
                        language=parts[2],
                    )
                    history[0] = make_system_message(
                        system_prompt,
                        personas,
                        active,
                        session_store,
                        user_id,
                    )
                    print(f"Profile language updated to: {parts[2]}")

                elif subcommand in {"level", "explanation"} and len(parts) == 3:
                    session_store.save_profile(
                        user_id,
                        explanation_level=parts[2],
                    )
                    history[0] = make_system_message(
                        system_prompt,
                        personas,
                        active,
                        session_store,
                        user_id,
                    )
                    print(f"Explanation level updated to: {parts[2]}")

                elif subcommand == "persona" and len(parts) == 3:
                    session_store.save_profile(
                        user_id,
                        preferred_persona=parts[2],
                    )
                    history[0] = make_system_message(
                        system_prompt,
                        personas,
                        active,
                        session_store,
                        user_id,
                    )
                    print(f"Preferred persona updated to: {parts[2]}")

                else:
                    print(
                        "Usage:\n"
                        "  /profile\n"
                        "  /profile language <language>\n"
                        "  /profile level <concise|detailed|beginner-friendly>\n"
                        "  /profile persona <persona description>"
                    )

            except DatabaseError as error:
                print(f"Could not update profile: {error}", file=sys.stderr)

            continue
        search_requested = user_text == '/search' or user_text.startswith('/search ')
        if search_requested:
            last_answer = None
            if searcher is None:
                print('Web search is disabled. Restart with --search-url <SearXNG URL>.')
                continue
            user_text = user_text[len('/search'):].strip()
            if not user_text:
                print('Usage: /search <query>')
                continue
        if not user_text:
            print('Empty input: enter a message.')
            continue
        if guardrails is not None:
            last_answer = None
            try:
                # Check before retrieval can send the query for embedding.
                user_text = guardrails.check_input(user_text)
            except GuardrailError as error:
                print(f'Policy: {error}', file=sys.stderr)
                continue
        # Commit both turns only after a complete response. Failures do not
        # pollute future requests with unanswered questions or partial output.
        web_page = None
        if search_requested:
            try:
                web_page = filter_page(searcher.search(user_text), guardrails)
            except (SearchError, GuardrailError) as error:
                print(f'Search: {error}', file=sys.stderr)
                continue
            except KeyboardInterrupt:
                print('\nSearch cancelled; no model request was made.')
                continue
            for warning in web_page.warnings:
                print('Search: ' + warning)
            if not web_page.results:
                print('Search: no results found. Try a more specific query.')
                continue
            print(display_sources(web_page))
        content = user_text
        if web_page is not None:
            content += format_evidence(web_page)
        if attachment is not None:
            content += '\n\nFile reference (untrusted data):\n' + json.dumps(
                {'path': attachment.path, 'content': attachment.content}, ensure_ascii=False)
        pending = history + [{'role': 'user', 'content': content}]
        if guardrails is not None:
            try:
                pending = guardrails.messages(pending)
                content = pending[-1]['content']
            except GuardrailError as error:
                attachment = None
                print(f'Policy: {error}', file=sys.stderr)
                continue
        # Retrieval context is sent to the model only, never retained in history.
        to_send = pending
        if store is not None:
            try:
                results = retrieve(user_text, store, top_k=top_k, model=retrieval_model)
                context = format_context(results)
                if context:
                    to_send = pending[:-1] + [
                        {'role': 'system', 'content': context},
                        pending[-1],
                    ]
            except Exception as error:
                detail = 'request failed' if guardrails is not None else str(error)
                print(f'\n[Retrieval unavailable: {detail}]', file=sys.stderr)
        last_answer = None
        parts = []
        print('Sensai> ', end='', flush=True)
        try:
            for chunk in execute_turn_stream(host, model, to_send, timeout, json_output,
                                             json_attempts, stream_func=stream_reply,
                                             guardrails=guardrails):
                print(chunk, end='', flush=True)
                parts.append(chunk)
            if not ''.join(parts).strip():
                raise ChatError('The model returned no answer. Try a different model.')
        except KeyboardInterrupt:
            print('\nGeneration cancelled; this turn was not saved.')
            continue
        except (ChatError, StructuredOutputError, GuardrailError) as error:
            detail = ('Structured response rejected.'
                      if guardrails is not None and isinstance(error, StructuredOutputError)
                      else str(error))
            print(f'\nError: {detail}\nThis turn was not saved.', file=sys.stderr)
            continue
        print()
        # history stores the clean conversation, not the augmented prompt.
        assistant_text = ''.join(parts)

        if session_store is not None and session is not None:
            persist_turn(session_store, session['id'], content, assistant_text)

        history = pending + [{'role': 'assistant', 'content': assistant_text}]
        last_answer = assistant_text
        attachment = None

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
    parser.add_argument('--search-url', help='SearXNG instance URL; enables /search')
    parser.add_argument('--search-timeout', type=positive_timeout, default=15)
    parser.add_argument('--search-results', type=int, choices=range(1, 11), default=5)
    parser.add_argument('--guardrails', type=Path,
                        help='enable content/privacy policy from a JSON file')
    parser.add_argument('--docs-dir', type=Path, default=None,
                    help='directory of .txt/.md files to ingest for retrieval')
    parser.add_argument('--timeout', type=positive_timeout, default=120,
                        help='read inactivity timeout in seconds (default: 120)')
    parser.add_argument('--persona', help='persona id to start with (see /persona)')
    parser.add_argument('--persona-dir', type=Path,
                        default=Path(__file__).resolve().parent / 'personas')
    parser.add_argument('--json-schema', type=Path,
                        help='validate responses against an inline JSON Schema file')
    parser.add_argument('--json-attempts', type=int, choices=range(1, 6), default=2,
                        help='total generation attempts per JSON answer (default: 2)')
    parser.add_argument('--workspace', type=Path,
                        help='allow /read beneath this directory (read-only, Linux/WSL)')
    parser.add_argument('--allow-create', action='store_true',
                        help='enable /save of new files after confirmation; requires --workspace')
    args = parser.parse_args()
    if not args.model.strip():
        parser.error('--model cannot be empty')
    if args.allow_create and args.workspace is None:
        parser.error('--allow-create requires --workspace')
    try:
        searcher = (SearxSearch(args.search_url, args.search_timeout, args.search_results)
                    if args.search_url else None)
    except SearchError as error:
        print(f'Cannot configure search: {error}', file=sys.stderr)
        return 1
    try:
        guardrails = Guardrails.from_file(args.guardrails) if args.guardrails else None
    except GuardrailError as error:
        print(f'Cannot configure guardrails: {error}', file=sys.stderr)
        return 1
    try:
        json_output = JsonOutput.from_file(args.json_schema) if args.json_schema else None
    except StructuredOutputError as error:
        print(f'Cannot configure JSON mode: {error}', file=sys.stderr)
        return 1
    try:
        prompt_store = PromptVersionStore(default_file=args.system_prompt)
        active_prompt_obj = prompt_store.get_active_version('system')
        if active_prompt_obj:
            prompt = active_prompt_obj['content']
        else:
            prompt = args.system_prompt.read_text(encoding='utf-8').strip()
            if not prompt:
                raise ValueError('system prompt file is empty')
    except (OSError, UnicodeError, ValueError) as error:
        print(f'Cannot load system prompt: {error}', file=sys.stderr)
        return 1
    store = None
    if args.docs_dir:
        from retrieval.store import VectorStore
        from retrieval.rag import ingest
        store = VectorStore(':memory:')
        try:
            count = ingest(str(args.docs_dir), store)
            print(f'Ingested {count} chunks from {args.docs_dir}')
        except Exception as error:
            print(f'Ingestion failed: {error}', file=sys.stderr)
            store = None
    try:
        personas = load_personas(args.persona_dir)
    except PersonaError as error:
        print(f'Cannot load personas: {error}', file=sys.stderr)
        return 1
    if args.persona is not None and args.persona not in personas:
        print(f'Unknown persona {args.persona!r}. Available: {", ".join(personas)}',
              file=sys.stderr)
        return 1
    try:
        session_store = SessionStore(
            Path(__file__).resolve().parent / 'sensai_sessions.db'
        )
    except DatabaseError as error:
        print(f'Cannot open session database: {error}', file=sys.stderr)
        return 1
    try:
        access_class = WorkspaceWriter if args.allow_create else WorkspaceReader
        reader = access_class(args.workspace) if args.workspace is not None else None
    except FileAccessError as error:
        print(f'Cannot configure workspace: {error}', file=sys.stderr)
        return 1
    try:
        return run_chat(
            args.model,
            prompt,
            args.host,
            args.timeout,
            personas,
            args.persona,
            json_output,
            args.json_attempts,
            reader,
            store=store,
            session_store=session_store,
            guardrails=guardrails,
            searcher=searcher,
        )
    finally:
        if reader is not None:
            reader.close()

if __name__ == '__main__':
    sys.exit(main())
