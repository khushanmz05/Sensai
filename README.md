# Sensai

**A local AI assistant for learning, researching and testing software ideas.**

Sensai connects an Ollama model to project documents, external tools and a
restricted Python runtime. Use the terminal or browser to ask follow-up questions,
switch between tutor and reviewer personas, turn notes into a task list, and check
an answer against documents or live web sources.

[Get started](START.md) · [Documentation](docs/README.md) · [Feature status](docs/FEATURES.md) · [User stories](docs/USER_STORIES.md)

## What you can do

| Workflow | Where to start |
| --- | --- |
| Chat with a local model, resume sessions and switch personas | [First launch](START.md) |
| Ask questions about uploaded documents | [Document retrieval](docs/WEB_DOCUMENT_UPLOAD.md) |
| Search the web and inspect the returned sources | [Web search](docs/WEB_SEARCH.md) |
| Call project and time tools with visible results | [MCP tools](docs/MCP.md) |
| Execute Python, inspect errors and verify a correction | [Sandbox](docs/SANDBOX.md) |
| Read permitted files and approve creation of new files | [File access](docs/FILE_ACCESS.md) |
| Extract tasks or plans, track progress and export validated JSON | [Structured workspace](docs/STRUCTURED_WORKSPACE.md) |
| Inspect runs, compare prompt versions and evaluate answers | [Quality and evaluation](docs/QUALITY.md) |

The [feature register](docs/FEATURES.md) distinguishes available workflows,
partial integrations and planned work. The full catalogue is a project target,
not a claim that every feature is complete.

## Start locally

Use **Python 3.10+ and Ollama**. The supported walkthrough is **Ubuntu 24.04**, directly
or in **WSL 2**; file permissions and the sandbox require Linux. No model API key
is needed. Follow [START.md](START.md) if you have not installed these tools.

With Ollama running, open an Ubuntu terminal in the project folder:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
ollama pull qwen3:0.6b
python chatbot.py --model qwen3:0.6b
```

At `You>`, ask `Explain Python functions with one small example.` Then ask a
follow-up. Enter `/exit` to return to the terminal. The small demonstration model
is convenient for setup; its answers still need checking.

For the browser, run this in the project folder with the environment active:

```bash
export SENSAI_MODEL=qwen3:0.6b
python -m uvicorn web.app:app --host 127.0.0.1 --port 8000
```

Open [chat](http://127.0.0.1:8000), [structured workspace](http://127.0.0.1:8000/structured)
or [dashboard](http://127.0.0.1:8000/dashboard). Select **Ollama** for real chat.
Optional search, MCP and sandbox setup is covered in the linked guides above.

## How it is built

Python handles the CLI and shared chat services; FastAPI serves the browser and
API; SQLite stores sessions, results and run events. Model requests go directly
to Ollama over HTTP. MCP uses its transport SDK, and the Python sandbox uses
Bubblewrap and seccomp. There is no LLM framework.

See [architecture](docs/ARCHITECTURE.md) for request flow and the code map, and
[configuration](docs/CONFIGURATION.md) for options, storage and feature modes.

## Verify and demonstrate

```bash
python -m pip install pytest
python -m pytest tests -q
```

Some checks require the optional MCP and sandbox dependencies. See
[verification](docs/VERIFY.md) for prerequisites, recorded evidence and the
difference between automated tests and real-model demonstrations.

For the defense, use the [30-minute runbook](docs/DEMO.md) and
[persona question set](docs/PERSONA_CHECKS.md).

This is a local educational application. Model output and judge scores are not
proof of correctness; the UI and API have no authentication. Keep the documented
localhost binding. Current limitations are listed with each feature rather than
hidden behind a single “complete” label.
