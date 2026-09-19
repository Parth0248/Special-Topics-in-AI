"""The boundary between the harness and the thing it is optimising.

The harness never imports the experiment. It writes a file, runs a subprocess,
and reads one number off stdout. That keeps a candidate that crashes, hangs, or
prints nonsense from being able to break the run — it is just a candidate that
scored nothing.
"""

from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

SCORE_LINE = re.compile(r"^SCORE:\s*([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)\s*$", re.M)

# A candidate that has not finished by now is not a candidate worth waiting for.
DEFAULT_TIMEOUT_SECONDS = 300


@dataclass
class Evaluation:
    """What came back from running one candidate."""

    score: float | None
    output: str
    failed_because: str = ""

    @property
    def ok(self) -> bool:
        return self.score is not None


@dataclass
class Experiment:
    """A directory holding a solution file and a fixed evaluator."""

    directory: Path
    solution_name: str = "solution.py"
    evaluator_name: str = "evaluate.py"
    timeout: int = DEFAULT_TIMEOUT_SECONDS

    def __post_init__(self) -> None:
        self.directory = Path(self.directory).expanduser().resolve()

    @property
    def solution_path(self) -> Path:
        return self.directory / self.solution_name

    @property
    def evaluator_path(self) -> Path:
        return self.directory / self.evaluator_name

    def read_solution(self) -> str:
        return self.solution_path.read_text(encoding="utf-8")

    def write_solution(self, source: str) -> None:
        self.solution_path.write_text(source, encoding="utf-8")

    def evaluate(self) -> Evaluation:
        """Run the evaluator and read the score off its output."""
        try:
            completed = subprocess.run(
                [sys.executable, str(self.evaluator_path)],
                cwd=self.directory,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
        except subprocess.TimeoutExpired:
            return Evaluation(
                None, "", f"did not finish within {self.timeout} seconds"
            )

        output = (completed.stdout + completed.stderr).strip()

        if completed.returncode != 0:
            return Evaluation(None, output, f"exited with code {completed.returncode}")

        matches = SCORE_LINE.findall(completed.stdout)
        if not matches:
            return Evaluation(None, output, "printed no SCORE line")

        # The last one wins, so a candidate cannot shadow the real score by
        # printing an earlier, better-looking one.
        return Evaluation(float(matches[-1]), output)
