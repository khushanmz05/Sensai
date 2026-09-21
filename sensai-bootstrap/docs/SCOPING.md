# Project scoping - proposal for team discussion

This is a concrete starting proposal, not a record of a team meeting.
Only B1 is implemented. The team must agree on the final use case, optional features,
owners and schedule before starting the full project.

## Use case

A software development student revising a long-running Python/C++ course wants
short explanations based on their own course notes, remembers study preferences,
and can return to the same study session on another day.
Without this system, the student must repeatedly paste notes and preferences into
a generic chat and manually find where an explanation came from. A basic local
chatbot can explain general concepts but cannot search the student's course notes.

Bootstrap demo: a student provides context about a programming exercise, asks for
an explanation and then asks a follow-up without repeating the original context.

## Feature choices and dependencies

| Feature | Why it fits | Depends on | Status |
| --- | --- | --- | --- |
| B1 CLI chat | Basic question/follow-up loop | Local Ollama, prompt file | Implemented |
| M1 Session Persistence & Profiles | Resume study and retain level/language preferences | B1 message history, session/profile storage | Proposed |
| R1 Basic RAG | Explain concepts from the student's notes | ingestion, chunking, Ollama embeddings, vector retrieval, B1 | Proposed |
| A5 Persona | Switch between explainer and reviewer during study | B1, multiple external persona definitions, runtime selection | Proposed |

A5 requires multiple profiles selectable during a session without clearing history.
A single system prompt file alone does NOT implement A5. M1 requires both saved
conversations and persistent preferences. R1 requires the complete ingestion,
embedding, storage, similarity search and context injection pipeline.

Exclude code execution, multi-agent orchestration, scheduling, web UI and web search
from this proposal: they do not help the chosen core study scenario enough to
justify their integration cost. No hidden assumption that a CLI counts as a web UI.

## Architecture before optional implementation

| Component | Responsibility | Interface |
| --- | --- | --- |
| CLI (existing) | Read a question, show progressive text | text input, chunk output |
| Session loop (existing) | Own ordered messages, commit complete turns | list of role/content objects |
| Ollama client (existing) | POST /api/chat; future POST /api/embed | messages to text chunks; text to vectors |
| Session store (future) | Validate and save/load history and preferences | session ID to messages/profile |
| Retrieval module (future) | Import notes, chunk, embed, rank relevant passages | query to passages with source IDs |
| Persona loader (future) | Load multiple personas and switch active instructions | persona name to instructions |
| Context builder (future) | Combine persona, preferences, notes and history | inputs to Ollama messages |

Future request order: CLI -> retrieve relevant notes -> assemble context -> Ollama
client -> streamed display -> commit history -> save session. Source labels must
refer to actual retrieved passages, not references invented by the model.
Imported notes are data, not instructions that override the system prompt.
Use a local JSON file for M1 initially; use atomic replacement and validate loaded
roles/content. For R1 begin with UTF-8 .txt/.md notes, a small local vector index and
cosine similarity. All embedding/model inference goes through Ollama HTTP directly.

## Stress tests

**Demo test:** import a short note on pointers, ask for an explanation referencing
that note, switch to reviewer persona and answer an exercise, then restart and
resume. Each proposed feature has a visible role in one study session.

**Time test:** rough planning estimates, not measured effort or a promise:
M1 1-2 person-days; R1 3-5; A5 1; integration and edge-case checks 2-3;
demo/docs 1. Total 8-12 person-days after bootstrap. Compare with the actual group
size and deadline, which are not supplied. Do not equate person-days to elapsed days.

**Depth test:** R1 is the hardest item. Before committing, every member should
explain chunks, embeddings, similarity, top-k selection, source attribution and
what happens when no relevant note exists. Prototype on a tiny known corpus first.

**Cut test:** drop A5 first if time is short. One study persona preserves the core
scenario. Keep M1 and R1 only if their complete scope is achievable.

## Individual exploration worksheet

Each member answers independently before the team meets:
1. Which technical problem in the catalogue interests you most, and why?
2. Who would use your proposed assistant, and for which specific task?
3. Which three features form one coherent scenario?
4. Which feature worries you most technically, and what would you prototype first?

At the meeting, compare overlaps and disagreements. Record the chosen use case,
accepted/rejected features and reasons, task owners, actual available time and
whether everyone can explain R1. These human decisions remain to be made; this
proposal does not fabricate individual answers or collective agreement.
