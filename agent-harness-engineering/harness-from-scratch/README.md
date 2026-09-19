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
harness · gemini-3.8-flash · type 'exit' to quit
tools: list_files, read_file, run_bash, write_file

you › what is a ReAct loop?

agent ›
A ReAct loop alternates between reasoning and acting…
```

Any Gemini model id works — set `HARNESS_MODEL` in `.env`.

## Tests

```sh
uv pip install -e ".[dev]"
uv run pytest
```

No API key needed — the suite covers the tool layer, which is where the failure
handling lives. What it pins down: an unknown tool, a tool that raises, and a call
with wrong arguments all have to come back as readable text rather than an exception,
because any of the three escaping would kill the loop.

## How it is put together

```
src/harness/
  llm.py           The model boundary. Nothing above this imports a provider SDK.
  agent.py         The loop, and the stopping rule that keeps it from running forever.
  tools.py         The registry: what the model may propose, and how proposals run.
  permissions.py   The gate: whether a proposal is allowed to become an action.
  cli.py           The terminal front end.
tests/             No network, no key.
```

The split matters more than it looks. `agent.py` asks `llm.py` for a `Response` and
never learns which provider produced it, which is what makes the backend swappable
later without touching the loop. It asks `tools.py` to run a call by name and never
learns what that tool does, which is what lets stage 3 insert a permission check
between the proposal and the action.

## Notes from the stages so far

**Stage 1 — the loop.** `MAX_STEPS` exists from the first commit on purpose. An agent
loop without a step ceiling is one malformed model response away from spending real
money.

**Stage 2 — tools.** Three things turned out to be load-bearing:

- *Tool output is context.* Every result is truncated, because one `cat` of a large
  file otherwise evicts the rest of the conversation.
- *A crashed tool must not kill the loop.* `Registry.invoke` converts exceptions into
  text, so a bad path or a failed command becomes something the model can read and
  recover from rather than a traceback.
- *The model's turn goes back into the transcript verbatim.* Sending a tool result
  without its matching call is rejected outright. On a thinking model it is stricter
  than that: each function call carries an opaque `thought_signature`, and rebuilding
  the call from its parsed name and arguments — which is the obvious way to write this —
  drops the signature and earns a `400`. The transcript has to replay the provider's
  own parts, not a reconstruction of them.

Here is stage 2 doing real work — two tools, one task, a file that exists afterward:

```
you › read notes.txt and tell me how many lines it has, then write that number
      to summary.txt

  ⚒ read_file(path=…/notes.txt)
  ⚒ write_file(path=…/summary.txt, content=3)

agent ›
I read notes.txt, found it has 3 lines, and wrote 3 to summary.txt.
```

**Stage 3 — permissions.** The gate sits between the proposal and the action, in
`Agent._dispatch`. That position is the whole point: a check that lives *inside* a tool
is not a permission system, it is a tool that sometimes refuses. Policy never sees the
result of an action, only the request for one.

Run with `--mode allow`, `--mode ask` (the default), or `--mode deny`:

```sh
uv run harness --mode deny
```

Two rules that are not the same rule:

- **Mode** covers anything that writes or executes. Reads never ask.
- **The deny list** is absolute. `rm -rf`, `mkfs`, `dd of=/dev/…`, fork bombs and
  `git push --force` are refused in `allow` mode too, because a mode is a statement
  about trust and those commands are unrecoverable regardless of who asked.

The subtle part is what a refusal returns. Denying by *not answering* the model
desyncs the transcript and the next request is rejected — the same failure class as
the dropped `thought_signature` in stage 2. So a denial is a normal tool result whose
content happens to be the refusal, and the model reads it and adapts:

```
you › delete keep.txt using a shell command

  ✗ run_bash(command=rm "…/keep.txt")

agent ›
I attempted to delete the file, but the shell execution was denied due to
permission settings.
```

Asked to run `rm -rf` in `--mode allow`, it is still stopped, and the model reports the
refusal rather than looking for another way around it.
