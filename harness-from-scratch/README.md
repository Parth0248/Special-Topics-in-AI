# harness-from-scratch

A coding agent built from nothing, one capability at a time.

The goal is not to end up with a agent that works — it is to make every design decision
in a harness visible. Each stage adds exactly one idea, runs, and is committed on its
own, so the diff between two stages *is* the explanation of what that capability costs.

## The stages

| Stage | Adds | The question it answers |
|---|---|---|
| 1 | The loop | What is the smallest thing that deserves to be called an agent? |
| 2 | Tools | How does a model act on the world instead of describing it? |
| 3 | Permissions | Who decides whether a proposed action is allowed to run? |
| 4 | Sandboxing | Where does the action run, and what can it reach from there? |
| 5 | Context | What happens when the conversation outgrows the window? |
| 6 | Subagents | How does one agent delegate without losing the thread? |

Stages land as separate commits. `git log --oneline` reads as the table above.

## Running it

You need a Google AI Studio key — the free tier is enough.
Get one at [aistudio.google.com/apikey](https://aistudio.google.com/apikey).

```sh
cp ../.env.example ../.env     # then paste your key into GOOGLE_API_KEY
uv venv
uv pip install -e .
uv run harness
```

You get a prompt. Type a question, get an answer, type `exit` to leave.

```
harness · gemini-2.5-flash · type 'exit' to quit

you › what is a ReAct loop?

agent ›
A ReAct loop alternates between reasoning and acting…
```

## How it is put together

```
src/harness/
  llm.py      The model boundary. Nothing above this file imports a provider SDK.
  agent.py    The loop, and the stopping rule that keeps it from running forever.
  cli.py      The terminal front end.
```

The split matters more than it looks. `agent.py` asks `llm.py` for a `Response` and
never learns which provider produced it, which is what makes the backend swappable
later without touching the loop.

## Stage 1 notes

The loop currently stops on the model's first reply, because there are no tools to run
yet. The branch that would dispatch a tool call is present and raises — it is the seam
stage 2 opens.

`MAX_STEPS` exists from the first commit on purpose. An agent loop without a step
ceiling is one malformed model response away from spending real money.
