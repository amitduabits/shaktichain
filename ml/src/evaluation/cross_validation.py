"""Time-series cross-validation for SHAKTI-CHAIN forecasting."""

import numpy as np
import pandas as pd
from typing import Optional, List, Dict, Any, Tuple, Iterator, Callable
from dataclasses import dataclass, field
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class TimeSeriesFold:
    """Container for a single cross-validation fold."""
    fold_idx: int
    train_start: pd.Timestamp
    train_end: pd.Timestamp
    val_start: pd.Timestamp
    val_end: pd.Timestamp
    train_size: int = 0
    val_size: int = 0


@dataclass
class CVResults:
    """Container for cross-validation results."""
    fold_metrics: List[Dict[str, float]]
    mean_metrics: Dict[str, float]
    std_metrics: Dict[str, float]
    folds: List[TimeSeriesFold]
    model_name: str = ""

    def to_dataframe(self) -> pd.DataFrame:
        """Convert fold metrics to DataFrame."""
        df = pd.DataFrame(self.fold_metrics)
        df.insert(0, "fold", range(len(df)))

        # Add summary row
        summary = {"fold": "mean"}
        summary.update(self.mean_metrics)
        df = pd.concat([df, pd.DataFrame([summary])], ignore_index=True)

        summary_std = {"fold": "std"}
        summary_std.update(self.std_metrics)
        df = pd.concat([df, pd.DataFrame([summary_std])], ignore_index=True)

        return df


class TimeSeriesSplit:
    """Time series cross-validation splitter.

    Implements expanding window or sliding window cross-validation
    with proper temporal ordering to prevent data leakage.

    Args:
        n_splits: Number of cross-validation folds
        train_months: Number of months for training in each fold
        val_months: Number of months for validation in each fold
        gap_hours: Gap between train and validation (to avoid leakage)
        expanding: If True, use expanding window; if False, use sliding window
        min_train_months: Minimum training months (for expanding window)
    """

    def __init__(
        self,
        n_splits: int = 5,
        train_months: int = 12,
        val_months: int = 1,
        gap_hours: int = 0,
        expanding: bool = True,
        min_train_months: Optional[int] = None,
    ):
        self.n_splits = n_splits
        self.train_months = train_months
        self.val_months = val_months
        self.gap_hours = gap_hours
        self.expanding = expanding
        self.min_train_months = min_train_months or train_months

    def split(
        self,
        data: pd.DataFrame,
        timestamp_col: str = "timestamp",
    ) -> Iterator[Tuple[np.ndarray, np.ndarray, TimeSeriesFold]]:
        """Generate train/validation indices for cross-validation.

        Args:
            data: DataFrame with time series data
            timestamp_col: Name of timestamp column

        Yields:
            Tuple of (train_indices, val_indices, fold_info)
        """
        # Ensure data is sorted by time
        data = data.sort_values(timestamp_col).reset_index(drop=True)
        timestamps = pd.to_datetime(data[timestamp_col])

        min_date = timestamps.min()
        max_date = timestamps.max()

        # Calculate fold boundaries
        total_months = (max_date.year - min_date.year) * 12 + (max_date.month - min_date.month)

        if total_months < self.train_months + self.val_months:
            raise ValueError(
                f"Not enough data for cross-validation. "
                f"Need {self.train_months + self.val_months} months, have {total_months}"
            )

        # Calculate validation start dates (working backwards from end)
        val_starts = []
        current_val_end = max_date

        for i in range(self.n_splits):
            val_end = current_val_end
            val_start = val_end - pd.DateOffset(months=self.val_months)
            val_starts.append((val_start, val_end))
            current_val_end = val_start - pd.DateOffset(hours=self.gap_hours)

        val_starts = list(reversed(val_starts))

        # Generate folds
        for fold_idx, (val_start, val_end) in enumerate(val_starts):
            if self.expanding:
                # Expanding window: always start from the beginning
                train_start = min_date
                train_end = val_start - pd.Timedelta(hours=self.gap_hours)
            else:
                # Sliding window: fixed training window size
                train_end = val_start - pd.Timedelta(hours=self.gap_hours)
                train_start = train_end - pd.DateOffset(months=self.train_months)

            # Get indices
            train_mask = (timestamps >= train_start) & (timestamps < train_end)
            val_mask = (timestamps >= val_start) & (timestamps <= val_end)

            train_indices = np.where(train_mask)[0]
            val_indices = np.where(val_mask)[0]

            if len(train_indices) == 0 or len(val_indices) == 0:
                logger.warning(f"Fold {fold_idx} has empty train or val set, skipping")
                continue

            fold_info = TimeSeriesFold(
                fold_idx=fold_idx,
                train_start=train_start,
                train_end=train_end,
                val_start=val_start,
                val_end=val_end,
                train_size=len(train_indices),
                val_size=len(val_indices),
            )

            logger.info(
                f"Fold {fold_idx}: Train {train_start.date()} to {train_end.date()} "
                f"({len(train_indices):,} samples), "
                f"Val {val_start.date()} to {val_end.date()} ({len(val_indices):,} samples)"
            )

            yield train_indices, val_indices, fold_info

    def get_n_splits(self) -> int:
        """Return number of splits."""
        return self.n_splits


