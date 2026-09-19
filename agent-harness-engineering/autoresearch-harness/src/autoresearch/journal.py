"""A durable record of what the loop tried.

A run that only prints to the terminal leaves nothing behind. The journal is
append-only JSONL written as each iteration finishes, so a run that is
interrupted still has everything up to that point, and a finished run can be
read back without rerunning anything.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class Attempt:
    """One turn of the loop."""

    iteration: int
    idea: str
    score: float | None
    best_before: float
    kept: bool
    reason: str
    when: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )

    @property
    def delta(self) -> float | None:
        return None if self.score is None else self.score - self.best_before


class Journal:
    """Appends attempts to a JSONL file and can summarise them afterwards."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.attempts: list[Attempt] = []

    def record(self, attempt: Attempt) -> None:
        self.attempts.append(attempt)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(attempt)) + "\n")

    @property
    def kept(self) -> list[Attempt]:
        return [a for a in self.attempts if a.kept]

    def summary(self, starting_score: float) -> str:
        if not self.attempts:
            return "No attempts were made."

        best = max((a.score for a in self.attempts if a.score is not None), default=None)
        final = best if best is not None else starting_score
        failures = sum(1 for a in self.attempts if a.score is None)

        lines = [
            f"{len(self.attempts)} attempts, {len(self.kept)} kept, {failures} failed to run.",
            f"Score: {starting_score:.6f} -> {final:.6f} "
            f"({final - starting_score:+.6f}).",
        ]

        if self.kept:
            lines.append("\nWhat worked:")
            lines.extend(
                f"  {a.iteration}. {a.idea} ({a.score:.6f}, {a.delta:+.6f})"
                for a in self.kept
            )

        return "\n".join(lines)
