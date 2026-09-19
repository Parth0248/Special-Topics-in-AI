# IDEA: Increase max_iter to 500 in HistGradientBoostingClassifier to allow further boosting iterations and improve convergence.

from sklearn.ensemble import HistGradientBoostingClassifier


def build_model():
    return HistGradientBoostingClassifier(
        max_iter=500, min_samples_leaf=10, random_state=0
    )
