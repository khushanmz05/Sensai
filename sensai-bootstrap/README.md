# Sensai bootstrap

Python 3.10+ CLI chatbot using the Ollama HTTP API directly. No LLM framework or Ollama SDK.
This submission implements the bootstrap, not the full Sensai feature catalogue.

## Setup (Linux / WSL)

Install Ollama using the instructions at https://ollama.com/download/linux
(the bootstrap subject also gives `curl -fsSL https://ollama.com/install.sh | sh`).
Then, inside this project folder:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
ollama pull llama3.2:1b
curl http://localhost:11434
python3 chatbot.py --model llama3.2:1b
```

`llama3.2:1b` is an example lightweight model; any installed chat model can be selected.
If Ollama is not running, open another terminal and run `ollama serve`.
If the service already owns port 11434, do not start a second instance.
On Ubuntu, if venv is unavailable, install `python3-venv` using your package manager.
Each group member must install/pull a model and perform the real-model checklist below.
No API key is needed for a local model.

## Windows PowerShell

Install Ollama from https://ollama.com/download/windows and launch it, then:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
ollama pull llama3.2:1b
.\.venv\Scripts\python.exe chatbot.py --model llama3.2:1b
```

## Usage

```bash
python3 chatbot.py --model llama3.2:1b
python3 chatbot.py --model YOUR_INSTALLED_MODEL --system-prompt prompts/system.txt
python3 chatbot.py --model llama3.2:1b --host http://localhost:11434 --timeout 240
python3 chatbot.py --help
```

Edit `prompts/system.txt` to change the system prompt; restart to reload it.
The default prompt is located relative to the script, so other working directories work.
Custom relative prompt paths are resolved relative to your current working directory.
The model is explicitly required on the command line; no model name is hardcoded.

- `/exit`: quit
- `/clear`: clear turns, retain the system prompt
- Ctrl+C during generation: discard this turn and continue chatting
- Ctrl+C or EOF at the input prompt: exit cleanly

## Implemented requirements

| Bootstrap requirement | Implementation |
| --- | --- |
| CLI and selectable model | argparse, required `--model` |
| Progressive responses | `stream=True`, read NDJSON chunks, print with flush |
| In-session history | resend system prompt + successful previous turns + new user turn |
| Prompt loaded from a file | `--system-prompt`, UTF-8 file validation |
| Missing model | HTTP 404 with model pull instruction |
| Empty input | explanation, no request sent |
| Connection failure | explicit error, return to input |

Also handles timeouts, HTTP errors, errors within streams, malformed responses,
empty answers and streams that end without a completion marker.
Only a complete question/answer pair is committed to history. Partial visible output
is not reused after an error. All model calls use `POST /api/chat` directly.

## Files and architecture

- `chatbot.py`: CLI, prompt loading, session loop and direct HTTP streaming
- `prompts/system.txt`: editable assistant instructions
- `requirements.txt`: sole external dependency
- `tests/test_chatbot.py`: local HTTP contract and error tests
- `docs/SCOPING.md`: proposed use case, justified future features, dependencies and architecture
- `docs/USER_STORIES.md`: stories and observable acceptance criteria
- `docs/VERIFY.md`: automated results and manual demo checklist
- `START_RU.md`: short Russian setup guide

`main()` loads configuration and the prompt. `run_chat()` owns history and terminal IO.
`stream_reply()` sends the message list and yields response text without managing history.
There is no file access tool, persistence, RAG or code execution in this bootstrap.

## Tests

```bash
python3 -m unittest discover -s tests -v
```

Tests start an ephemeral localhost HTTP server and exercise the API contract.
They do not need Ollama and do not establish model answer quality. For real-model
verification use `docs/VERIFY.md`.

## Limits

History is in RAM and is lost at exit. We resend all completed turns; there is no
budgeting or summarization and very long sessions can exceed the model context.
The selected model controls response quality and may not reliably obey the prompt.
The timeout is an inactivity timeout, not a total generation time limit.
Input is one line per turn. Future features in SCOPING are proposals, not delivered functionality.

## Sources

Assignment: Sensai_bootstrap.pdf, Sensai_project.pdf, features_catalog.pdf supplied with the task.
API reference: https://docs.ollama.com/api/chat
Streaming: https://docs.ollama.com/api/streaming
