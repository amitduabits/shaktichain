"""Forecast evaluation metrics for SHAKTI-CHAIN."""

import numpy as np
import pandas as pd
import torch
from typing import Dict, List, Optional, Union, Tuple
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)


def calculate_mape(actuals: Union[np.ndarray, List[float]], predictions: Union[np.ndarray, List[float]], epsilon: float = 1e-8) -> float:
    """Backward-compatible helper for tests expecting module-level MAPE."""
    actual_arr = np.asarray(actuals, dtype=float)
    pred_arr = np.asarray(predictions, dtype=float)
    if actual_arr.size == 0:
        return float("nan")
    return float(np.mean(np.abs(actual_arr - pred_arr) / (np.abs(actual_arr) + epsilon)) * 100.0)


def calculate_coverage(
    actuals: Union[np.ndarray, List[float]],
    lower: Union[np.ndarray, List[float]],
    upper: Union[np.ndarray, List[float]],
) -> float:
    """Backward-compatible helper for prediction interval coverage."""
    actual_arr = np.asarray(actuals, dtype=float)
    lower_arr = np.asarray(lower, dtype=float)
    upper_arr = np.asarray(upper, dtype=float)
    if actual_arr.size == 0:
        return float("nan")
    return float(np.mean((actual_arr >= lower_arr) & (actual_arr <= upper_arr)))


class TimePeriod(Enum):
    """Time period categories for Indian power grid."""
    PEAK = "peak"           # 18:00-22:00 (evening peak)
    OFF_PEAK = "off_peak"   # 22:00-06:00 (night)
    SHOULDER = "shoulder"   # 06:00-18:00 (day)


class Season(Enum):
    """Indian seasons for power demand analysis."""
    SUMMER = "summer"       # March-June (extreme demand due to AC)
    MONSOON = "monsoon"     # July-September (variable)
    WINTER = "winter"       # October-February (moderate)


class DayType(Enum):
    """Day type categories."""
    WEEKDAY = "weekday"
    WEEKEND = "weekend"
    HOLIDAY = "holiday"


@dataclass
class MetricResult:
    """Container for metric results with statistics."""
    mean: float
    std: float = 0.0
    min: float = 0.0
    max: float = 0.0
    median: float = 0.0
    count: int = 0
    values: List[float] = field(default_factory=list)

    def __repr__(self):
        return f"{self.mean:.4f} ± {self.std:.4f}"


@dataclass
class EvaluationResults:
    """Container for all evaluation results."""
    overall: Dict[str, MetricResult]
    by_horizon: Dict[int, Dict[str, MetricResult]]
    by_time_period: Dict[str, Dict[str, MetricResult]]
    by_season: Dict[str, Dict[str, MetricResult]]
    by_day_type: Dict[str, Dict[str, MetricResult]]
    metadata: Dict[str, any] = field(default_factory=dict)


