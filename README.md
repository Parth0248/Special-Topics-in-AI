# Agent Harness Engineering

A working set of projects on **agent harnesses** — the layer between a language model and
the real world that decides what the model can see, what it is allowed to do, and what
happens when it does it.

Each project here is standalone: its own dependencies, its own README, its own run
command, its own demo.

## Projects

| Project | What it is | Stack |
|---|---|---|
| [`harness-from-scratch/`](harness-from-scratch/) | A coding agent built up in numbered stages, from a bare ReAct loop to a sandboxed multi-tool harness with permissions and subagents. | Python, Gemini |
| [`deepseek-harness-plugins/`](deepseek-harness-plugins/) | Two plugins written from scratch for the DeepSeek Harness, plus a Creator-mode profile that layers 5–7 plugins on top of the stock build. | TypeScript, Cordis |
| [`autoresearch-harness/`](autoresearch-harness/) | A harness that runs a research loop end to end: propose a hypothesis, run the experiment, read the result, revise. | TBD |

## Repository layout

```
harness-from-scratch/        Project 1 — build a harness from first principles
deepseek-harness-plugins/    Project 2 — extend an existing production harness
autoresearch-harness/        Project 3 — a harness aimed at automated research
docs/                        Cross-project notes and demo recordings index
```

## Getting started

Every project reads its secrets from a local `.env` that is never committed. Copy the
template and fill in your own keys:

```sh
cp .env.example .env
```

Then follow the README inside whichever project you want to run.

## Why these three

They approach the same problem from three directions. The first builds a harness from
nothing, so every design decision is explicit. The second extends a harness that already
carries production constraints, where the interesting work is fitting into someone else's
seams. The third points a harness at a task — research — where success is not a passing
test but a result worth keeping.

## License

MIT. See [LICENSE](LICENSE).
