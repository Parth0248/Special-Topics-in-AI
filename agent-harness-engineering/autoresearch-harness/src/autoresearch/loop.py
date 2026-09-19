"""The research loop.

    propose a change → run it → compare → keep or revert → repeat

That is the whole idea, and the literature suggests it is enough: FML-bench
found greedy hill climbing roughly matches tree search on ML research tasks,
so this deliberately does not build a search tree.

What makes it work is not the proposing. It is the discipline around it:

- The evaluator is fixed and the harness cannot edit it. A loop allowed to
  rewrite its own scoring finds the bug in the scorer long before it finds a
  better model.
- Every candidate is judged against the best so far, not the previous one, so
  a lucky run cannot drag the baseline down.
- A candidate that fails to run is a loss, not an error. The loop keeps going.
- Reverting restores the exact previous bytes, not a regenerated approximation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from .experiment import Evaluation, Experiment
from .journal import Attempt, Journal
from .llm import LLM

SYSTEM_PROMPT = """You improve a machine-learning solution by rewriting one file.

You are given the current solution, its score, and what has already been tried.
Propose the single change you think most likely to raise the score.

Rules:
- Reply with the complete new file, nothing else. No commentary, no diff.
- Keep the `build_model()` function and its contract: it takes no arguments and
  returns an unfitted scikit-learn estimator or Pipeline.
- Use only scikit-learn and numpy.
- Change one thing at a time. A rewrite that changes five things teaches
  nothing when the score moves, because you cannot tell which one did it.
- Do not try to read, write, or affect anything outside this file.

Begin the file with a one-line comment starting `# IDEA:` naming what you
changed and why, in plain language."""

IDEA_LINE = re.compile(r"^#\s*IDEA:\s*(.+)$", re.M)
CODE_FENCE = re.compile(r"^```(?:python)?\n(.*?)^```", re.M | re.S)

# Left alone, this loop runs until the money does.
DEFAULT_MAX_ITERATIONS = 10


def extract_source(reply: str) -> str:
    """Pull the file out of a reply that may or may not be fenced."""
    fenced = CODE_FENCE.search(reply)
    return (fenced.group(1) if fenced else reply).strip() + "\n"


def extract_idea(source: str, fallback: str = "unlabelled change") -> str:
    match = IDEA_LINE.search(source)
    return match.group(1).strip() if match else fallback


@dataclass
class Progress:
    """What the loop reports as it goes, so a front end can show it."""

    iteration: int
    idea: str
    evaluation: Evaluation
    best: float
    kept: bool


@dataclass
class ResearchLoop:
    """Hill-climbs a solution file against a fixed evaluator."""

    llm: LLM
    experiment: Experiment
    journal: Journal
    max_iterations: int = DEFAULT_MAX_ITERATIONS
    on_progress: Callable[[Progress], None] | None = None
    best_score: float = field(init=False, default=0.0)

    def run(self) -> str:
        """Run until the iteration budget is spent. Returns a summary."""
        baseline = self.experiment.evaluate()
        if not baseline.ok:
            return (
                "The starting solution does not run, so there is nothing to "
                f"improve on: {baseline.failed_because}\n\n{baseline.output}"
            )

        self.best_score = baseline.score
        best_source = self.experiment.read_solution()

        for iteration in range(1, self.max_iterations + 1):
            reply = self.llm.respond(
                [self._prompt(best_source)], SYSTEM_PROMPT
            ).text
            candidate = extract_source(reply)
            idea = extract_idea(candidate)

            self.experiment.write_solution(candidate)
            evaluation = self.experiment.evaluate()

            score_to_beat = self.best_score
            kept = evaluation.ok and evaluation.score > score_to_beat

            if kept:
                self.best_score = evaluation.score
                best_source = candidate
            else:
                # Restore the exact bytes that scored best, not a regeneration
                # of them. Anything else lets drift accumulate across reverts.
                self.experiment.write_solution(best_source)

            self.journal.record(
                Attempt(
                    iteration=iteration,
                    idea=idea,
                    score=evaluation.score,
                    best_before=score_to_beat,
                    kept=kept,
                    reason=evaluation.failed_because
                    or ("improved" if kept else "no improvement"),
                )
            )

            if self.on_progress:
                self.on_progress(
                    Progress(iteration, idea, evaluation, self.best_score, kept)
                )

        self.experiment.write_solution(best_source)
        return self.journal.summary(baseline.score)

    def _prompt(self, current_source: str):
        from google.genai import types

        return types.Content(
            role="user",
            parts=[types.Part(text=self._describe(current_source))],
        )

    def _describe(self, current_source: str) -> str:
        parts = [
            f"Current best score: {self.best_score:.6f} (higher is better).",
            "",
            "The file as it stands:",
            "",
            current_source,
        ]

        if self.journal.attempts:
            parts += ["", "Already tried:"]
            for attempt in self.journal.attempts[-8:]:
                if attempt.score is None:
                    outcome = f"failed to run — {attempt.reason}"
                else:
                    verdict = "kept" if attempt.kept else "reverted"
                    outcome = f"{attempt.score:.6f} ({verdict})"
                parts.append(f"  - {attempt.idea}: {outcome}")
            parts += [
                "",
                "Do not repeat an idea that was already reverted. Try a "
                "different kind of change.",
            ]

        return "\n".join(parts)


def load_experiment(directory: Path | str) -> Experiment:
    return Experiment(directory=Path(directory))
