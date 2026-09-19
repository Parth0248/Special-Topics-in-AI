# Agent Harness Engineering

A language model on its own produces text. A **harness** is everything around it that
turns text into action: the loop that keeps it going, the tools it can call, the rules
about what it may run, the sandbox it runs in, and the memory that survives a context
window.

This is three projects on that problem, approached from three directions.

## The three projects

### 1. [`harness-from-scratch/`](harness-from-scratch/)

A coding agent built from nothing, one capability at a time — bare loop, then tools,
then permissions, then sandboxing, then context management, then subagents. Each stage
is a separate commit, so the diff between two stages is the explanation of what that
capability costs.

**Python · Gemini**

### 2. `deepseek-harness-plugins/` — in progress

Two plugins written from scratch for the DeepSeek Harness, plus a Creator-mode profile
layering five more on top of the stock build. Where project 1 is about designing seams,
this one is about fitting into someone else's.

**TypeScript · Cordis**

### 3. `autoresearch-harness/` — planned

A harness aimed at a task where success is not a passing test but a result worth
keeping: propose a hypothesis, run the experiment, read what happened, revise.

## Why three

A harness built from scratch makes every decision explicit, because nothing is inherited.
A harness extended at its seams shows which of those decisions survive contact with
production constraints. A harness pointed at research asks the harder question — whether
the loop can make progress when no one has written down what "done" means.

## Running them

Each project has its own README and its own setup. All of them read secrets from the
`.env` at the repository root:

```sh
cp ../.env.example ../.env
```
