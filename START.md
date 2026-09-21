# Quick Start — Ubuntu / WSL

Extract the archive and open a terminal in `sensai-bootstrap`.
Python 3.10 or newer is required.

1. Install Ollama: https://ollama.com/download/linux
2. Create the environment and download a model:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
ollama pull llama3.2:1b
```

3. Check the service:

```bash
curl http://localhost:11434
```

If the connection fails, run `ollama serve` in another terminal and leave it open.

4. Start the chat:

```bash
python3 chatbot.py --model llama3.2:1b
```

Enter `My name is Mark`, then `What is my name?` to check conversation context.
Ask for a long explanation to check that output appears progressively.
`/exit` quits; `/clear` resets history. Ctrl+C during generation cancels that turn.
System instructions are in `prompts/system.txt`; restart after editing them.

5. Run automated checks:

```bash
python3 -m unittest discover -s tests -v
```

These tests simulate the API. Every member must also test with a real local model.
`docs/SCOPING.md` contains the complete preliminary six-week plan for four members:
all 28 catalogue entries, architecture, ownership and acceptance milestones.
Additional features are planned; only the mandatory base is implemented in the bootstrap.
The README, plan and user stories are in English for the repository and defense.