class BlockingTimeSeriesSplit:
    """Blocking time series split for faster cross-validation.

    Divides data into contiguous blocks and uses each block as validation set.

    Args:
        n_splits: Number of cross-validation folds
        gap_hours: Gap between train and validation
    """

    def __init__(
        self,
        n_splits: int = 5,
        gap_hours: int = 0,
    ):
        self.n_splits = n_splits
        self.gap_hours = gap_hours

    def split(
        self,
        data: pd.DataFrame,
        timestamp_col: str = "timestamp",
    ) -> Iterator[Tuple[np.ndarray, np.ndarray, TimeSeriesFold]]:
        """Generate train/validation indices.

        Args:
            data: DataFrame with time series data
            timestamp_col: Name of timestamp column

        Yields:
            Tuple of (train_indices, val_indices, fold_info)
        """
        data = data.sort_values(timestamp_col).reset_index(drop=True)
        timestamps = pd.to_datetime(data[timestamp_col])
        n_samples = len(data)

        # Calculate block size
        block_size = n_samples // (self.n_splits + 1)

        for fold_idx in range(self.n_splits):
            # Validation block
            val_start_idx = (fold_idx + 1) * block_size
            val_end_idx = min((fold_idx + 2) * block_size, n_samples)

            # Training: all data before validation
            train_end_idx = val_start_idx - self.gap_hours

            train_indices = np.arange(0, train_end_idx)
            val_indices = np.arange(val_start_idx, val_end_idx)

            fold_info = TimeSeriesFold(
                fold_idx=fold_idx,
                train_start=timestamps.iloc[0],
                train_end=timestamps.iloc[train_end_idx - 1] if train_end_idx > 0 else timestamps.iloc[0],
                val_start=timestamps.iloc[val_start_idx],
                val_end=timestamps.iloc[val_end_idx - 1],
                train_size=len(train_indices),
                val_size=len(val_indices),
            )

            yield train_indices, val_indices, fold_info


class CrossValidator:
    """Cross-validator for time series forecasting models.

    Args:
        splitter: Time series splitter instance
        evaluator: ForecastEvaluator instance
        encoder_length: Historical context length
        decoder_length: Forecast horizon
    """

    def __init__(
        self,
        splitter: TimeSeriesSplit,
        evaluator: "ForecastEvaluator",
        encoder_length: int = 168,
        decoder_length: int = 48,
    ):
        self.splitter = splitter
        self.evaluator = evaluator
        self.encoder_length = encoder_length
        self.decoder_length = decoder_length

    def cross_validate(
        self,
        model_fn: Callable,
        data: pd.DataFrame,
        target_col: str = "load_mw",
        timestamp_col: str = "timestamp",
        feature_cols: Optional[List[str]] = None,
    ) -> CVResults:
        """Run cross-validation for a model.

        Args:
            model_fn: Function that creates and returns a fitted model
                      Signature: model_fn(train_data) -> model
            data: Full DataFrame with all data
            target_col: Target column name
            timestamp_col: Timestamp column name
            feature_cols: Optional list of feature columns

        Returns:
            CVResults with metrics across all folds
        """
        fold_metrics = []
        folds = []

        for train_idx, val_idx, fold_info in self.splitter.split(data, timestamp_col):
            logger.info(f"Processing fold {fold_info.fold_idx}...")

            # Get train and validation data
            train_data = data.iloc[train_idx].copy()
            val_data = data.iloc[val_idx].copy()

            try:
                # Fit model
                model = model_fn(train_data)

                # Generate predictions on validation set
                predictions, targets, timestamps = self._generate_predictions(
                    model, val_data, target_col, timestamp_col, feature_cols
                )

                # Evaluate
                results = self.evaluator.evaluate(
                    predictions=predictions,
                    targets=targets,
                    timestamps=timestamps,
                )

                # Extract overall metrics
                metrics = {name: result.mean for name, result in results.overall.items()}
                fold_metrics.append(metrics)
                folds.append(fold_info)

            except Exception as e:
                logger.error(f"Fold {fold_info.fold_idx} failed: {e}")
                continue

        if not fold_metrics:
            raise ValueError("All folds failed!")

        # Calculate mean and std across folds
        metrics_df = pd.DataFrame(fold_metrics)
        mean_metrics = metrics_df.mean().to_dict()
        std_metrics = metrics_df.std().to_dict()

        return CVResults(
            fold_metrics=fold_metrics,
            mean_metrics=mean_metrics,
            std_metrics=std_metrics,
            folds=folds,
        )

    def _generate_predictions(
        self,
        model: Any,
        val_data: pd.DataFrame,
        target_col: str,
        timestamp_col: str,
        feature_cols: Optional[List[str]],
    ) -> Tuple[np.ndarray, np.ndarray, pd.DatetimeIndex]:
        """Generate predictions for validation data.

        Args:
            model: Fitted model with predict method
            val_data: Validation data
            target_col: Target column name
            timestamp_col: Timestamp column name
            feature_cols: Feature column names

        Returns:
            Tuple of (predictions, targets, timestamps)
        """
        # For baseline models: use rolling predictions
        if hasattr(model, "forecast"):
            # Baseline model interface
            y = val_data[target_col]
            predictions = model.predict(horizon=len(y))
            targets = y.values
            timestamps = pd.DatetimeIndex(val_data[timestamp_col])
        else:
            # TFT/PyTorch model interface
            # This would require more complex handling
            raise NotImplementedError("PyTorch model cross-validation not implemented in this function")

        return predictions.reshape(1, -1), targets.reshape(1, -1), timestamps


