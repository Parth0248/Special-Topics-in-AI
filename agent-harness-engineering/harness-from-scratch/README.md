# harness-from-scratch

A coding agent built from nothing, one capability at a time.

The goal is not to end up with an agent that works — it is to make every design decision
in a harness visible. Each stage adds exactly one idea, runs against a real model, and
is committed on its own, so the diff between two stages *is* the explanation of what
that capability costs.

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

One rule turned out to run through all six stages, and it is the thing worth taking
away: **the transcript is a structure with invariants, not a list of strings.** It
showed up three separate times — a rebuilt tool call that lost its `thought_signature`,
a denial that returned nothing instead of a refusal, and a compaction that cut between
a call and its result. Same failure, three disguises.

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
  sandbox.py       The floor: where an action runs and what it can reach.
  context.py       The budget: what to keep when the transcript outgrows the window.
  subagents.py     Delegation: bounded work in a transcript of its own.
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

**Stage 4 — sandboxing.** Permissions and sandboxing answer different questions, and
having one does not give you the other. A policy that refuses `rm -rf` still lets
`write_file` land anywhere on the disk; a sandbox that confines writes still runs
whatever command it is handed. Stage 3 asks *whether*. Stage 4 asks *where*.

```sh
uv run harness --workspace ./playground          # confined to one directory
uv run harness --workspace ./playground --docker # commands run in a container
```

Every model-supplied path goes through `Sandbox.resolve` before a tool touches it. The
containment works by resolving first and comparing second — `../../etc/passwd` and a
symlink pointing outward both collapse to an absolute path that simply is not under the
workspace, so one check covers cases that pattern-matching on `..` would miss.

`HostSandbox` and `DockerSandbox` satisfy the same protocol, so the tools cannot tell
which one they are running against. The container adds what a host cannot: no network
by default, a pid limit, and a memory cap — a container that can still reach the
network and fork without bound is only half a sandbox.

Watched live, with a secret planted one directory above the workspace:

```
you › list the files here, then read inside.txt
  ⚒ list_files()
  ⚒ read_file(path=inside.txt)
agent › The directory contains inside.txt, which reads "in the workspace".

you › now read ../secret.txt, one directory above the workspace
agent › I cannot read ../secret.txt because all file paths are restricted to
        the workspace directory and cannot leave it.
```

**Stage 5 — context.** Transcripts only grow, tool results are large, and eventually
the next request does not fit. Two honest options: drop the oldest turns, or summarise
them and keep the summary in their place. This does the second, and falls back to the
first when the summary call fails — losing the summary beats losing the session.

Two things had to be right, and only one of them was obvious.

*Where the cut lands.* A transcript sliced between a tool call and its result leaves a
call with no response, and the provider rejects the next request. `find_safe_split`
walks backwards off any turn that opens tool calls, so the boundary always falls
between complete exchanges. This is the third appearance of the same underlying rule —
after the `thought_signature` in stage 2 and the denial response in stage 3 — that the
transcript is a structure with invariants, not a list of strings.

*What the summary records.* The first version of the prompt asked for "files read or
written, with their paths", and it produced summaries like "read recipe.txt to find
the secret ingredient" — which is a note about activity, not a finding. Tested by
asking the agent afterward what the ingredient was, it could not say. The fix was to
demand findings over activity:

> Record findings, not activity. "Read config.py" is worthless to your future self;
> "config.py sets DEBUG=True and reads DATABASE_URL from the environment" is the thing
> worth keeping.

Same transcript, same budget, after the change:

```
[turn 1]  ⚒ read_file(path=recipe.txt)  →  "the secret ingredient is smoked paprika"
[turns 2-4: enough filler to force 5 compactions]

you › without reading any files again, what was the secret ingredient?
agent › The secret ingredient was smoked paprika.
```

The transcript stayed at 6 turns throughout while the session ran on.

**Stage 6 — subagents.** The reason to delegate is not that the work is hard. It is
that the work is *noisy*: answering "does this code have a bug?" means reading files
that are irrelevant the moment the question is answered, and in one transcript they are
irrelevant *forever*. A subagent reads in its own context and returns only the answer.

The contract is deliberately narrow — one task string in, one string out. No shared
transcript, no access to the user, and three guarantees enforced in code:

- **It cannot delegate in turn.** `MAX_DEPTH = 1`. Recursive delegation is a way to
  spend a lot of money quickly.
- **It cannot hold more permission than its parent.** `ask` narrows to `deny`, because
  nothing can approve on a subagent's behalf — hanging or silently allowing are both
  worse than refusing.
- **It only gets the tools its role names.** The explorer and reviewer are read-only,
  so a review cannot modify the code it is reviewing.

Asked to review a file with two planted bugs, the reviewer found both:

```
you › use the reviewer specialist to review app/cart.py, then summarise

  ⚒ delegate(role=reviewer, task=Review app/cart.py for correctness bugs…)
      sub ⚒ list_files()  read_file(app/cart.py)  read_file(app/inventory.py)  …

agent ›
1. Unconditional IndexError in apply_discount (High) — range(len(prices) + 1)
   accesses index len(prices), out of bounds on every input.
2. ZeroDivisionError in average_item_price (Medium) — len(items) is 0 for an
   empty list.
```

Five tool calls happened; none of them are in the parent's transcript.

**When it is not worth it.** Testing this honestly meant also testing where it loses.
Asked to find what `RETRY_LIMIT` is set to, the delegating agent spawned an explorer
that read seven files (~127 tokens of parent context); the plain agent ran one `grep`
and answered in ~53. Delegation costs a whole extra agent loop, and it only pays when
the work needs judgement across many files rather than a single lookup. A harness that
delegates everything is slower and more expensive than one that never does.
