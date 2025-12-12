"""
Result Aggregator - Cross-experiment analysis and aggregation for SHAKTI-CHAIN.

Provides tools for combining results across experiments, computing
aggregate statistics, and generating comparative analyses.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class AggregatedMetric:
    """Aggregated metric across experiments."""
    name: str
    values: list[float]
    mean: float
    std: float
    median: float
    min: float
    max: float
    ci_lower: float
    ci_upper: float
    n: int

    @classmethod
    def from_values(
        cls,
        name: str,
        values: list[float],
        confidence_level: float = 0.95,
    ) -> AggregatedMetric:
        """Create from list of values."""
        values = [v for v in values if v is not None and not np.isnan(v)]

        if not values:
            return cls(
                name=name,
                values=[],
                mean=np.nan,
                std=np.nan,
                median=np.nan,
                min=np.nan,
                max=np.nan,
                ci_lower=np.nan,
                ci_upper=np.nan,
                n=0,
            )

        arr = np.array(values)
        mean = float(np.mean(arr))
        std = float(np.std(arr, ddof=1)) if len(arr) > 1 else 0

        # Confidence interval
        from scipy import stats
        se = std / np.sqrt(len(arr)) if len(arr) > 0 else 0
        t_crit = stats.t.ppf((1 + confidence_level) / 2, df=max(1, len(arr) - 1))
        margin = t_crit * se

        return cls(
            name=name,
            values=values,
            mean=mean,
            std=std,
            median=float(np.median(arr)),
            min=float(np.min(arr)),
            max=float(np.max(arr)),
            ci_lower=mean - margin,
            ci_upper=mean + margin,
            n=len(arr),
        )

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "mean": self.mean,
            "std": self.std,
            "median": self.median,
            "min": self.min,
            "max": self.max,
            "ci_95": [self.ci_lower, self.ci_upper],
            "n": self.n,
        }


@dataclass
class ExperimentComparison:
    """Comparison between two experiments."""
    experiment1_id: str
    experiment2_id: str
    metrics_compared: dict[str, dict]
    statistical_tests: list[dict]
    summary: str

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "experiment1_id": self.experiment1_id,
            "experiment2_id": self.experiment2_id,
            "metrics_compared": self.metrics_compared,
            "statistical_tests": self.statistical_tests,
            "summary": self.summary,
        }


@dataclass
class AggregationResult:
    """Result of aggregating multiple experiments."""
    experiment_ids: list[str]
    aggregated_metrics: dict[str, AggregatedMetric]
    metadata: dict
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "experiment_ids": self.experiment_ids,
            "aggregated_metrics": {
                k: v.to_dict() for k, v in self.aggregated_metrics.items()
            },
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
        }


class ResultAggregator:
    """
    Aggregates and analyzes results across multiple experiments.

    Provides:
    - Cross-experiment metric aggregation
    - Pairwise experiment comparisons
    - Trend analysis across experiment parameters
    - Summary report generation
    """

    def __init__(
        self,
        results_dir: Path | str = "experiments/results",
        confidence_level: float = 0.95,
    ):
        self.results_dir = Path(results_dir)
        self.confidence_level = confidence_level

        # Cached data
        self._experiments_cache: dict[str, dict] = {}

    def load_experiment(self, experiment_id: str) -> Optional[dict]:
        """Load an experiment result."""
        if experiment_id in self._experiments_cache:
            return self._experiments_cache[experiment_id]

        exp_dir = self.results_dir / experiment_id

        if not exp_dir.exists():
            logger.warning(f"Experiment not found: {experiment_id}")
            return None

        result_file = exp_dir / "result.json"
        if not result_file.exists():
            logger.warning(f"Result file not found for: {experiment_id}")
            return None

        with open(result_file, "r") as f:
            result = json.load(f)

        # Load additional metrics if available
        metrics_dir = exp_dir / "metrics"
        if metrics_dir.exists():
            for metric_file in metrics_dir.glob("*.json"):
                metric_name = metric_file.stem.split("_")[0]
                with open(metric_file, "r") as f:
                    if metric_name not in result:
                        result[f"detailed_{metric_name}"] = json.load(f)

        self._experiments_cache[experiment_id] = result
        return result

    def load_experiments(self, experiment_ids: list[str]) -> list[dict]:
        """Load multiple experiments."""
        results = []
        for exp_id in experiment_ids:
            result = self.load_experiment(exp_id)
            if result is not None:
                results.append(result)
        return results

    def list_experiments(
        self,
        scenario: Optional[str] = None,
        status: Optional[str] = None,
    ) -> list[str]:
        """List available experiments with optional filtering."""
        experiments = []

        for exp_dir in self.results_dir.iterdir():
            if not exp_dir.is_dir() or exp_dir.name.startswith("."):
                continue

            result_file = exp_dir / "result.json"
            if not result_file.exists():
                continue

            try:
                with open(result_file, "r") as f:
                    result = json.load(f)

                # Apply filters
                if scenario and result.get("config", {}).get("scenario") != scenario:
                    continue
                if status and result.get("status") != status:
                    continue

                experiments.append(exp_dir.name)
            except Exception as e:
                logger.warning(f"Error loading {exp_dir.name}: {e}")

        return sorted(experiments, reverse=True)

    def aggregate_metrics(
        self,
        experiment_ids: list[str],
        metric_paths: Optional[list[str]] = None,
    ) -> AggregationResult:
        """
        Aggregate metrics across multiple experiments.

        Args:
            experiment_ids: List of experiment IDs to aggregate
            metric_paths: Specific metric paths to aggregate (e.g., ["metrics.efficiency.mean"])

        Returns:
            AggregationResult with aggregated metrics
        """
        results = self.load_experiments(experiment_ids)

        if not results:
            return AggregationResult(
                experiment_ids=experiment_ids,
                aggregated_metrics={},
                metadata={"error": "No results loaded"},
            )

        # Default metric paths if not specified
        if metric_paths is None:
            metric_paths = [
                "metrics.clearing_price.mean",
                "metrics.clearing_quantity.mean",
                "metrics.efficiency.mean",
                "metrics.total_welfare.buyer_surplus_mean",
                "metrics.total_welfare.seller_surplus_mean",
                "metrics.total_welfare.total_surplus_mean",
            ]

        # Extract values for each metric
        aggregated = {}
        for path in metric_paths:
            values = []
            for result in results:
                value = self._extract_nested_value(result, path)
                if value is not None:
                    values.append(value)

            metric_name = path.replace(".", "_")
            aggregated[metric_name] = AggregatedMetric.from_values(
                name=metric_name,
                values=values,
                confidence_level=self.confidence_level,
            )

        # Compute metadata
        scenarios = set()
        run_modes = set()
        total_periods = 0

        for result in results:
            config = result.get("config", {})
            scenarios.add(config.get("scenario", "unknown"))
            run_modes.add(config.get("run_mode", "unknown"))
            total_periods += result.get("completed_periods", 0)

        metadata = {
            "num_experiments": len(results),
            "scenarios": list(scenarios),
            "run_modes": list(run_modes),
            "total_periods": total_periods,
        }

        return AggregationResult(
            experiment_ids=[r.get("experiment_id", "") for r in results],
            aggregated_metrics=aggregated,
            metadata=metadata,
        )

    def _extract_nested_value(self, data: dict, path: str) -> Optional[Any]:
        """Extract a value from nested dictionary using dot notation."""
        keys = path.split(".")
        current = data

        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return None

        return current if not isinstance(current, dict) else None

    def compare_experiments(
        self,
        experiment1_id: str,
        experiment2_id: str,
        metrics: Optional[list[str]] = None,
    ) -> ExperimentComparison:
        """
        Compare two experiments statistically.

        Args:
            experiment1_id: First experiment ID
            experiment2_id: Second experiment ID
            metrics: List of metrics to compare

        Returns:
            ExperimentComparison with statistical tests
        """
        from .statistical_analyzer import StatisticalAnalyzer

        result1 = self.load_experiment(experiment1_id)
        result2 = self.load_experiment(experiment2_id)

        if result1 is None or result2 is None:
            return ExperimentComparison(
                experiment1_id=experiment1_id,
                experiment2_id=experiment2_id,
                metrics_compared={},
                statistical_tests=[],
                summary="One or both experiments not found",
            )

        analyzer = StatisticalAnalyzer()

        # Default metrics to compare
        if metrics is None:
            metrics = ["clearing_price", "efficiency", "total_welfare"]

        metrics_compared = {}
        statistical_tests = []

        for metric in metrics:
            # Extract metric values from both experiments
            values1 = self._extract_period_values(result1, metric)
            values2 = self._extract_period_values(result2, metric)

            if not values1 or not values2:
                continue

            # Compute summary statistics
            metrics_compared[metric] = {
                "experiment1": {
                    "mean": float(np.mean(values1)),
                    "std": float(np.std(values1)),
                    "n": len(values1),
                },
                "experiment2": {
                    "mean": float(np.mean(values2)),
                    "std": float(np.std(values2)),
                    "n": len(values2),
                },
                "difference": float(np.mean(values1) - np.mean(values2)),
                "percent_change": float(
                    (np.mean(values1) - np.mean(values2)) / np.mean(values2) * 100
                ) if np.mean(values2) != 0 else 0,
            }

            # Run statistical test
            test_result = analyzer.two_sample_t_test(
                np.array(values1),
                np.array(values2),
                paired=False,
                equal_var=False,
            )

            statistical_tests.append({
                "metric": metric,
                "test_type": "two_sample_t_test",
                "statistic": test_result.statistic,
                "p_value": test_result.p_value,
                "effect_size": test_result.effect_size,
                "significant": test_result.reject_null,
            })

        # Generate summary
        significant_diffs = [t for t in statistical_tests if t.get("significant")]
        summary_parts = []

        if not metrics_compared:
            summary = "No comparable metrics found"
        else:
            if significant_diffs:
                summary_parts.append(
                    f"Found {len(significant_diffs)} significant difference(s): "
                    f"{', '.join(t['metric'] for t in significant_diffs)}"
                )
            else:
                summary_parts.append("No significant differences found")

            summary = ". ".join(summary_parts)

        return ExperimentComparison(
            experiment1_id=experiment1_id,
            experiment2_id=experiment2_id,
            metrics_compared=metrics_compared,
            statistical_tests=statistical_tests,
            summary=summary,
        )

    def _extract_period_values(
        self,
        result: dict,
        metric: str,
    ) -> list[float]:
        """Extract per-period values for a metric."""
        # Try to find in detailed metrics first
        detailed = result.get(f"detailed_{metric}", [])
        if detailed:
            return [d.get("value", d.get(metric, 0)) for d in detailed]

        # Fall back to summary metrics
        metrics = result.get("metrics", {})

        # Handle nested paths
        if "." in metric:
            value = self._extract_nested_value(metrics, metric)
            if value is not None:
                return [value]
        elif metric in metrics:
            metric_data = metrics[metric]
            if isinstance(metric_data, dict):
                return [metric_data.get("mean", 0)]
            elif isinstance(metric_data, (int, float)):
                return [metric_data]

        return []

    def compare_scenarios(
        self,
        scenario1: str,
        scenario2: str,
        metrics: Optional[list[str]] = None,
    ) -> dict:
        """
        Compare all experiments of two scenarios.

        Args:
            scenario1: First scenario name
            scenario2: Second scenario name
            metrics: Metrics to compare

        Returns:
            Comparison results
        """
        exp1_ids = self.list_experiments(scenario=scenario1, status="completed")
        exp2_ids = self.list_experiments(scenario=scenario2, status="completed")

        if not exp1_ids or not exp2_ids:
            return {
                "error": "Insufficient experiments for comparison",
                "scenario1_count": len(exp1_ids),
                "scenario2_count": len(exp2_ids),
            }

        # Aggregate each scenario
        agg1 = self.aggregate_metrics(exp1_ids, metrics)
        agg2 = self.aggregate_metrics(exp2_ids, metrics)

        # Compare aggregated metrics
        comparisons = {}
        for metric_name in set(agg1.aggregated_metrics.keys()) & set(agg2.aggregated_metrics.keys()):
            m1 = agg1.aggregated_metrics[metric_name]
            m2 = agg2.aggregated_metrics[metric_name]

            comparisons[metric_name] = {
                "scenario1": {
                    "mean": m1.mean,
                    "std": m1.std,
                    "ci_95": [m1.ci_lower, m1.ci_upper],
                    "n": m1.n,
                },
                "scenario2": {
                    "mean": m2.mean,
                    "std": m2.std,
                    "ci_95": [m2.ci_lower, m2.ci_upper],
                    "n": m2.n,
                },
                "difference": m1.mean - m2.mean,
                "ci_overlap": not (m1.ci_upper < m2.ci_lower or m2.ci_upper < m1.ci_lower),
            }

        return {
            "scenario1": scenario1,
            "scenario2": scenario2,
            "num_experiments": {
                "scenario1": len(exp1_ids),
                "scenario2": len(exp2_ids),
            },
            "comparisons": comparisons,
        }

    def compute_parameter_effects(
        self,
        experiment_ids: list[str],
        parameter: str,
        metric: str,
    ) -> dict:
        """
        Analyze how a parameter affects a metric across experiments.

        Args:
            experiment_ids: Experiments to analyze
            parameter: Parameter name (in config)
            metric: Metric to analyze

        Returns:
            Effect analysis results
        """
        results = self.load_experiments(experiment_ids)

        if not results:
            return {"error": "No results loaded"}

        # Extract parameter values and corresponding metrics
        data_points = []
        for result in results:
            config = result.get("config", {})
            param_value = config.get(parameter) or config.get("custom_params", {}).get(parameter)

            if param_value is None:
                continue

            metric_values = self._extract_period_values(result, metric)
            if not metric_values:
                continue

            data_points.append({
                "parameter": param_value,
                "metric_mean": np.mean(metric_values),
                "metric_std": np.std(metric_values),
                "n": len(metric_values),
            })

        if not data_points:
            return {"error": "No data points extracted"}

        # Group by parameter value
        grouped = {}
        for dp in data_points:
            param = dp["parameter"]
            if param not in grouped:
                grouped[param] = []
            grouped[param].append(dp["metric_mean"])

        # Compute statistics for each parameter value
        param_effects = {}
        for param, values in grouped.items():
            param_effects[str(param)] = {
                "mean": float(np.mean(values)),
                "std": float(np.std(values)),
                "n": len(values),
            }

        # Compute correlation if parameter is numeric
        try:
            params = [float(dp["parameter"]) for dp in data_points]
            metrics = [dp["metric_mean"] for dp in data_points]
            from scipy.stats import pearsonr, spearmanr

            pearson_r, pearson_p = pearsonr(params, metrics)
            spearman_r, spearman_p = spearmanr(params, metrics)

            correlation = {
                "pearson_r": float(pearson_r),
                "pearson_p": float(pearson_p),
                "spearman_r": float(spearman_r),
                "spearman_p": float(spearman_p),
            }
        except (ValueError, TypeError):
            correlation = None

        return {
            "parameter": parameter,
            "metric": metric,
            "num_experiments": len(results),
            "num_data_points": len(data_points),
            "parameter_effects": param_effects,
            "correlation": correlation,
        }

    def generate_summary_report(
        self,
        experiment_ids: list[str],
        output_path: Optional[Path] = None,
    ) -> dict:
        """
        Generate a comprehensive summary report.

        Args:
            experiment_ids: Experiments to summarize
            output_path: Optional path to save the report

        Returns:
            Summary report dictionary
        """
        results = self.load_experiments(experiment_ids)

        if not results:
            return {"error": "No results loaded"}

        # Aggregate all metrics
        aggregation = self.aggregate_metrics(experiment_ids)

        # Compute success rates
        completed = sum(1 for r in results if r.get("status") == "completed")
        failed = sum(1 for r in results if r.get("status") == "failed")

        # Collect scenarios and configurations
        scenarios = {}
        for result in results:
            scenario = result.get("config", {}).get("scenario", "unknown")
            if scenario not in scenarios:
                scenarios[scenario] = 0
            scenarios[scenario] += 1

        # Generate report
        report = {
            "generated_at": datetime.now().isoformat(),
            "summary": {
                "total_experiments": len(results),
                "completed": completed,
                "failed": failed,
                "success_rate": completed / len(results) if results else 0,
            },
            "scenarios": scenarios,
            "aggregated_metrics": aggregation.to_dict(),
            "experiments": [
                {
                    "id": r.get("experiment_id"),
                    "status": r.get("status"),
                    "scenario": r.get("config", {}).get("scenario"),
                    "completed_periods": r.get("completed_periods", 0),
                }
                for r in results
            ],
        }

        # Save if path provided
        if output_path:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w") as f:
                json.dump(report, f, indent=2)
            logger.info(f"Summary report saved to {output_path}")

        return report

    def load_raw_data(
        self,
        experiment_id: str,
        data_type: str,
    ) -> Optional[pd.DataFrame]:
        """
        Load raw data (trades, bids, etc.) for an experiment.

        Args:
            experiment_id: Experiment ID
            data_type: Type of data ("trades", "bids", "market_state", "agent_states")

        Returns:
            DataFrame with the raw data
        """
        exp_dir = self.results_dir / experiment_id / "raw_data"

        if not exp_dir.exists():
            return None

        # Find matching parquet files
        files = list(exp_dir.glob(f"{data_type}*.parquet"))

        if not files:
            return None

        # Load and concatenate all files
        dfs = []
        for file in files:
            try:
                df = pd.read_parquet(file)
                dfs.append(df)
            except Exception as e:
                logger.warning(f"Error loading {file}: {e}")

        if not dfs:
            return None

        return pd.concat(dfs, ignore_index=True)

    def compute_trade_analysis(
        self,
        experiment_id: str,
    ) -> dict:
        """
        Detailed trade analysis for an experiment.

        Args:
            experiment_id: Experiment ID

        Returns:
            Trade analysis results
        """
        trades_df = self.load_raw_data(experiment_id, "trades")

        if trades_df is None or trades_df.empty:
            return {"error": "No trade data available"}

        analysis = {
            "total_trades": len(trades_df),
            "total_volume": float(trades_df["quantity"].sum()),
            "total_value": float((trades_df["price"] * trades_df["quantity"]).sum()),
            "price_statistics": {
                "mean": float(trades_df["price"].mean()),
                "std": float(trades_df["price"].std()),
                "min": float(trades_df["price"].min()),
                "max": float(trades_df["price"].max()),
                "median": float(trades_df["price"].median()),
            },
            "quantity_statistics": {
                "mean": float(trades_df["quantity"].mean()),
                "std": float(trades_df["quantity"].std()),
                "min": float(trades_df["quantity"].min()),
                "max": float(trades_df["quantity"].max()),
            },
        }

        # Per-agent-type analysis if available
        if "buyer_type" in trades_df.columns and "seller_type" in trades_df.columns:
            buyer_types = trades_df.groupby("buyer_type").agg({
                "quantity": ["sum", "count"],
                "buyer_surplus": "sum",
            }).round(2)

            seller_types = trades_df.groupby("seller_type").agg({
                "quantity": ["sum", "count"],
                "seller_surplus": "sum",
            }).round(2)

            analysis["by_buyer_type"] = buyer_types.to_dict()
            analysis["by_seller_type"] = seller_types.to_dict()

        # Per-period analysis
        if "period" in trades_df.columns:
            period_stats = trades_df.groupby("period").agg({
                "price": "mean",
                "quantity": "sum",
                "trade_id": "count",
            }).rename(columns={"trade_id": "num_trades"})

            analysis["by_period"] = {
                "price_trend": period_stats["price"].tolist(),
                "volume_trend": period_stats["quantity"].tolist(),
                "trades_per_period": period_stats["num_trades"].tolist(),
            }

        return analysis

    def export_to_csv(
        self,
        experiment_ids: list[str],
        output_dir: Path | str,
    ) -> dict:
        """
        Export experiment results to CSV files.

        Args:
            experiment_ids: Experiments to export
            output_dir: Output directory

        Returns:
            Export status
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        exported = []

        for exp_id in experiment_ids:
            result = self.load_experiment(exp_id)
            if result is None:
                continue

            # Export summary metrics
            metrics = result.get("metrics", {})
            metrics_flat = self._flatten_dict(metrics)

            df = pd.DataFrame([metrics_flat])
            df["experiment_id"] = exp_id
            df.to_csv(output_dir / f"{exp_id}_summary.csv", index=False)

            # Export raw data if available
            for data_type in ["trades", "bids"]:
                raw_df = self.load_raw_data(exp_id, data_type)
                if raw_df is not None:
                    raw_df.to_csv(output_dir / f"{exp_id}_{data_type}.csv", index=False)

            exported.append(exp_id)

        return {
            "exported": exported,
            "output_dir": str(output_dir),
        }

    def _flatten_dict(
        self,
        d: dict,
        parent_key: str = "",
        sep: str = "_",
    ) -> dict:
        """Flatten a nested dictionary."""
        items = []
        for k, v in d.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            if isinstance(v, dict):
                items.extend(self._flatten_dict(v, new_key, sep).items())
            else:
                items.append((new_key, v))
        return dict(items)
