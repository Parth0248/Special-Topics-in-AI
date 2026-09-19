"""Terminal front end for the research loop."""

from __future__ import annotations

import argparse
import shutil
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from rich.console import Console

from .experiment import Experiment
from .journal import Journal
from .llm import LLM
from .loop import DEFAULT_MAX_ITERATIONS, Progress, ResearchLoop

# The model writes the idea lines, so they can contain anything. A Windows
# console defaults to cp1252 and raises on the first character it cannot encode,
# which would lose a finished run at the moment it prints its summary.
console = Console(legacy_windows=False, safe_box=True)

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _load_env() -> None:
    for directory in Path(__file__).resolve().parents:
        candidate = directory / ".env"
        if candidate.is_file():
            load_dotenv(candidate)
            return


def _report(progress: Progress) -> None:
    evaluation = progress.evaluation

    if not evaluation.ok:
        console.print(
            f"[dim]{progress.iteration:>3}[/dim] [red]failed[/red]  "
            f"{progress.idea} [dim]({evaluation.failed_because})[/dim]"
        )
        return

    if progress.kept:
        console.print(
            f"[dim]{progress.iteration:>3}[/dim] [green]kept[/green]    "
            f"{evaluation.score:.6f}  {progress.idea}"
        )
    else:
        console.print(
            f"[dim]{progress.iteration:>3}[/dim] [yellow]revert[/yellow]  "
            f"{evaluation.score:.6f}  {progress.idea}"
        )


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="autoresearch",
        description="Improve a solution by proposing, running, and keeping or "
        "reverting changes.",
    )
    parser.add_argument(
        "--experiment",
        default=str(PROJECT_ROOT / "experiment"),
        help="Directory holding solution.py and evaluate.py.",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=DEFAULT_MAX_ITERATIONS,
        help=f"How many candidates to try. Default: {DEFAULT_MAX_ITERATIONS}.",
    )
    parser.add_argument(
        "--journal",
        default=None,
        help="Where to write the run log. Default: runs/<timestamp>.jsonl",
    )
    parser.add_argument(
        "--restore",
        action="store_true",
        help="Put the starting solution back and exit, discarding any "
        "improvements from earlier runs.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    options = _parse_args(argv)
    _load_env()

    experiment = Experiment(directory=options.experiment)

    if not experiment.solution_path.is_file():
        console.print(f"[red]No solution.py in {experiment.directory}[/red]")
        return 1
    if not experiment.evaluator_path.is_file():
        console.print(f"[red]No evaluate.py in {experiment.directory}[/red]")
        return 1

    starting = experiment.directory / "solution.starting.py"

    if options.restore:
        if not starting.is_file():
            console.print("[red]No solution.starting.py to restore from.[/red]")
            return 1
        shutil.copyfile(starting, experiment.solution_path)
        console.print("Restored the starting solution.")
        return 0

    # Kept so a run can always be undone, and so the README's baseline number
    # stays reproducible after the loop has improved on it.
    if not starting.is_file():
        shutil.copyfile(experiment.solution_path, starting)

    journal_path = Path(
        options.journal
        or PROJECT_ROOT / "runs" / f"{datetime.now():%Y%m%d-%H%M%S}.jsonl"
    )

    try:
        llm = LLM()
    except RuntimeError as exc:
        console.print(f"[red]{exc}[/red]")
        return 1

    loop = ResearchLoop(
        llm=llm,
        experiment=experiment,
        journal=Journal(journal_path),
        max_iterations=options.iterations,
        on_progress=_report,
    )

    console.print(f"[dim]autoresearch · {llm.model} · {options.iterations} iterations[/dim]")
    console.print(f"[dim]experiment: {experiment.directory}[/dim]")
    console.print(f"[dim]journal: {journal_path}[/dim]\n")

    summary = loop.run()

    console.print(f"\n{summary}")
    console.print(f"\n[dim]Full log: {journal_path}[/dim]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
