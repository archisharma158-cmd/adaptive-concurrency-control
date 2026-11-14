"""
src/models/predict.py
Prediction module — loads trained models and makes predictions.

This module provides a clean interface for the adaptive controller to
request predictions without knowing the internals of the ML models.
"""

import numpy as np
import pandas as pd
from pathlib import Path
import joblib
import json
from typing import Optional


class Predictor:
    """Loads a trained model and makes predictions.

    Parameters
    ----------
    model_path : str
        Path to a saved .joblib model file.
    meta_path : str, optional
        Path to the training metadata JSON.
    """

    def __init__(self, model_path: str, meta_path: Optional[str] = None):
        self.model = joblib.load(model_path)
        self.meta = {}
        if meta_path and Path(meta_path).exists():
            with open(meta_path, "r") as f:
                self.meta = json.load(f)
        self.feature_cols = self.meta.get("feature_columns", [])

    def predict(self, features: pd.DataFrame) -> np.ndarray:
        """Make predictions from a feature DataFrame.

        Parameters
        ----------
        features : pd.DataFrame
            Must contain the columns the model was trained on.

        Returns
        -------
        np.ndarray of predicted values.
        """
        if self.feature_cols:
            # Ensure column order matches training
            missing = set(self.feature_cols) - set(features.columns)
            if missing:
                # Fill missing columns with 0 (they may be lag features
                # not yet available)
                for col in missing:
                    features = features.copy()
                    features[col] = 0.0
            X = features[self.feature_cols]
        else:
            X = features.select_dtypes(include=[np.number])

        return self.model.predict(X)

    def predict_single(self, features: dict) -> float:
        """Predict a single observation from a feature dict.

        Parameters
        ----------
        features : dict
            Feature name → value.

        Returns
        -------
        float predicted value.
        """
        df = pd.DataFrame([features])
        preds = self.predict(df)
        return float(preds[0])


class EnsemblePredictor:
    """Combines multiple predictors by averaging their outputs.

    Parameters
    ----------
    predictors : list[Predictor]
        List of individual predictors.
    weights : list[float], optional
        Weights for weighted average. Defaults to equal weights.
    """

    def __init__(self, predictors: list, weights: Optional[list] = None):
        self.predictors = predictors
        if weights is None:
            self.weights = [1.0 / len(predictors)] * len(predictors)
        else:
            total = sum(weights)
            self.weights = [w / total for w in weights]

    def predict(self, features: pd.DataFrame) -> np.ndarray:
        predictions = []
        for pred, w in zip(self.predictors, self.weights):
            try:
                p = pred.predict(features) * w
                predictions.append(p)
            except Exception as e:
                print(f"  WARNING: Predictor failed: {e}")
                continue

        if not predictions:
            return np.zeros(len(features))
        return np.sum(predictions, axis=0)

    def predict_single(self, features: dict) -> float:
        df = pd.DataFrame([features])
        return float(self.predict(df)[0])

