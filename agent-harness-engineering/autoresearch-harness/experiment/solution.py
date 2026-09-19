"""The file the harness edits.

It must define `build_model()` returning an unfitted scikit-learn estimator
(or pipeline). Everything else — features, preprocessing, hyperparameters,
which model entirely — is open for the harness to change.

This starting point is deliberately mediocre: default settings, no scaling,
no feature work. That leaves room to climb.
"""

from sklearn.tree import DecisionTreeClassifier


def build_model():
    return DecisionTreeClassifier(random_state=0)
