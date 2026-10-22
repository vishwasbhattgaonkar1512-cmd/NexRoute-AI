"""Custom estimators kept in their own module so saved models can always be unpickled."""
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, RegressorMixin


class GroupMeanRegressor(BaseEstimator, RegressorMixin):
    """Predicts the training mean of the target for each value of one column (fallback: global mean)."""

    def __init__(self, column="Ship Mode"):
        self.column = column

    def fit(self, X, y):
        y = pd.Series(np.asarray(y, dtype=float), index=X.index)
        self.means_ = y.groupby(X[self.column]).mean().to_dict()
        self.global_mean_ = float(y.mean())
        return self

    def predict(self, X):
        return X[self.column].map(self.means_).fillna(self.global_mean_).to_numpy(dtype=float)
