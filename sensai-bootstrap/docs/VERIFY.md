# Verification

## Automated run

2026-09-21: Python 3.12.14, requests 2.34.2, 10 tests passed.
Command: `python3 -m unittest discover -s tests -v`

Verified using a local fake Ollama HTTP server plus injected connection/timeout errors:
- Separate UTF-8 content chunks and streaming request flag
- Full system/user/assistant history in the next request
- No HTTP request for empty input
- Explicit model-not-found message
- Discarded partial turn after premature stream termination
- Reported error inside a stream
- Clear command retains the system prompt
- Explicit connection and timeout errors
- Cancelled generation does not alter history

This environment has no Ollama installation/model. Real inference, model quality,
GPU/CPU performance and actual Ollama compatibility must be checked on each member's machine.
No real-model pass is claimed.

## Manual checklist for every group member

1. Install Ollama, pull the chosen model and verify `curl http://localhost:11434`.
2. Run `python3 chatbot.py --model llama3.2:1b` (or your installed model).
3. Ask for a long explanation. Observe text arriving progressively.
4. Say `My name is Mark`; then ask `What is my name?`. Inspect contextual answer.
5. Submit a blank line. Check the explanation and continued input.
6. Run with `--model definitely-missing-sensai-model`. Send a question; check the pull hint.
7. Run with `--host http://127.0.0.1:1`. Send a question; check connection error.
8. Create a separate prompt file with a distinctive instruction, pass its path via
   `--system-prompt`, and observe the changed behavior. Model compliance is not guaranteed.
9. Pass a nonexistent prompt file. Check startup fails cleanly with exit code 1.
10. Interrupt a long answer using Ctrl+C. Ask a new question and check normal recovery.
11. Try `/clear`, `/exit`, and EOF at the prompt.
12. Record your machine, model, Ollama version and real-model result in the team's notes.

## Short bootstrap demonstration

Show the prompt file and startup model argument. Ask a programming question and a
follow-up, pointing out progressive output and retained context. Demonstrate an empty
input and one connection/model error. Explain the three function responsibilities.
Finish with SCOPING.md, clearly distinguishing delivered B1 from future proposals.
