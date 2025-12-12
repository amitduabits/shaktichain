"""
Cross-Validation for Load Forecasting (Domain 7).

Implements walk-forward cross-validation for time series forecasting evaluation.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple, Type

import numpy as np
import pandas as pd

from .evaluation_metrics import (
    ForecastEvaluation,
    evaluate_forecast,
    mape,
    rmse,
    coverage_probability,
)

logger = logging.getLogger(__name__)


@dataclass
class CVFold:
    """
    Single cross-validation fold result.

    Attributes:
        fold_idx: Fold index
        train_start: Training start index
        train_end: Training end index
        test_start: Test start index
        test_end: Test end index
        metrics: Evaluation metrics for this fold
        predictions: Predictions for test set
        actuals: Actual values for test set
    """
    fold_idx: int
    train_start: int
    train_end: int
    test_start: int
    test_end: int
    metrics: Dict[str, float] = field(default_factory=dict)
    predictions: Optional[np.ndarray] = None
    actuals: Optional[np.ndarray] = None
    lower_bound: Optional[np.ndarray] = None
    upper_bound: Optional[np.ndarray] = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "fold_idx": self.fold_idx,
            "train_start": self.train_start,
            "train_end": self.train_end,
            "test_start": self.test_start,
            "test_end": self.test_end,
            "metrics": self.metrics,
        }


@dataclass
class CVResult:
    """
    Cross-validation result.

    Attributes:
        n_splits: Number of splits
        folds: List of fold results
        mean_metrics: Mean metrics across folds
        std_metrics: Standard deviation of metrics
        all_predictions: All predictions concatenated
        all_actuals: All actuals concatenated
    """
    n_splits: int
    folds: List[CVFold] = field(default_factory=list)
    mean_metrics: Dict[str, float] = field(default_factory=dict)
    std_metrics: Dict[str, float] = field(default_factory=dict)
    all_predictions: Optional[np.ndarray] = None
    all_actuals: Optional[np.ndarray] = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "n_splits": self.n_splits,
            "folds": [f.to_dict() for f in self.folds],
            "mean_metrics": self.mean_metrics,
            "std_metrics": self.std_metrics,
        }

    def get_metric_values(self, metric: str) -> List[float]:
        """Get values of a metric across all folds."""
        return [f.metrics.get(metric, np.nan) for f in self.folds]


@dataclass
class ModelCVResult:
    """
    Cross-validation result for a specific model.

    Attributes:
        model_name: Name of the model
        cv_result: Cross-validation result
        training_time: Total training time in seconds
    """
    model_name: str
    cv_result: CVResult
    training_time: float = 0.0

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "model_name": self.model_name,
            "cv_result": self.cv_result.to_dict(),
            "training_time": self.training_time,
        }


class ForecastCrossValidator:
    """
    Walk-forward cross-validation for time series forecasting.

    Uses an expanding window approach where training data grows
    with each fold, simulating real-world forecasting conditions.
    """

    def __init__(self, n_splits: int = 5):
        """
        Initialize cross-validator.

        Args:
            n_splits: Number of CV splits
        """
        self.n_splits = n_splits

    def walk_forward_cv(
        self,
        data: pd.DataFrame,
        model_class: Type,
        horizon: int,
        min_train_size: int,
        target_col: str = "load_mw",
        model_kwargs: Optional[Dict[str, Any]] = None,
    ) -> CVResult:
        """
        Perform walk-forward cross-validation.

        Args:
            data: Input DataFrame with time series data
            model_class: Model class to instantiate
            horizon: Prediction horizon
            min_train_size: Minimum training set size
            target_col: Target column name
            model_kwargs: Additional kwargs for model constructor

        Returns:
            CVResult with fold-wise and aggregate metrics
        """
        model_kwargs = model_kwargs or {}
        n = len(data)

        # Calculate fold sizes
        available_for_test = n - min_train_size
        if available_for_test < self.n_splits * horizon:
            logger.warning(
                f"Not enough data for {self.n_splits} splits with horizon {horizon}. "
                f"Reducing splits."
            )
            self.n_splits = max(1, available_for_test // horizon)

        test_size = horizon
        fold_step = (available_for_test - test_size) // max(1, self.n_splits - 1)
        if fold_step < 1:
            fold_step = 1

        result = CVResult(n_splits=self.n_splits)
        all_predictions = []
        all_actuals = []

        for fold_idx in range(self.n_splits):
            # Calculate split indices
            train_end = min_train_size + fold_idx * fold_step
            test_start = train_end
            test_end = min(test_start + test_size, n)

            if test_end <= test_start:
                break

            # Split data
            train_df = data.iloc[:train_end].copy()
            test_df = data.iloc[test_start:test_end].copy()

            # Train model
            try:
                model = model_class(**model_kwargs)

                # Handle different model interfaces
                if hasattr(model, 'fit'):
                    model.fit(train_df, target_col=target_col)
                elif hasattr(model, 'train'):
                    model.train(train_df, target_col=target_col)

                # Generate predictions
                if hasattr(model, 'predict'):
                    pred_result = model.predict(train_df, horizon=len(test_df))
                    if isinstance(pred_result, tuple) and len(pred_result) == 3:
                        predictions, lower, upper = pred_result
                    else:
                        predictions = pred_result
                        lower = upper = None
                elif hasattr(model, 'forecast'):
                    predictions = model.forecast(len(test_df))
                    lower = upper = None
                else:
                    raise ValueError(f"Model {model_class} has no predict or forecast method")

                # Get actual values
                actuals = test_df[target_col].values

                # Ensure same length
                min_len = min(len(predictions), len(actuals))
                predictions = predictions[:min_len]
                actuals = actuals[:min_len]
                if lower is not None:
                    lower = lower[:min_len]
                    upper = upper[:min_len]

                # Calculate metrics
                fold_metrics = {
                    "mape": mape(actuals, predictions),
                    "rmse": rmse(actuals, predictions),
                }
                if lower is not None and upper is not None:
                    fold_metrics["coverage"] = coverage_probability(
                        actuals, lower, upper
                    )

                fold = CVFold(
                    fold_idx=fold_idx,
                    train_start=0,
                    train_end=train_end,
                    test_start=test_start,
                    test_end=test_end,
                    metrics=fold_metrics,
                    predictions=predictions,
                    actuals=actuals,
                    lower_bound=lower,
                    upper_bound=upper,
                )
                result.folds.append(fold)

                all_predictions.extend(predictions)
                all_actuals.extend(actuals)

            except Exception as e:
                logger.error(f"Error in fold {fold_idx}: {e}")
                fold = CVFold(
                    fold_idx=fold_idx,
                    train_start=0,
                    train_end=train_end,
                    test_start=test_start,
                    test_end=test_end,
                    metrics={"error": str(e)},
                )
                result.folds.append(fold)

        # Aggregate metrics
        if result.folds:
            metric_names = ["mape", "rmse", "coverage"]
            for metric in metric_names:
                values = [
                    f.metrics.get(metric)
                    for f in result.folds
                    if metric in f.metrics and f.metrics[metric] is not None
                ]
                if values:
                    result.mean_metrics[metric] = float(np.mean(values))
                    result.std_metrics[metric] = float(np.std(values))

        if all_predictions:
            result.all_predictions = np.array(all_predictions)
            result.all_actuals = np.array(all_actuals)

        return result

    def sliding_window_cv(
        self,
        data: pd.DataFrame,
        model_class: Type,
        horizon: int,
        window_size: int,
        target_col: str = "load_mw",
        model_kwargs: Optional[Dict[str, Any]] = None,
    ) -> CVResult:
        """
        Perform sliding window cross-validation.

        Unlike walk-forward, this uses a fixed-size training window
        that slides through the data.

        Args:
            data: Input DataFrame
            model_class: Model class to instantiate
            horizon: Prediction horizon
            window_size: Fixed training window size
            target_col: Target column name
            model_kwargs: Additional kwargs for model constructor

        Returns:
            CVResult
        """
        model_kwargs = model_kwargs or {}
        n = len(data)

        # Calculate number of possible folds
        available_folds = (n - window_size - horizon) // horizon + 1
        n_folds = min(self.n_splits, available_folds)

        if n_folds < 1:
            raise ValueError(
                f"Not enough data for sliding window CV. "
                f"Need at least {window_size + horizon} samples."
            )

        result = CVResult(n_splits=n_folds)
        all_predictions = []
        all_actuals = []

        fold_step = max(1, (n - window_size - horizon) // max(1, n_folds - 1))

        for fold_idx in range(n_folds):
            # Calculate split indices
            train_start = fold_idx * fold_step
            train_end = train_start + window_size
            test_start = train_end
            test_end = min(test_start + horizon, n)

            if test_end <= test_start or train_end > n:
                break

            # Split data
            train_df = data.iloc[train_start:train_end].copy()
            test_df = data.iloc[test_start:test_end].copy()

            try:
                model = model_class(**model_kwargs)

                if hasattr(model, 'fit'):
                    model.fit(train_df, target_col=target_col)
                elif hasattr(model, 'train'):
                    model.train(train_df, target_col=target_col)

                if hasattr(model, 'predict'):
                    pred_result = model.predict(train_df, horizon=len(test_df))
                    if isinstance(pred_result, tuple) and len(pred_result) == 3:
                        predictions, lower, upper = pred_result
                    else:
                        predictions = pred_result
                        lower = upper = None
                elif hasattr(model, 'forecast'):
                    predictions = model.forecast(len(test_df))
                    lower = upper = None
                else:
                    raise ValueError(f"Model has no predict or forecast method")

                actuals = test_df[target_col].values

                min_len = min(len(predictions), len(actuals))
                predictions = predictions[:min_len]
                actuals = actuals[:min_len]
                if lower is not None:
                    lower = lower[:min_len]
                    upper = upper[:min_len]

                fold_metrics = {
                    "mape": mape(actuals, predictions),
                    "rmse": rmse(actuals, predictions),
                }
                if lower is not None and upper is not None:
                    fold_metrics["coverage"] = coverage_probability(actuals, lower, upper)

                fold = CVFold(
                    fold_idx=fold_idx,
                    train_start=train_start,
                    train_end=train_end,
                    test_start=test_start,
                    test_end=test_end,
                    metrics=fold_metrics,
                    predictions=predictions,
                    actuals=actuals,
                    lower_bound=lower,
                    upper_bound=upper,
                )
                result.folds.append(fold)

                all_predictions.extend(predictions)
                all_actuals.extend(actuals)

            except Exception as e:
                logger.error(f"Error in sliding fold {fold_idx}: {e}")
                fold = CVFold(
                    fold_idx=fold_idx,
                    train_start=train_start,
                    train_end=train_end,
                    test_start=test_start,
                    test_end=test_end,
                    metrics={"error": str(e)},
                )
                result.folds.append(fold)

        # Aggregate metrics
        if result.folds:
            for metric in ["mape", "rmse", "coverage"]:
                values = [
                    f.metrics.get(metric)
                    for f in result.folds
                    if metric in f.metrics and f.metrics[metric] is not None
                ]
                if values:
                    result.mean_metrics[metric] = float(np.mean(values))
                    result.std_metrics[metric] = float(np.std(values))

        if all_predictions:
            result.all_predictions = np.array(all_predictions)
            result.all_actuals = np.array(all_actuals)

        return result


class MultiModelCrossValidator:
    """
    Cross-validator for comparing multiple models.
    """

    def __init__(self, n_splits: int = 5):
        """
        Initialize multi-model cross-validator.

        Args:
            n_splits: Number of CV splits
        """
        self.n_splits = n_splits
        self.cv = ForecastCrossValidator(n_splits)

    def compare_models(
        self,
        data: pd.DataFrame,
        models: Dict[str, Tuple[Type, Dict[str, Any]]],
        horizon: int,
        min_train_size: int,
        target_col: str = "load_mw",
    ) -> Dict[str, ModelCVResult]:
        """
        Compare multiple models using cross-validation.

        Args:
            data: Input DataFrame
            models: Dict mapping model name to (model_class, kwargs)
            horizon: Prediction horizon
            min_train_size: Minimum training set size
            target_col: Target column name

        Returns:
            Dict mapping model name to ModelCVResult
        """
        import time

        results = {}

        for model_name, (model_class, model_kwargs) in models.items():
            logger.info(f"Cross-validating {model_name}...")

            start_time = time.time()
            try:
                cv_result = self.cv.walk_forward_cv(
                    data=data,
                    model_class=model_class,
                    horizon=horizon,
                    min_train_size=min_train_size,
                    target_col=target_col,
                    model_kwargs=model_kwargs,
                )
                training_time = time.time() - start_time

                results[model_name] = ModelCVResult(
                    model_name=model_name,
                    cv_result=cv_result,
                    training_time=training_time,
                )

                logger.info(
                    f"{model_name}: MAPE={cv_result.mean_metrics.get('mape', np.nan):.2f}%, "
                    f"RMSE={cv_result.mean_metrics.get('rmse', np.nan):.2f}"
                )

            except Exception as e:
                logger.error(f"Error cross-validating {model_name}: {e}")
                results[model_name] = ModelCVResult(
                    model_name=model_name,
                    cv_result=CVResult(n_splits=self.n_splits),
                    training_time=time.time() - start_time,
                )

        return results

    def get_best_model(
        self,
        results: Dict[str, ModelCVResult],
        metric: str = "mape",
    ) -> str:
        """
        Get the best model based on a metric.

        Args:
            results: Model comparison results
            metric: Metric to use for comparison (lower is better)

        Returns:
            Name of best model
        """
        best_name = None
        best_value = float('inf')

        for name, result in results.items():
            value = result.cv_result.mean_metrics.get(metric, float('inf'))
            if value < best_value:
                best_value = value
                best_name = name

        return best_name

    def get_ranking(
        self,
        results: Dict[str, ModelCVResult],
        metric: str = "mape",
    ) -> List[Tuple[str, float]]:
        """
        Get model ranking based on a metric.

        Args:
            results: Model comparison results
            metric: Metric to use for ranking

        Returns:
            List of (model_name, metric_value) sorted by metric
        """
        ranking = []
        for name, result in results.items():
            value = result.cv_result.mean_metrics.get(metric, float('inf'))
            ranking.append((name, value))

        ranking.sort(key=lambda x: x[1])
        return ranking


def cross_validate_forecaster(
    data: pd.DataFrame,
    model_class: Type,
    horizon: int = 24,
    n_splits: int = 5,
    min_train_size: int = 168,
    target_col: str = "load_mw",
    model_kwargs: Optional[Dict[str, Any]] = None,
) -> CVResult:
    """
    Convenience function for cross-validation.

    Args:
        data: Input DataFrame
        model_class: Model class
        horizon: Prediction horizon
        n_splits: Number of CV splits
        min_train_size: Minimum training size
        target_col: Target column
        model_kwargs: Model constructor kwargs

    Returns:
        CVResult
    """
    cv = ForecastCrossValidator(n_splits)
    return cv.walk_forward_cv(
        data=data,
        model_class=model_class,
        horizon=horizon,
        min_train_size=min_train_size,
        target_col=target_col,
        model_kwargs=model_kwargs,
    )
