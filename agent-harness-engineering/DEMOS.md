# Demo commands

Exact command sequences for recording each project. Every one has been run as written.

Set the key once, at the repository root:

```sh
cp .env.example .env     # then fill in GOOGLE_API_KEY
```

---

## 1. harness-from-scratch

```sh
cd agent-harness-engineering/harness-from-scratch
uv venv && uv pip install -e ".[dev]"
```

**The stage progression** — this is the code walkthrough spine:

```sh
git log --oneline -- .
```

Reads as: loop → tools → permissions → sandboxing → context → subagents. Walking
`git show <stage>` for each one shows exactly what that capability cost.

**Tests** (fast, no key, 62 of them):

```sh
uv run pytest -q
```

**Live agent:**

```sh
uv run harness --mode allow
```

Things worth asking it on camera, in order:

1. `read pyproject.toml and tell me what this project depends on`
   — two tools, visible in the `⚒` lines.
2. `use the reviewer specialist to review src/harness/tools.py`
   — delegation: the subagent's reads scroll past, and only its answer comes back.

**Permissions**, in a second run:

```sh
uv run harness --mode deny
```

Ask: `delete pyproject.toml` → refused, and the model reports the refusal rather than
retrying.

**Sandboxing:**

```sh
mkdir -p /tmp/playground && echo secret > /tmp/secret.txt
uv run harness --workspace /tmp/playground --mode allow
```

Ask: `read ../secret.txt` → refused, path resolves outside the workspace.

---

## 2. deepseek-harness-plugins

```sh
cd agent-harness-engineering/deepseek-harness-plugins
node scripts/link-harness.mjs /path/to/deepseek-harness
node scripts/setup.mjs
```

**Prove the plugins work** (no UI, fastest demo):

```sh
cd /path/to/deepseek-harness
node --import tsx/esm /path/to/deepseek-harness-plugins/verify.mjs
```

**Prove they load into the real harness:**

```sh
cd /path/to/deepseek-harness
pnpm dsh web \
  --patch /path/to/deepseek-harness-plugins/creator-profile.yml \
  --patch /path/to/deepseek-harness-plugins/cordis.local.yml \
  --port 3099
```

A clean boot with no `did not activate` warnings is the result. Then in the UI, select
Creator mode and ask the agent to use `remember`, then `recall`, then `pulse`.

**Prove the Creator-mode toggles took effect:**

```sh
pnpm dsh web --patch .../creator-profile.yml --patch .../cordis.local.yml --dump-config
```

Grep for `tool-plugin-manager`, `plan-mode`, `scratchpad`, `session-pulse` — all present
and enabled, and `session-title` carries the re-tuned 8-word config.

---

## 3. autoresearch-harness

```sh
cd agent-harness-engineering/autoresearch-harness
uv venv && uv pip install -e ".[dev]"
```

**Establish the baseline first** — the number the loop has to beat:

```sh
uv run python experiment/evaluate.py
```

→ `SCORE: 0.920983`

**Tests** (20, no key):

```sh
uv run pytest -q
```

Worth naming on camera: `test_a_worse_candidate_is_reverted_byte_for_byte` and
`test_a_crashing_candidate_counts_as_a_loss_and_the_loop_continues`. Those are the two
ways a hill climb silently fakes progress.

**The run itself** — about a minute for 8 iterations:

```sh
uv run autoresearch --iterations 8
```

Each line shows `kept` or `revert` as it happens. The summary at the end gives the
before/after.

**Read the journal back** — the artifact that makes the claim checkable:

```sh
cat runs/*.jsonl
```

**Undo it** so the repo is back to baseline:

```sh
uv run autoresearch --restore
```