def cross_validate_baselines(
    data: pd.DataFrame,
    baselines: Dict[str, "BaselineModel"],
    evaluator: "ForecastEvaluator",
    n_splits: int = 5,
    train_months: int = 12,
    val_months: int = 1,
    target_col: str = "load_mw",
    timestamp_col: str = "timestamp",
) -> Dict[str, CVResults]:
    """Cross-validate multiple baseline models.

    Args:
        data: Full DataFrame with time series data
        baselines: Dictionary of baseline models
        evaluator: ForecastEvaluator instance
        n_splits: Number of CV folds
        train_months: Training months per fold
        val_months: Validation months per fold
        target_col: Target column name
        timestamp_col: Timestamp column name

    Returns:
        Dictionary mapping model names to CVResults
    """
    splitter = TimeSeriesSplit(
        n_splits=n_splits,
        train_months=train_months,
        val_months=val_months,
        expanding=True,
    )

    all_results = {}

    for model_name, model in baselines.items():
        logger.info(f"\nCross-validating {model_name}...")

        fold_metrics = []
        folds = []

        for train_idx, val_idx, fold_info in splitter.split(data, timestamp_col):
            train_data = data.iloc[train_idx]
            val_data = data.iloc[val_idx]

            try:
                # Fit model on training data
                y_train = train_data.set_index(timestamp_col)[target_col]
                model.fit(y_train)

                # Predict on validation period
                horizon = len(val_idx)
                predictions = model.predict(horizon=horizon)

                # Get targets
                targets = val_data[target_col].values
                timestamps = pd.DatetimeIndex(val_data[timestamp_col])

                # Evaluate
                results = evaluator.evaluate(
                    predictions=predictions.reshape(1, -1),
                    targets=targets.reshape(1, -1),
                    timestamps=timestamps,
                )

                metrics = {name: result.mean for name, result in results.overall.items()}
                fold_metrics.append(metrics)
                folds.append(fold_info)

                logger.info(f"  Fold {fold_info.fold_idx}: MAPE={metrics.get('mape', np.nan):.2f}%")

            except Exception as e:
                logger.error(f"  Fold {fold_info.fold_idx} failed: {e}")
                continue

        if fold_metrics:
            metrics_df = pd.DataFrame(fold_metrics)
            cv_results = CVResults(
                fold_metrics=fold_metrics,
                mean_metrics=metrics_df.mean().to_dict(),
                std_metrics=metrics_df.std().to_dict(),
                folds=folds,
                model_name=model_name,
            )
            all_results[model_name] = cv_results

            logger.info(f"  Mean MAPE: {cv_results.mean_metrics.get('mape', np.nan):.2f}% "
                       f"± {cv_results.std_metrics.get('mape', np.nan):.2f}%")

    return all_results


def format_cv_comparison(results: Dict[str, CVResults]) -> pd.DataFrame:
    """Format cross-validation results for comparison.

    Args:
        results: Dictionary of model name to CVResults

    Returns:
        DataFrame with comparison summary
    """
    rows = []

    for model_name, cv_results in results.items():
        row = {"model": model_name}

        for metric in ["mae", "mape", "rmse", "smape", "coverage_90"]:
            mean = cv_results.mean_metrics.get(metric, np.nan)
            std = cv_results.std_metrics.get(metric, np.nan)
            row[f"{metric}_mean"] = mean
            row[f"{metric}_std"] = std
            row[metric] = f"{mean:.3f} ± {std:.3f}"

        rows.append(row)

    df = pd.DataFrame(rows)
    df = df.sort_values("mape_mean")
    df = df.set_index("model")

    return df
