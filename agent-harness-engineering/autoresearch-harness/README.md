# autoresearch-harness

A harness pointed at a task with no test to pass: make this model better.

```
propose a change → run it → compare → keep or revert → repeat
```

That loop is the whole idea, and the evidence says it is enough. FML-bench found
greedy hill climbing roughly matches tree search on machine-learning research tasks,
so this deliberately does not build a search tree — the interesting engineering is in
the discipline around the loop, not in the search.

## A real run

Eight iterations against `gemini-3.8-flash`, improving a breast-cancer classifier
scored by 5-fold cross-validated ROC-AUC:

```
  1 KEEP     0.992264  Replace DecisionTreeClassifier with RandomForestClassifier
  2 revert   0.991055  Replace RandomForest with ExtraTreesClassifier
  3 revert   0.992261  Increase n_estimators to 300
  4 KEEP     0.993997  Switch to HistGradientBoostingClassifier
  5 KEEP     0.994789  Increase max_iter to 300
  6 KEEP     0.994847  Decrease min_samples_leaf to 10
  7 revert   0.994847  Increase max_leaf_nodes to 63
  8 KEEP     0.994848  Increase max_iter to 500

8 attempts, 5 kept, 0 failed to run.
Score: 0.920983 -> 0.994848 (+0.073865).
```

The shape is what a working hill climb looks like: a large early gain, three reverts
where the proposal was plausible but not actually better, and diminishing returns as
it converges. The winner is saved at [`runs/best-solution-20260919.py`](runs/) and
reproduces `0.994848` exactly on a fresh run.

## Running it

```sh
uv venv
uv pip install -e ".[dev]"
uv run autoresearch --iterations 8
```

Each iteration takes a few seconds — the evaluation is ~2s and the rest is the model.
Then:

```sh
uv run autoresearch --restore   # put the baseline back
uv run pytest                   # 20 tests, no API key needed
```

## The contract

The harness never imports the experiment. It writes a file, runs a subprocess, and
reads one number:

```
stdout ends with `SCORE: <float>`, higher is better.
A non-zero exit means the candidate failed and does not count.
```

Nothing else crosses the boundary. That is what lets a candidate crash, hang, or print
nonsense without taking the run down with it.

```
experiment/
  solution.py    The file the harness rewrites. Defines build_model().
  evaluate.py    Fixed scoring. The harness never edits this.
```

## What keeps the numbers honest

An autoresearch loop that reports improvement is easy to build. One whose improvement
is *real* takes four specific constraints, and each of them is a way the loop would
otherwise fool itself:

**The evaluator is off-limits.** The harness rewrites `solution.py` and nothing else.
A loop allowed to edit its own scoring finds the bug in the scorer long before it finds
a better model — and reports a wonderful number either way.

**The scoring is fixed across candidates.** Same data, same folds, same seed. Without
that the score moves on its own and the loop happily climbs noise.

**Every candidate is judged against the best so far, not the previous one.** Otherwise
one lucky run drags the baseline down and everything after it is measured against the
wrong thing.

**A revert restores the exact previous bytes.** Not a regenerated approximation of
them. This is the one most likely to be gotten wrong quietly, because a loop that
re-derives the old file mostly works — until drift accumulates across reverts and the
final artifact is not the thing that earned the score. There is a test for it.

A failed candidate is a loss, not an error. Crashes, timeouts, and missing score lines
all count as "did not improve", the file is restored, and the loop keeps going. That
too has tests, because a hill climb that dies on its first bad proposal is not a hill
climb.

## Layout

```
src/autoresearch/
  loop.py         Propose, evaluate, keep or revert.
  experiment.py   The subprocess boundary and score parsing.
  journal.py      Append-only JSONL of every attempt.
  llm.py          The model boundary.
  cli.py          Terminal front end.
experiment/       The thing being optimised.
runs/             Journals and saved winners.
tests/            20 tests against a scripted model. No network.
```

The journal is append-only and written as each iteration finishes, so an interrupted
run still has everything up to that point, and a finished run can be read back without
rerunning anything.

## What it does not do

No multi-agent roles, no git branches per candidate, no parallel workers — all of which
exist in the systems this borrows from. One loop that demonstrably moves a number is
the deliverable; the rest is scope. The honest limitation is that hill climbing gets
stuck in local optima, and eight iterations on one dataset is a demonstration, not a
result.
