"""The harness/experiment boundary.

A candidate that crashes, hangs, or prints nonsense must come back as a failed
candidate — never as an exception that ends the run.
"""

import pytest

from autoresearch.experiment import Experiment

EVALUATOR = """\
import sys
{body}
"""


@pytest.fixture
def experiment(tmp_path):
    (tmp_path / "solution.py").write_text("x = 1\n", encoding="utf-8")
    return Experiment(directory=tmp_path, timeout=30)


def _evaluator(experiment: Experiment, body: str) -> None:
    experiment.evaluator_path.write_text(EVALUATOR.format(body=body), encoding="utf-8")


def test_a_clean_run_yields_its_score(experiment):
    _evaluator(experiment, "print('SCORE: 0.875')")

    result = experiment.evaluate()

    assert result.ok
    assert result.score == 0.875


def test_scientific_notation_is_read(experiment):
    _evaluator(experiment, "print('SCORE: 1.5e-3')")

    assert experiment.evaluate().score == pytest.approx(0.0015)


def test_a_crash_is_a_failed_candidate_not_an_exception(experiment):
    _evaluator(experiment, "raise ValueError('bad candidate')")

    result = experiment.evaluate()

    assert not result.ok
    assert result.score is None
    assert "exited with code" in result.failed_because
    assert "bad candidate" in result.output


def test_a_nonzero_exit_without_a_crash_still_fails(experiment):
    _evaluator(experiment, "print('SCORE: 0.99')\nsys.exit(3)")

    result = experiment.evaluate()

    assert not result.ok
    assert "code 3" in result.failed_because


def test_missing_score_line_fails(experiment):
    _evaluator(experiment, "print('all done, looks great')")

    result = experiment.evaluate()

    assert not result.ok
    assert "no SCORE line" in result.failed_because


def test_a_hang_is_cut_off(tmp_path):
    (tmp_path / "solution.py").write_text("x = 1\n", encoding="utf-8")
    experiment = Experiment(directory=tmp_path, timeout=2)
    _evaluator(experiment, "import time; time.sleep(30)")

    result = experiment.evaluate()

    assert not result.ok
    assert "did not finish" in result.failed_because


def test_the_last_score_wins_so_an_earlier_line_cannot_shadow_it(experiment):
    _evaluator(experiment, "print('SCORE: 0.99')\nprint('SCORE: 0.11')")

    assert experiment.evaluate().score == 0.11


def test_writing_and_reading_the_solution_round_trips(experiment):
    source = "def build_model():\n    return None  # café ☕\n"

    experiment.write_solution(source)

    assert experiment.read_solution() == source
