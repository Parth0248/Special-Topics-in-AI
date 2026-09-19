"""The loop's job is to only ever move uphill, and to leave the best file behind.

The two ways a hill climb silently fakes progress: a revert that does not
restore the exact previous file, and a crashed candidate that ends the run
instead of counting as a loss. Both are checked here against a scripted model,
so no API key is needed.
"""

from autoresearch.experiment import Experiment
from autoresearch.journal import Journal
from autoresearch.loop import ResearchLoop, extract_idea, extract_source

# Prints whatever SCORE the solution file names, so a test can drive the loop.
EVALUATOR = """\
import re, pathlib, sys
source = pathlib.Path('solution.py').read_text(encoding='utf-8')
if 'BOOM' in source:
    raise RuntimeError('this candidate does not run')
print('SCORE: ' + re.search(r'score=([0-9.]+)', source).group(1))
"""


class ScriptedLLM:
    """Returns prepared replies in order, so the loop is deterministic."""

    model = "scripted"

    def __init__(self, replies):
        self.replies = list(replies)
        self.prompts = []

    def respond(self, messages, system_prompt):
        self.prompts.append(messages[0].parts[0].text)

        class R:
            text = self.replies.pop(0) if self.replies else "# IDEA: nothing\nscore=0.0\n"

        return R()


def _setup(tmp_path, starting_score="0.50"):
    (tmp_path / "solution.py").write_text(
        f"# IDEA: starting point\nscore={starting_score}\n", encoding="utf-8"
    )
    (tmp_path / "evaluate.py").write_text(EVALUATOR, encoding="utf-8")
    return Experiment(directory=tmp_path, timeout=60)


def _loop(tmp_path, replies, iterations):
    experiment = _setup(tmp_path)
    return ResearchLoop(
        llm=ScriptedLLM(replies),
        experiment=experiment,
        journal=Journal(tmp_path / "journal.jsonl"),
        max_iterations=iterations,
    ), experiment


def test_an_improvement_is_kept(tmp_path):
    loop, experiment = _loop(tmp_path, ["# IDEA: better\nscore=0.80\n"], 1)

    loop.run()

    assert loop.best_score == 0.80
    assert "score=0.80" in experiment.read_solution()


def test_a_worse_candidate_is_reverted_byte_for_byte(tmp_path):
    loop, experiment = _loop(tmp_path, ["# IDEA: worse\nscore=0.10\n"], 1)
    before = experiment.read_solution()

    loop.run()

    assert loop.best_score == 0.50
    assert experiment.read_solution() == before


def test_an_equal_score_is_not_an_improvement(tmp_path):
    loop, experiment = _loop(tmp_path, ["# IDEA: same\nscore=0.50\n"], 1)

    loop.run()

    assert loop.best_score == 0.50
    assert "starting point" in experiment.read_solution()


def test_a_crashing_candidate_counts_as_a_loss_and_the_loop_continues(tmp_path):
    loop, experiment = _loop(
        tmp_path,
        ["# IDEA: explodes\nBOOM\nscore=0.99\n", "# IDEA: fine\nscore=0.70\n"],
        2,
    )

    loop.run()

    assert loop.best_score == 0.70
    assert len(loop.journal.attempts) == 2
    assert loop.journal.attempts[0].score is None
    assert loop.journal.attempts[1].kept


def test_the_best_file_survives_a_later_regression(tmp_path):
    loop, experiment = _loop(
        tmp_path,
        [
            "# IDEA: good\nscore=0.90\n",
            "# IDEA: bad\nscore=0.20\n",
        ],
        2,
    )

    loop.run()

    assert loop.best_score == 0.90
    assert "score=0.90" in experiment.read_solution()


def test_every_candidate_is_judged_against_the_best_not_the_previous(tmp_path):
    loop, _ = _loop(
        tmp_path,
        [
            "# IDEA: high\nscore=0.90\n",
            "# IDEA: middling\nscore=0.60\n",
            "# IDEA: still middling\nscore=0.70\n",
        ],
        3,
    )

    loop.run()

    kept = [a.iteration for a in loop.journal.attempts if a.kept]
    assert kept == [1], "only the first beat the running best"


def test_the_model_is_told_what_has_already_been_tried(tmp_path):
    loop, _ = _loop(
        tmp_path,
        ["# IDEA: scaling\nscore=0.20\n", "# IDEA: another\nscore=0.30\n"],
        2,
    )

    loop.run()

    assert "scaling" in loop.llm.prompts[1]
    assert "Do not repeat" in loop.llm.prompts[1]


def test_a_broken_starting_point_stops_before_spending_anything(tmp_path):
    (tmp_path / "solution.py").write_text("BOOM\n", encoding="utf-8")
    (tmp_path / "evaluate.py").write_text(EVALUATOR, encoding="utf-8")
    llm = ScriptedLLM([])

    loop = ResearchLoop(
        llm=llm,
        experiment=Experiment(directory=tmp_path, timeout=60),
        journal=Journal(tmp_path / "journal.jsonl"),
        max_iterations=5,
    )

    summary = loop.run()

    assert "does not run" in summary
    assert llm.prompts == [], "the model must not be called at all"


def test_source_is_extracted_from_a_fenced_reply():
    reply = "Here you go:\n\n```python\n# IDEA: x\ncode here\n```\n\nHope that helps."

    assert extract_source(reply) == "# IDEA: x\ncode here\n"


def test_source_survives_an_unfenced_reply():
    assert extract_source("# IDEA: x\ncode\n") == "# IDEA: x\ncode\n"


def test_the_idea_line_is_read_back():
    assert extract_idea("# IDEA: scale the features\ncode\n") == "scale the features"


def test_a_missing_idea_line_falls_back():
    assert extract_idea("code with no label\n") == "unlabelled change"
