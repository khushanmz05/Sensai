# User stories

## Implemented bootstrap (B1)

### B1-1 - Ask a follow-up
As a programming student, I want to ask a follow-up without repeating my earlier
question, so that I can study a concept through a continuous conversation.
Acceptance criteria:
- The request contains the system prompt and all completed user/assistant turns.
- Reply chunks appear progressively, before the whole response has completed.
- A second question is sent with the first question and the completed first answer.

### B1-2 - Use a local setup
As a student with limited hardware, I want to choose my installed model and study
instructions at launch, so that I can adapt the assistant without editing code.
Acceptance criteria:
- `--model` selects the model sent to Ollama.
- `--system-prompt` loads UTF-8 instructions as the first system message.
- Missing/unreadable/empty prompt files produce a clear error and nonzero exit.

### B1-3 - Recover from mistakes
As a student preparing a demo, I want understandable errors, so that I can correct
my setup and continue the conversation.
Acceptance criteria:
- Whitespace-only input produces an explanation and sends no request.
- An unavailable model produces a pull instruction; connection errors mention the service.
- Failed or interrupted turns are excluded from later history; successful earlier turns remain.

## Proposed features - not implemented

### M1-1 - Resume study
As a student, I want to reopen a saved session, so that I can continue yesterday's work.
Acceptance criteria: saved turns reload in order; the next request includes them;
an unknown or corrupt session gives a clear error without overwriting the file.

### M1-2 - Remember preferences
As a student, I want my preferred language and level saved, so that I do not repeat them.
Acceptance criteria: preferences survive restart; they are injected at initialization;
I can edit them without modifying source code.

### R1-1 - Search my notes
As a student, I want explanations based on my notes, so that answers fit my course.
Acceptance criteria: local .txt/.md notes are chunked and embedded through Ollama;
semantic top-k passages enter the request; displayed source IDs match retrieved notes.

### R1-2 - Recognize missing evidence
As a student, I want to know when my notes do not cover a question, so that I do not
mistake general model knowledge for course material.
Acceptance criteria: irrelevant retrieval is excluded using a documented threshold;
no-match results are reported; no fabricated source ID is displayed as a real citation.

### A5-1 - Switch study mode
As a student, I want to switch from explainer to reviewer during a session, so that
I can test my understanding after reading an explanation.
Acceptance criteria: a runtime command selects an external persona definition;
prior user/assistant turns remain; the next request uses the new persona instructions.

### A5-2 - Customize a persona
As a tutor, I want to adjust an assistant's name, tone, role and scope in a file,
so that I can adapt it to my students without changing Python code.
Acceptance criteria: at least two personas can be selected; invalid definitions
produce an error; an unsuccessful switch preserves the current persona and history.
