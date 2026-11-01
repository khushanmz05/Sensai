# Install and run Sensai, step by step

This guide takes you from a fresh computer to your first answer in the terminal and browser.
Use **Ubuntu 24.04 LTS**, either directly on Linux or inside **WSL 2 on Windows**.
The CLI file features require Linux/WSL. This guide starts the terminal application;
the [web search guide](docs/WEB_SEARCH.md) explains the browser and a local provider
without Docker. For running generated Python with error correction (T2), use
the [sandbox setup guide](docs/SANDBOX.md) after completing the basic installation.

You need an internet connection for installation, permission to install software,
and access to this repository or a project ZIP supplied by the team. Allow several
GB of free disk space for the tools and model. Download speed and model response
time depend on your computer. No API key is needed for this local model.

## Before you copy commands

- Run commands one line at a time. Wait until a command finishes before continuing.
- Copy only the contents of command blocks, not the surrounding backticks.
- If a command fails, stop at that step and use [Troubleshooting](#troubleshooting).
- `PS C:\...>` means **Windows PowerShell**. `name@computer:~$` means the
  **Ubuntu terminal**. `You>` means you are **inside Sensai**.
- Never copy these prompt prefixes. They only show where input belongs.
- When `sudo` asks for a password, enter your **Ubuntu password** and press Enter.
  No letters or dots appear while typing; this is normal.

## 1. Windows only: install and open Ubuntu

If you already have Ubuntu in WSL, open it and continue at step 2. If you use
Ubuntu directly, open its Terminal application and also continue at step 2.

On Windows 11 or a supported Windows 10 version:

1. Open Start, search for **PowerShell**, right-click it, and choose
   **Run as administrator**.
2. Run this command in **PowerShell**:

   ```powershell
   wsl --install -d Ubuntu-24.04
   ```

3. Restart Windows if requested.
4. Open **Ubuntu 24.04 LTS** from Start. On first launch, wait for setup and
   create the requested Linux username and password. Remember this password.
5. You should now see a prompt similar to `name@computer:~$`.

**All remaining shell commands in this guide run in Ubuntu, not PowerShell.**
For WSL installation failures, follow the
[Microsoft WSL installation guide](https://learn.microsoft.com/en-us/windows/wsl/install).

## 2. Install the required tools

In the **Ubuntu terminal**, run:

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git curl zstd
python3 --version
```

Expected: a version such as `Python 3.12.x`. Sensai requires Python **3.10 or newer**.
The `python3-venv` package creates the project's isolated Python environment;
`zstd` is needed to extract the Ollama download.

## 3. Get the project

Choose **one** option below. If you already have the project in Ubuntu, open that
folder with `cd` and skip to the check at the end of this step. Do not replace your
existing work. Later examples use `~/sensai`; substitute your existing folder if
it has a different name. `~` means your Ubuntu home folder.

### Option A: download the ZIP (no Git setup needed)

1. In your browser, sign in to GitHub and open the
   [Sensai repository](https://github.com/EpitechPGE3-2026/G-AIA-500-BAR-5-1-sensai-2/tree/main).
2. Check that the selected branch is **main**. Click **Code → Download ZIP**.
   If you cannot access the repository, ask the team for access or the project ZIP.
3. Extract the ZIP. Find the extracted folder that directly contains `chatbot.py`
   and `requirements.txt` (there may be an extra outer folder).
4. On **Windows/WSL**, run these commands in Ubuntu to open your Linux home folder
   in Windows File Explorer:

   ```bash
   cd ~
   explorer.exe .
   ```

   Copy the extracted project folder into that window and name the copied folder
   `sensai`. On **native Ubuntu**, use the Files application to copy it into your
   Home folder and name it `sensai`. If that name already exists, use your existing
   project or choose another name; do not overwrite it.
5. Return to the Ubuntu terminal:

   ```bash
   cd ~/sensai
   ```

A ZIP is enough to run the app. It has no Git history, so use option B if you need
to develop on branches and push commits.

### Option B: clone with Git (if GitHub access is already configured)

In the Ubuntu terminal:

```bash
cd ~
git clone https://github.com/EpitechPGE3-2026/G-AIA-500-BAR-5-1-sensai-2.git sensai
cd ~/sensai
```

If Git asks for credentials or reports that the repository cannot be found, use
option A to run the project, or ask the team to help configure repository access.
Do not enter your GitHub account password as a Git HTTPS password.

### Check that you opened the right folder

```bash
pwd
ls chatbot.py requirements.txt
```

Expected: the project folder path, followed by both filenames with no error.
Keep this terminal open in the project folder for the following steps.

## 4. Create the Python environment and install dependencies

In the **Ubuntu terminal, inside the project folder**:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pip check
```

Expected: the prompt starts with `(.venv)` after activation, installation finishes
without an error, and the last command says `No broken requirements found.`
The `.venv` folder holds this project's Python packages. Do not use `sudo pip`.

## 5. Install and check Ollama

Ollama runs the language model. Sensai connects to it locally.
For this guide, install Ollama **inside the same Ubuntu environment as Sensai**.

If `ollama --version` already works there, skip the installation command. Otherwise,
run the [official Linux installer](https://docs.ollama.com/linux):

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

Wait for installation to finish. Then run:

```bash
ollama --version
curl http://localhost:11434
```

Expected: an Ollama version and `Ollama is running`. The shell prompt may appear
immediately after that text on the same line; that is normal.

If the connection fails, open a **second Ubuntu terminal** and run:

```bash
ollama serve
```

Leave that terminal open; it is running the model server. Return to your **first
terminal** and repeat `curl http://localhost:11434`. Continue once it returns
`Ollama is running`. If the installer already started the service, you do not need
the second terminal. If `ollama serve` reports `address already in use`, check the
URL again: a server may already be running on that port.

## 6. Download the model

In your **first Ubuntu terminal**:

```bash
ollama pull qwen3:0.6b
ollama list
```

Wait for the download to finish. Expected: `qwen3:0.6b` appears in the model list.
You only need to download it once. This small model is used for our demonstrations;
its answers can be inaccurate, repetitive or mix languages.

## 7. Start Sensai and ask a question

In the **first Ubuntu terminal**, with `(.venv)` active and inside the project:

```bash
python chatbot.py --model qwen3:0.6b
```

Expected: a Sensai banner showing `qwen3:0.6b`, session information and a `You>` prompt.

At `You>`, type this question and press Enter:

```text
Explain what a Python function is in two short sentences.
```

Wait for an answer after `Sensai>`. The first answer may take longer while the model
loads. To check conversation history, send `My name is Alex`, wait for the reply,
then send `What is my name?`. The expected answer mentions Alex, although model
quality is not guaranteed.

To leave the chat, enter:

```text
/exit
```

You should return to the Ubuntu prompt with `(.venv)`. Run installation, test and
Git commands there, never at `You>`.

## 8. Open the browser interface

Leave the CLI with `/exit`. In the same Ubuntu terminal, with `(.venv)` active:

```bash
export SENSAI_MODEL=qwen3:0.6b
python -m uvicorn web.app:app --host 127.0.0.1 --port 8000
```

Leave this terminal open. Expected: a message saying Uvicorn is running on
`http://127.0.0.1:8000`. In your browser, open that address. Select **Mode → Ollama**,
check the model name, and send `Explain Python functions in two sentences.`

The top navigation opens **Structured workspace** and **Dashboard**. MCP and web
search need the optional setup linked below; selecting their mode alone does not
start the required services. Click **Clear** to clear the current web conversation.
This removes its messages; the CLI's `/clear` instead starts a new saved session.

To stop the web server, return to its terminal and press **Ctrl+C**. Restart it
after changing environment variables or code. A normal page refresh is enough
after starting the updated server.

## 9. Check the installation with automated tests

Use a separate Ubuntu terminal, or stop the web server first. Inside the project:

```bash
source .venv/bin/activate
python -m pip install -r requirements-mcp.txt
python -m pip install pytest
python -m pytest tests -q
```

For the real sandbox checks, also install the Linux dependencies and run its
smoke check as described in [SANDBOX.md](docs/SANDBOX.md). Without them those
checks can be skipped; a skip is not a successful execution test.

Expected: the test run finishes without failures. The count changes as features
are added, so use [the verification record](docs/VERIFY.md) for dated results.
Most automated tests use controlled model responses; they do not establish real
model quality. Steps 7 and 8 separately check your running model connection.

## Start again tomorrow

Open Ubuntu. You do **not** need to reinstall packages or download the model again.
Use your actual project folder if it is not `~/sensai`:

```bash
cd ~/sensai
source .venv/bin/activate
curl http://localhost:11434
```

If the last command fails, start `ollama serve` in another Ubuntu terminal as in
step 5. Once Ollama responds, run in the first terminal:

```bash
python chatbot.py --model qwen3:0.6b
```

Use `/exit` to close Sensai. Optionally run `deactivate` afterward to leave the
Python environment. If you started `ollama serve` manually, Ctrl+C in its terminal
stops that server when you are finished.

## Choose your next workflow

| Task | Guide |
| --- | --- |
| Resume sessions and change preferences | [Daily use](docs/CONFIGURATION.md) |
| Upload notes and ask questions about them | [Document retrieval](docs/WEB_DOCUMENT_UPLOAD.md) |
| Extract tasks, save progress and export JSON | [Structured workspace](docs/STRUCTURED_WORKSPACE.md) |
| Read files and save approved answers | [File access](docs/FILE_ACCESS.md) |
| Use project and time tools | [MCP setup](docs/MCP.md) |
| Execute and repair Python examples | [Sandbox setup](docs/SANDBOX.md) |
| Search current web sources | [Search setup](docs/WEB_SEARCH.md) |
| Test privacy/content filtering | [Guardrails](docs/GUARDRAILS.md) |

Optional setup is intentionally separate: basic chat does not require SearXNG,
MCP servers, a sandbox or an embedding model. Exit each CLI session with `/exit`
before entering shell commands. For the complete map, open [Documentation](docs/README.md).

## Troubleshooting

| What you see | What to do |
| --- | --- |
| `ensurepip is not available` while creating `.venv` | Run `sudo apt install -y python3-venv`, then repeat step 4 from `python3 -m venv .venv`. If the error names a version-specific package, such as `python3.12-venv`, install that package too. |
| `.venv/bin/activate: No such file or directory` | Check `pwd` and `ls chatbot.py requirements.txt`. If you are in the right project, repeat step 4; the environment may not have been created successfully. |
| `python: command not found` | In the project folder, run `source .venv/bin/activate`. Before creating the environment, use `python3`, as shown in step 4. |
| `No module named requests` or `No module named jsonschema` | Activate `.venv`, then run `python -m pip install -r requirements.txt`. |
| `requirements.txt` or `chatbot.py` cannot be found | Open the folder that directly contains those files, not the outer ZIP folder. Repeat the check at the end of step 3. |
| Ollama installation says `requires zstd` | Run `sudo apt install -y zstd`, then repeat the installer command in step 5. |
| `ollama: command not found` | Complete step 5 inside Ubuntu. A Windows Ollama installation is separate from the Ubuntu installation used here. |
| `Connection failed or was interrupted` | Enter `/exit`, check `curl http://localhost:11434`, and follow step 5 if it fails. If the service responds, inspect its terminal output and retry the chat. |
| `address already in use` from `ollama serve` | Run `curl http://localhost:11434` in the first terminal. If it says `Ollama is running`, use that server; do not start another one. |
| Model not found | Leave Sensai with `/exit`, run `ollama pull qwen3:0.6b`, and start Sensai again with the same model name. |
| A response times out | After confirming Ollama is running and the model is installed, exit and retry with `python chatbot.py --model qwen3:0.6b --timeout 240`. This increases the wait between response chunks. |
| `Empty input: enter a message.` | You pressed Enter without a question. Type a question or `/exit`. |
| `/read` or `/save` is unavailable | Follow [File access](docs/FILE_ACCESS.md). `/read` requires `--workspace`; `/save` also requires `--allow-create`. |
| `Target already exists; overwriting is not allowed.` | Choose a new filename for `/save`; the app intentionally never overwrites an existing file. |

If you are still stuck, send the team the command you ran and the full error text,
plus your Ubuntu version (`cat /etc/os-release`) and Python version
(`python3 --version`). Do not include passwords or access tokens.

## More troubleshooting

| What you see | What to do |
| --- | --- |
| Browser page does not open | Keep Uvicorn running and check its terminal for errors. Open the exact localhost URL it prints. |
| Port 8000 is already in use | Use the terminal running your old Sensai server to stop it with Ctrl+C, then restart. |
| MCP or search is disabled | Configure the corresponding service using its guide, then restart Uvicorn. |
| Documents disappear after restarting | The current web document index is in memory. Upload the files again; saved chat history is separate. |
| `nomic-embed-text` is missing | Run `ollama pull nomic-embed-text` before document retrieval. |
| Sandbox installation/check fails | Follow [Sandbox setup](docs/SANDBOX.md). Generated code must never be run on the host as a workaround. |

## Verification scope

The current commands and CLI options were checked against the project on Ubuntu
24.04 in WSL. Installation troubleshooting includes errors encountered during our
own setup (`python3-venv`, `zstd` and a stopped Ollama server). The rewritten guide
has not yet been followed from start to finish on a fresh Windows installation.
