# deepseek-harness-plugins

Two plugins written from scratch for the [DeepSeek Harness](https://github.com/deepseek-harness),
plus a Creator-mode profile that turns on seven more of the ones it already ships.

Where [`harness-from-scratch`](../harness-from-scratch/) is about designing seams, this
is about finding someone else's and fitting into them without forking anything. Nothing
in the harness is modified — the plugins live here and are loaded by path.

Built against DeepSeek Harness `0.1.6-alpha.2`, commit `ddefc45`.

## The two plugins

### `scratchpad` — notes that outlive the session

A conversation ends and everything the agent worked out goes with it. The next session
rediscovers the same facts: which command runs the tests, which module owns the retry
logic, which approach was already tried and abandoned.

Three tools over one JSON file: `remember`, `recall`, `forget`.

```
remember(key="test-command", value="pnpm vitest run --reporter dot")
  → Saved "test-command". 1 note on the scratchpad.

recall(key="test")
  → test-command: pnpm vitest run --reporter dot

forget(key="test-command")
  → Forgot "test-command". 0 notes remain.
```

Writing an existing key replaces it rather than duplicating. Both the note count and
note length are configuration, not constants, so the file cannot grow without bound.

### `session-pulse` — what did the agent actually do?

The transcript shows what the agent *said*. It does not show that `read_file` ran forty
times, that three of those failed, or that one tool accounts for most of the session.
That information streams past and is gone.

This listens to the harness's `tools/result` event, keeps a tally, and exposes it
through a `pulse` tool:

```
pulse()
  → 4 tool calls over ~1 minute, 1 failed.

      read_file: 3 calls, 1 failed
      write_file: 1 call

    read_file has run 3 times — worth checking you are not looping.
```

It also warns in the server log once a tool crosses a configurable repeat threshold,
which is the cheapest loop detector there is.

**The two plugins use different seams on purpose.** `scratchpad` registers tools;
`session-pulse` registers an event listener and reads the harness's own telemetry. One
demo of `defineTool` twice would have shown half as much of the framework.

## Running them

You need a DeepSeek Harness checkout that boots from source.

```sh
# 1. Point this project at your harness checkout (symlinks, no install —
#    see "One instance only" below for why).
node scripts/link-harness.mjs /path/to/deepseek-harness

# 2. Generate the patch file with absolute paths filled in.
node scripts/setup.mjs

# 3. Boot the harness with both layers.
cd /path/to/deepseek-harness
pnpm dsh web \
  --patch /path/to/this/creator-profile.yml \
  --patch /path/to/this/cordis.local.yml
```

`--patch` is a launcher flag, so it goes *before* the app's own flags (`--port`,
`--no-open`). Putting it after gets you `error: unknown option '--patch'`.

## The Creator-mode profile

The harness composes 166 plugin entries, many shipped switched off. `creator-profile.yml`
turns on seven and re-tunes two, aimed at long autonomous sessions:

| Entry | Why |
|---|---|
| `tool-plugin-manager` | Creator mode itself — lets the agent install and toggle plugins from inside a conversation. |
| `tool-fs-search` | Content search. Without it the agent can only read files it can already name. |
| `skill-filesystem`, `tool-skill` | Project conventions load from disk instead of being pasted each session. |
| `plan-mode` | A read-only planning phase before execution. |
| `compaction-basic`, `command-compact` | Folds an overlong transcript instead of failing the request. |
| `tool-subagent-control` | Lets the agent steer the subagents it spawns rather than firing them blind. |
| `session-title` | Re-tuned from 5 words to 8 — a config override, not an enable. |

Verified with `--dump-config`: all nine plus both authored plugins report `ENABLED`,
and `session-title` carries the new values.

## Two things that cost time

**One instance only.** A plugin imports `@deepseek-ai/cordis`, and Node resolves that
from the *plugin's* directory — which has no `node_modules`. The obvious fix, installing
our own copies, is wrong even though it works: the harness requires every plugin to
share the installation's single cordis instance, and a second copy makes `instanceof`
checks against the framework quietly fail. `link-harness.mjs` symlinks the harness's own
packages instead of installing anything.

**`required: false` is not the same as omitting `required`.** An optional tool parameter
leaves the key out entirely. Setting it to `false` fails the schema compiler at load
with `parameters.key.required must be true when present` — which is a good error, and
the reason the plugin failed to activate the first time.

## Layout

```
plugins/
  scratchpad/src/index.ts      Tool seam: three tools over a JSON file.
  session-pulse/src/index.ts   Event seam: listens to tools/result.
creator-profile.yml            The configured plugins — committed, machine independent.
cordis.template.yml            Patch template; {{ROOT}} is filled in by setup.
scripts/
  link-harness.mjs             Symlink the harness's packages into node_modules.
  setup.mjs                    Render cordis.local.yml from the template.
```

`cordis.local.yml` and `node_modules/` are generated and gitignored. The template and
the scripts are the committed source, so a fresh clone reproduces both with two commands.
