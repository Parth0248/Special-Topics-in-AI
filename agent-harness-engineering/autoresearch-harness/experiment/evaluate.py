"""Score whatever `solution.py` currently defines.

The contract between the harness and the experiment is deliberately narrow:

    stdout ends with a line `SCORE: <float>`, and higher is better.
    A non-zero exit means the candidate failed and does not count.

Nothing else crosses the boundary. The harness never imports the experiment,
so a candidate that hangs, crashes, or prints garbage is a failed candidate
rather than a failed run.

This file is *not* edited by the harness. If the thing being optimised could
rewrite its own scoring, hill climbing would find the bug in the scorer long
before it found a better model — which is the most common way an autoresearch
loop produces a number that means nothing.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from sklearn.datasets import load_breast_cancer
from sklearn.model_selection import StratifiedKFold, cross_val_score

sys.path.insert(0, str(Path(__file__).parent))

# Fixed across every candidate: same data, same folds, same seed. Without this
# the score moves on its own and the loop climbs noise.
RANDOM_SEED = 0
FOLDS = 5


def main() -> int:
    from solution import build_model

    data = load_breast_cancer()
    features, labels = data.data, data.target

    splitter = StratifiedKFold(n_splits=FOLDS, shuffle=True, random_state=RANDOM_SEED)
    scores = cross_val_score(
        build_model(), features, labels, cv=splitter, scoring="roc_auc"
    )

    print(f"folds: {' '.join(f'{s:.4f}' for s in scores)}")
    print(f"std:   {np.std(scores):.4f}")
    print(f"SCORE: {np.mean(scores):.6f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