class ForecastEvaluator:
    """Comprehensive forecast evaluation for SHAKTI-CHAIN.

    Implements multiple evaluation metrics across different dimensions:
    - Overall performance
    - By forecast horizon (1h, 6h, 24h, 48h)
    - By time period (peak, off-peak, shoulder)
    - By season (summer, monsoon, winter)
    - By day type (weekday, weekend, holiday)

    Args:
        quantiles: List of quantiles for probabilistic forecasts
        horizons: List of forecast horizons to evaluate
        holidays: Optional list of holiday dates
    """

    def __init__(
        self,
        quantiles: List[float] = [0.1, 0.5, 0.9],
        horizons: List[int] = [1, 6, 24, 48],
        holidays: Optional[List[pd.Timestamp]] = None,
    ):
        self.quantiles = quantiles
        self.horizons = horizons
        self.holidays = set(holidays) if holidays else set()

        # Find median quantile index
        self.median_idx = quantiles.index(0.5) if 0.5 in quantiles else len(quantiles) // 2

        # Define time period hours
        self.peak_hours = list(range(18, 22))      # 18:00-21:59
        self.off_peak_hours = list(range(22, 24)) + list(range(0, 6))  # 22:00-05:59
        self.shoulder_hours = list(range(6, 18))   # 06:00-17:59

        # Define seasons by month
        self.summer_months = [3, 4, 5, 6]          # March-June
        self.monsoon_months = [7, 8, 9]            # July-September
        self.winter_months = [10, 11, 12, 1, 2]    # October-February

    def evaluate(
        self,
        predictions: Union[np.ndarray, torch.Tensor],
        targets: Union[np.ndarray, torch.Tensor],
        timestamps: Optional[pd.DatetimeIndex] = None,
    ) -> EvaluationResults:
        """Evaluate forecasts across all dimensions.

        Args:
            predictions: Predicted values (batch, horizon, output_size, num_quantiles)
                        or (batch, horizon) for point forecasts
            targets: True values (batch, horizon, output_size) or (batch, horizon)
            timestamps: Timestamps for each prediction step (batch, horizon)

        Returns:
            EvaluationResults with metrics across all dimensions
        """
        # Convert to numpy
        if isinstance(predictions, torch.Tensor):
            predictions = predictions.cpu().numpy()
        if isinstance(targets, torch.Tensor):
            targets = targets.cpu().numpy()

        # Handle different input shapes
        is_quantile = len(predictions.shape) > 2 and predictions.shape[-1] == len(self.quantiles)

        if is_quantile:
            # Quantile predictions: (batch, horizon, output_size, num_quantiles)
            # or (batch, horizon, num_quantiles)
            if len(predictions.shape) == 4:
                predictions = predictions[:, :, 0, :]  # Take first output
                targets = targets[:, :, 0] if len(targets.shape) == 3 else targets
            point_predictions = predictions[:, :, self.median_idx]
        else:
            # Point predictions: (batch, horizon)
            point_predictions = predictions
            predictions = None  # No quantile predictions

        # Flatten for overall metrics
        flat_preds = point_predictions.flatten()
        flat_targets = targets.flatten()

        # Calculate overall metrics
        overall = self._calculate_metrics(
            flat_preds, flat_targets,
            predictions.reshape(-1, len(self.quantiles)) if predictions is not None else None,
        )

        # Calculate by horizon
        by_horizon = self._evaluate_by_horizon(point_predictions, targets, predictions)

        # Calculate by time period, season, day type if timestamps provided
        if timestamps is not None:
            by_time_period = self._evaluate_by_time_period(
                point_predictions, targets, timestamps, predictions
            )
            by_season = self._evaluate_by_season(
                point_predictions, targets, timestamps, predictions
            )
            by_day_type = self._evaluate_by_day_type(
                point_predictions, targets, timestamps, predictions
            )
        else:
            by_time_period = {}
            by_season = {}
            by_day_type = {}

        return EvaluationResults(
            overall=overall,
            by_horizon=by_horizon,
            by_time_period=by_time_period,
            by_season=by_season,
            by_day_type=by_day_type,
            metadata={
                "n_samples": len(flat_preds),
                "quantiles": self.quantiles,
                "horizons": self.horizons,
            }
        )

    def _calculate_metrics(
        self,
        predictions: np.ndarray,
        targets: np.ndarray,
        quantile_predictions: Optional[np.ndarray] = None,
    ) -> Dict[str, MetricResult]:
        """Calculate all metrics for given predictions and targets.

        Args:
            predictions: Point predictions (flattened)
            targets: True values (flattened)
            quantile_predictions: Quantile predictions (flattened, num_quantiles)

        Returns:
            Dictionary of metric names to MetricResult
        """
        metrics = {}

        # Filter out NaN values
        valid_mask = ~(np.isnan(predictions) | np.isnan(targets))
        predictions = predictions[valid_mask]
        targets = targets[valid_mask]

        if len(predictions) == 0:
            return {name: MetricResult(mean=np.nan) for name in [
                "mae", "mape", "rmse", "smape", "coverage_90", "pinball"
            ]}

        # MAE (Mean Absolute Error)
        mae = np.mean(np.abs(predictions - targets))
        metrics["mae"] = MetricResult(mean=mae, count=len(predictions))

        # RMSE (Root Mean Squared Error)
        rmse = np.sqrt(np.mean((predictions - targets) ** 2))
        metrics["rmse"] = MetricResult(mean=rmse, count=len(predictions))

        # MAPE (Mean Absolute Percentage Error)
        # Avoid division by zero
        epsilon = 1e-8
        mape = np.mean(np.abs(predictions - targets) / (np.abs(targets) + epsilon)) * 100
        metrics["mape"] = MetricResult(mean=mape, count=len(predictions))

        # SMAPE (Symmetric Mean Absolute Percentage Error)
        smape = np.mean(
            2 * np.abs(predictions - targets) / (np.abs(predictions) + np.abs(targets) + epsilon)
        ) * 100
        metrics["smape"] = MetricResult(mean=smape, count=len(predictions))

        # Quantile-based metrics
        if quantile_predictions is not None:
            quantile_predictions = quantile_predictions[valid_mask]

            # Coverage (90% prediction interval)
            if 0.1 in self.quantiles and 0.9 in self.quantiles:
                q10_idx = self.quantiles.index(0.1)
                q90_idx = self.quantiles.index(0.9)
                lower = quantile_predictions[:, q10_idx]
                upper = quantile_predictions[:, q90_idx]
                coverage = np.mean((targets >= lower) & (targets <= upper))
                metrics["coverage_90"] = MetricResult(mean=coverage, count=len(predictions))

                # Prediction interval width
                interval_width = np.mean(upper - lower)
                metrics["interval_width"] = MetricResult(mean=interval_width, count=len(predictions))

            # Pinball loss for each quantile
            pinball_losses = []
            for i, q in enumerate(self.quantiles):
                errors = targets - quantile_predictions[:, i]
                pinball = np.mean(np.maximum(q * errors, (q - 1) * errors))
                pinball_losses.append(pinball)
                metrics[f"pinball_q{int(q*100)}"] = MetricResult(mean=pinball, count=len(predictions))

            # Average pinball loss
            metrics["pinball_avg"] = MetricResult(mean=np.mean(pinball_losses), count=len(predictions))

            # Winkler score (for 80% PI)
            if 0.1 in self.quantiles and 0.9 in self.quantiles:
                q10_idx = self.quantiles.index(0.1)
                q90_idx = self.quantiles.index(0.9)
                lower = quantile_predictions[:, q10_idx]
                upper = quantile_predictions[:, q90_idx]
                alpha = 0.2  # For 80% PI

                width = upper - lower
                below = 2 / alpha * (lower - targets) * (targets < lower)
                above = 2 / alpha * (targets - upper) * (targets > upper)
                winkler = np.mean(width + below + above)
                metrics["winkler"] = MetricResult(mean=winkler, count=len(predictions))

        return metrics

    def _evaluate_by_horizon(
        self,
        predictions: np.ndarray,
        targets: np.ndarray,
        quantile_predictions: Optional[np.ndarray] = None,
    ) -> Dict[int, Dict[str, MetricResult]]:
        """Evaluate metrics by forecast horizon.

        Args:
            predictions: Point predictions (batch, horizon)
            targets: True values (batch, horizon)
            quantile_predictions: Quantile predictions (batch, horizon, num_quantiles)

        Returns:
            Dictionary mapping horizon to metrics
        """
        results = {}
        max_horizon = predictions.shape[1]

        for horizon in self.horizons:
            if horizon <= max_horizon:
                # Get predictions at this specific horizon
                h_preds = predictions[:, horizon - 1]
                h_targets = targets[:, horizon - 1]

                if quantile_predictions is not None:
                    h_quant = quantile_predictions[:, horizon - 1, :]
                else:
                    h_quant = None

                results[horizon] = self._calculate_metrics(h_preds, h_targets, h_quant)

        return results

    def _evaluate_by_time_period(
        self,
        predictions: np.ndarray,
        targets: np.ndarray,
        timestamps: pd.DatetimeIndex,
        quantile_predictions: Optional[np.ndarray] = None,
    ) -> Dict[str, Dict[str, MetricResult]]:
        """Evaluate metrics by time period (peak, off-peak, shoulder).

        Args:
            predictions: Point predictions (batch, horizon)
            targets: True values (batch, horizon)
            timestamps: Timestamps (batch, horizon) or flattened
            quantile_predictions: Quantile predictions

        Returns:
            Dictionary mapping time period to metrics
        """
        results = {}

        # Flatten arrays
        flat_preds = predictions.flatten()
        flat_targets = targets.flatten()

        if len(timestamps) != len(flat_preds):
            # Timestamps might be (batch,) instead of (batch, horizon)
            # Create hourly timestamps for each prediction
            timestamps = self._expand_timestamps(timestamps, predictions.shape)

        flat_ts = pd.DatetimeIndex(timestamps.flatten())
        hours = flat_ts.hour

        if quantile_predictions is not None:
            flat_quant = quantile_predictions.reshape(-1, len(self.quantiles))
        else:
            flat_quant = None

        # Peak hours (18:00-22:00)
        peak_mask = np.isin(hours, self.peak_hours)
        if np.any(peak_mask):
            results[TimePeriod.PEAK.value] = self._calculate_metrics(
                flat_preds[peak_mask], flat_targets[peak_mask],
                flat_quant[peak_mask] if flat_quant is not None else None
            )

        # Off-peak hours (22:00-06:00)
        off_peak_mask = np.isin(hours, self.off_peak_hours)
        if np.any(off_peak_mask):
            results[TimePeriod.OFF_PEAK.value] = self._calculate_metrics(
                flat_preds[off_peak_mask], flat_targets[off_peak_mask],
                flat_quant[off_peak_mask] if flat_quant is not None else None
            )

        # Shoulder hours (06:00-18:00)
        shoulder_mask = np.isin(hours, self.shoulder_hours)
        if np.any(shoulder_mask):
            results[TimePeriod.SHOULDER.value] = self._calculate_metrics(
                flat_preds[shoulder_mask], flat_targets[shoulder_mask],
                flat_quant[shoulder_mask] if flat_quant is not None else None
            )

        return results

    def _evaluate_by_season(
        self,
        predictions: np.ndarray,
        targets: np.ndarray,
        timestamps: pd.DatetimeIndex,
        quantile_predictions: Optional[np.ndarray] = None,
    ) -> Dict[str, Dict[str, MetricResult]]:
        """Evaluate metrics by Indian season.

        Args:
            predictions: Point predictions (batch, horizon)
            targets: True values (batch, horizon)
            timestamps: Timestamps
            quantile_predictions: Quantile predictions

        Returns:
            Dictionary mapping season to metrics
        """
        results = {}

        # Flatten arrays
        flat_preds = predictions.flatten()
        flat_targets = targets.flatten()

        if len(timestamps) != len(flat_preds):
            timestamps = self._expand_timestamps(timestamps, predictions.shape)

        flat_ts = pd.DatetimeIndex(timestamps.flatten())
        months = flat_ts.month

        if quantile_predictions is not None:
            flat_quant = quantile_predictions.reshape(-1, len(self.quantiles))
        else:
            flat_quant = None

        # Summer (March-June)
        summer_mask = np.isin(months, self.summer_months)
        if np.any(summer_mask):
            results[Season.SUMMER.value] = self._calculate_metrics(
                flat_preds[summer_mask], flat_targets[summer_mask],
                flat_quant[summer_mask] if flat_quant is not None else None
            )

        # Monsoon (July-September)
        monsoon_mask = np.isin(months, self.monsoon_months)
        if np.any(monsoon_mask):
            results[Season.MONSOON.value] = self._calculate_metrics(
                flat_preds[monsoon_mask], flat_targets[monsoon_mask],
                flat_quant[monsoon_mask] if flat_quant is not None else None
            )

        # Winter (October-February)
        winter_mask = np.isin(months, self.winter_months)
        if np.any(winter_mask):
            results[Season.WINTER.value] = self._calculate_metrics(
                flat_preds[winter_mask], flat_targets[winter_mask],
                flat_quant[winter_mask] if flat_quant is not None else None
            )

        return results

    def _evaluate_by_day_type(
        self,
        predictions: np.ndarray,
        targets: np.ndarray,
        timestamps: pd.DatetimeIndex,
        quantile_predictions: Optional[np.ndarray] = None,
    ) -> Dict[str, Dict[str, MetricResult]]:
        """Evaluate metrics by day type (weekday, weekend, holiday).

        Args:
            predictions: Point predictions (batch, horizon)
            targets: True values (batch, horizon)
            timestamps: Timestamps
            quantile_predictions: Quantile predictions

        Returns:
            Dictionary mapping day type to metrics
        """
        results = {}

        # Flatten arrays
        flat_preds = predictions.flatten()
        flat_targets = targets.flatten()

        if len(timestamps) != len(flat_preds):
            timestamps = self._expand_timestamps(timestamps, predictions.shape)

        flat_ts = pd.DatetimeIndex(timestamps.flatten())

        if quantile_predictions is not None:
            flat_quant = quantile_predictions.reshape(-1, len(self.quantiles))
        else:
            flat_quant = None

        # Create masks
        is_weekend = np.isin(flat_ts.dayofweek, [5, 6])  # Saturday=5, Sunday=6
        is_holiday = np.array([ts in self.holidays for ts in flat_ts.normalize()])

        # Holidays
        if np.any(is_holiday):
            results[DayType.HOLIDAY.value] = self._calculate_metrics(
                flat_preds[is_holiday], flat_targets[is_holiday],
                flat_quant[is_holiday] if flat_quant is not None else None
            )

        # Weekends (excluding holidays)
        weekend_mask = is_weekend & ~is_holiday
        if np.any(weekend_mask):
            results[DayType.WEEKEND.value] = self._calculate_metrics(
                flat_preds[weekend_mask], flat_targets[weekend_mask],
                flat_quant[weekend_mask] if flat_quant is not None else None
            )

        # Weekdays (excluding holidays)
        weekday_mask = ~is_weekend & ~is_holiday
        if np.any(weekday_mask):
            results[DayType.WEEKDAY.value] = self._calculate_metrics(
                flat_preds[weekday_mask], flat_targets[weekday_mask],
                flat_quant[weekday_mask] if flat_quant is not None else None
            )

        return results

    def _expand_timestamps(
        self,
        timestamps: pd.DatetimeIndex,
        shape: Tuple[int, int],
    ) -> np.ndarray:
        """Expand timestamps from (batch,) to (batch, horizon).

        Assumes hourly frequency.

        Args:
            timestamps: Start timestamps for each batch
            shape: (batch_size, horizon)

        Returns:
            Expanded timestamps array
        """
        batch_size, horizon = shape
        expanded = np.empty((batch_size, horizon), dtype='datetime64[ns]')

        for i in range(batch_size):
            start_ts = timestamps[i] if i < len(timestamps) else timestamps[-1]
            for h in range(horizon):
                expanded[i, h] = start_ts + pd.Timedelta(hours=h)

        return expanded

    def compare_models(
        self,
        model_results: Dict[str, EvaluationResults],
    ) -> pd.DataFrame:
        """Compare multiple models' results.

        Args:
            model_results: Dictionary mapping model names to their evaluation results

        Returns:
            DataFrame with comparison across all metrics
        """
        comparison_data = []

        for model_name, results in model_results.items():
            row = {"model": model_name}

            # Overall metrics
            for metric_name, metric_result in results.overall.items():
                row[f"overall_{metric_name}"] = metric_result.mean

            # Horizon metrics (just MAPE for brevity)
            for horizon, metrics in results.by_horizon.items():
                if "mape" in metrics:
                    row[f"mape_{horizon}h"] = metrics["mape"].mean

            comparison_data.append(row)

        df = pd.DataFrame(comparison_data)
        df = df.set_index("model")

        return df

    def to_dataframe(self, results: EvaluationResults) -> Dict[str, pd.DataFrame]:
        """Convert evaluation results to DataFrames.

        Args:
            results: EvaluationResults object

        Returns:
            Dictionary of DataFrames for each evaluation dimension
        """
        dfs = {}

        # Overall metrics
        overall_data = {name: result.mean for name, result in results.overall.items()}
        dfs["overall"] = pd.DataFrame([overall_data])

        # By horizon
        horizon_data = []
        for horizon, metrics in results.by_horizon.items():
            row = {"horizon": horizon}
            row.update({name: result.mean for name, result in metrics.items()})
            horizon_data.append(row)
        if horizon_data:
            dfs["by_horizon"] = pd.DataFrame(horizon_data).set_index("horizon")

        # By time period
        time_data = []
        for period, metrics in results.by_time_period.items():
            row = {"period": period}
            row.update({name: result.mean for name, result in metrics.items()})
            time_data.append(row)
        if time_data:
            dfs["by_time_period"] = pd.DataFrame(time_data).set_index("period")

        # By season
        season_data = []
        for season, metrics in results.by_season.items():
            row = {"season": season}
            row.update({name: result.mean for name, result in metrics.items()})
            season_data.append(row)
        if season_data:
            dfs["by_season"] = pd.DataFrame(season_data).set_index("season")

        # By day type
        day_data = []
        for day_type, metrics in results.by_day_type.items():
            row = {"day_type": day_type}
            row.update({name: result.mean for name, result in metrics.items()})
            day_data.append(row)
        if day_data:
            dfs["by_day_type"] = pd.DataFrame(day_data).set_index("day_type")

        return dfs
