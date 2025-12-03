#!/usr/bin/env python
"""
Evaluation script for SHAKTI-CHAIN forecasting models.

Evaluates TFT model against baselines with cross-validation and generates
comprehensive evaluation report.

Usage:
    python scripts/evaluate_models.py
    python scripts/evaluate_models.py --model-path checkpoints/tft/best.ckpt
    python scripts/evaluate_models.py --n-cv-folds 5 --output-dir evaluation_results
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import argparse
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any

import numpy as np
import pandas as pd
import torch
import yaml

from src.evaluation.metrics import ForecastEvaluator, EvaluationResults
from src.evaluation.baselines import (
    get_all_baselines,
    get_simple_baselines,
    NaiveModel,
    SeasonalNaiveModel,
    ARIMAModel,
    XGBoostModel,
    ProphetModel,
)
from src.evaluation.cross_validation import (
    TimeSeriesSplit,
    cross_validate_baselines,
    format_cv_comparison,
    CVResults,
)
from src.evaluation.visualization import (
    plot_model_comparison,
    plot_cv_results,
    plot_metrics_by_dimension,
    create_evaluation_report_plots,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def load_data(data_path: str) -> pd.DataFrame:
    """Load and prepare data for evaluation.

    Args:
        data_path: Path to processed data parquet file

    Returns:
        DataFrame with time series data
    """
    logger.info(f"Loading data from {data_path}")
    data = pd.read_parquet(data_path)

    # Ensure timestamp column
    if "timestamp" not in data.columns:
        raise ValueError("Data must have a 'timestamp' column")

    data["timestamp"] = pd.to_datetime(data["timestamp"])
    data = data.sort_values("timestamp").reset_index(drop=True)

    logger.info(f"Loaded {len(data):,} rows from {data['timestamp'].min()} to {data['timestamp'].max()}")

    return data


def evaluate_tft_model(
    model_path: str,
    data: pd.DataFrame,
    evaluator: ForecastEvaluator,
    config_path: str = "configs/training/tft.yaml",
) -> EvaluationResults:
    """Evaluate TFT model on test data.

    Args:
        model_path: Path to model checkpoint
        data: Full DataFrame with data
        evaluator: ForecastEvaluator instance
        config_path: Path to model config

    Returns:
        EvaluationResults
    """
    logger.info(f"Loading TFT model from {model_path}")

    try:
        from src.training.tft_lightning_module import TFTLightningModule
        from src.data.datamodule import V2GDataModule

        # Load config
        with open(config_path) as f:
            config = yaml.safe_load(f)

        # Create data module
        data_module = V2GDataModule(
            data_path=config["data"]["data_path"],
            target_columns=config["features"]["target_columns"],
            known_future_features=config["features"]["known_future_features"],
            observed_features=config["features"]["observed_features"],
            static_features=config["features"].get("static_features"),
            encoder_length=config["data"]["encoder_length"],
            decoder_length=config["data"]["decoder_length"],
            batch_size=config["training"]["batch_size"],
            num_workers=0,  # For simplicity
            test_start=config["data"]["test_start"],
            test_end=config["data"]["test_end"],
        )
        data_module.setup("test")

        # Load model
        model = TFTLightningModule.load_from_checkpoint(model_path)
        model.eval()

        # Generate predictions
        all_predictions = []
        all_targets = []
        all_timestamps = []

        test_loader = data_module.test_dataloader()

        with torch.no_grad():
            for batch in test_loader:
                predictions, _ = model(
                    static_covariates=batch.get("static_covariates"),
                    historical_observed=batch["historical_observed"],
                    historical_known=batch["historical_known"],
                    future_known=batch["future_known"],
                )
                all_predictions.append(predictions.numpy())
                all_targets.append(batch["target"].numpy())

        # Concatenate
        predictions = np.concatenate(all_predictions, axis=0)
        targets = np.concatenate(all_targets, axis=0)

        # Evaluate
        results = evaluator.evaluate(
            predictions=predictions,
            targets=targets,
        )

        return results

    except Exception as e:
        logger.error(f"Failed to evaluate TFT model: {e}")
        raise


def evaluate_baselines(
    data: pd.DataFrame,
    evaluator: ForecastEvaluator,
    test_start: str,
    test_end: str,
    target_col: str = "load_mw",
    horizon: int = 48,
) -> Dict[str, EvaluationResults]:
    """Evaluate baseline models on test data.

    Args:
        data: Full DataFrame with data
        evaluator: ForecastEvaluator instance
        test_start: Test period start date
        test_end: Test period end date
        target_col: Target column name
        horizon: Forecast horizon

    Returns:
        Dictionary mapping model names to EvaluationResults
    """
    logger.info("Evaluating baseline models...")

    # Split data
    test_mask = (data["timestamp"] >= test_start) & (data["timestamp"] <= test_end)
    train_data = data[~test_mask]
    test_data = data[test_mask]

    logger.info(f"Train: {len(train_data):,} samples, Test: {len(test_data):,} samples")

    # Prepare time series
    y_train = train_data.set_index("timestamp")[target_col]
    y_test = test_data.set_index("timestamp")[target_col]

    results = {}

    # Get baselines
    baselines = {
        "Naive (Yesterday)": NaiveModel(),
        "Seasonal Naive (Last Week)": SeasonalNaiveModel(),
    }

    # Try to add more complex baselines
    try:
        baselines["XGBoost"] = XGBoostModel()
    except ImportError:
        logger.warning("XGBoost not available")

    try:
        baselines["ARIMA"] = ARIMAModel()
    except ImportError:
        logger.warning("ARIMA not available (statsmodels required)")

    try:
        baselines["Prophet"] = ProphetModel()
    except ImportError:
        logger.warning("Prophet not available")

    # Evaluate each baseline
    for name, model in baselines.items():
        logger.info(f"  Evaluating {name}...")

        try:
            # Fit on training data
            model.fit(y_train)

            # Generate predictions for test period
            # We'll use rolling predictions
            predictions = []
            targets = []
            timestamps = []

            test_indices = list(range(0, len(test_data) - horizon, horizon))

            for idx in test_indices[:100]:  # Limit for speed
                # Get historical data up to this point
                current_ts = y_test.index[idx]
                history_end_idx = train_data[train_data["timestamp"] < current_ts].index.max()

                if pd.isna(history_end_idx):
                    continue

                # Fit on all data up to this point
                y_history = data.loc[:history_end_idx].set_index("timestamp")[target_col]
                model.fit(y_history)

                # Predict
                preds = model.predict(horizon=horizon)
                actuals = y_test.iloc[idx:idx + horizon].values

                if len(actuals) == horizon:
                    predictions.append(preds)
                    targets.append(actuals)
                    timestamps.extend(y_test.index[idx:idx + horizon])

            if predictions:
                predictions = np.array(predictions)
                targets = np.array(targets)
                timestamps = pd.DatetimeIndex(timestamps[:len(predictions.flatten())])

                # Evaluate
                eval_results = evaluator.evaluate(
                    predictions=predictions,
                    targets=targets,
                    timestamps=timestamps,
                )
                results[name] = eval_results

                logger.info(f"    MAPE: {eval_results.overall.get('mape', {}).mean:.2f}%")

        except Exception as e:
            logger.error(f"    Failed: {e}")
            continue

    return results


def run_cross_validation(
    data: pd.DataFrame,
    evaluator: ForecastEvaluator,
    n_splits: int = 5,
    train_months: int = 12,
    val_months: int = 1,
    target_col: str = "load_mw",
) -> Dict[str, CVResults]:
    """Run cross-validation on baseline models.

    Args:
        data: Full DataFrame with data
        evaluator: ForecastEvaluator instance
        n_splits: Number of CV folds
        train_months: Training months per fold
        val_months: Validation months per fold
        target_col: Target column name

    Returns:
        Dictionary mapping model names to CVResults
    """
    logger.info(f"Running {n_splits}-fold cross-validation...")

    baselines = get_simple_baselines()

    # Try to add XGBoost
    try:
        baselines["xgboost"] = XGBoostModel()
    except ImportError:
        pass

    cv_results = cross_validate_baselines(
        data=data,
        baselines=baselines,
        evaluator=evaluator,
        n_splits=n_splits,
        train_months=train_months,
        val_months=val_months,
        target_col=target_col,
    )

    return cv_results


def generate_markdown_report(
    tft_results: Optional[EvaluationResults],
    baseline_results: Dict[str, EvaluationResults],
    cv_results: Dict[str, CVResults],
    output_path: str,
    plots_dir: str,
) -> str:
    """Generate markdown evaluation report.

    Args:
        tft_results: TFT model evaluation results
        baseline_results: Baseline models evaluation results
        cv_results: Cross-validation results
        output_path: Path to save the report
        plots_dir: Directory containing plots

    Returns:
        Path to generated report
    """
    logger.info("Generating evaluation report...")

    report_lines = []

    # Header
    report_lines.extend([
        "# SHAKTI-CHAIN Forecast Evaluation Report",
        "",
        f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "---",
        "",
    ])

    # Executive Summary
    report_lines.extend([
        "## Executive Summary",
        "",
    ])

    # Find best model
    all_results = {}
    if tft_results:
        all_results["TFT"] = tft_results
    all_results.update(baseline_results)

    if all_results:
        best_model = min(all_results.items(), key=lambda x: x[1].overall.get("mape", {}).mean or float("inf"))
        report_lines.extend([
            f"- **Best Model:** {best_model[0]}",
            f"- **Best MAPE:** {best_model[1].overall.get('mape', {}).mean:.2f}%",
            f"- **Best RMSE:** {best_model[1].overall.get('rmse', {}).mean:.2f}",
            f"- **Coverage (90% PI):** {best_model[1].overall.get('coverage_90', {}).mean * 100:.1f}%"
            if best_model[1].overall.get('coverage_90') else "N/A",
            "",
        ])

    # Target Metrics
    report_lines.extend([
        "### Target Metrics",
        "",
        "| Metric | Target | Achieved |",
        "|--------|--------|----------|",
    ])

    if tft_results:
        tft_mape = tft_results.overall.get("mape", {}).mean
        tft_coverage = tft_results.overall.get("coverage_90", {}).mean
        report_lines.extend([
            f"| MAPE | < 5% | {tft_mape:.2f}% {'✅' if tft_mape < 5 else '❌'} |",
            f"| Coverage (90% PI) | > 88% | {tft_coverage * 100:.1f}% {'✅' if tft_coverage > 0.88 else '❌'} |"
            if tft_coverage else "| Coverage (90% PI) | > 88% | N/A |",
        ])
    report_lines.append("")

    # Overall Metrics Comparison
    report_lines.extend([
        "---",
        "",
        "## Overall Metrics Comparison",
        "",
        "| Model | MAE | MAPE (%) | RMSE | sMAPE (%) | Coverage |",
        "|-------|-----|----------|------|-----------|----------|",
    ])

    for name, results in all_results.items():
        mae = results.overall.get("mae", {}).mean
        mape = results.overall.get("mape", {}).mean
        rmse = results.overall.get("rmse", {}).mean
        smape = results.overall.get("smape", {}).mean
        coverage = results.overall.get("coverage_90", {}).mean

        report_lines.append(
            f"| {name} | {mae:.2f} | {mape:.2f} | {rmse:.2f} | {smape:.2f} | "
            f"{coverage * 100:.1f}% |" if coverage else f"| {name} | {mae:.2f} | {mape:.2f} | {rmse:.2f} | {smape:.2f} | N/A |"
        )
    report_lines.append("")

    # Metrics by Forecast Horizon
    report_lines.extend([
        "---",
        "",
        "## Metrics by Forecast Horizon",
        "",
    ])

    for name, results in all_results.items():
        if results.by_horizon:
            report_lines.extend([
                f"### {name}",
                "",
                "| Horizon | MAE | MAPE (%) | RMSE |",
                "|---------|-----|----------|------|",
            ])

            for horizon in sorted(results.by_horizon.keys()):
                metrics = results.by_horizon[horizon]
                mae = metrics.get("mae", {}).mean
                mape = metrics.get("mape", {}).mean
                rmse = metrics.get("rmse", {}).mean
                report_lines.append(f"| {horizon}h | {mae:.2f} | {mape:.2f} | {rmse:.2f} |")

            report_lines.append("")

    # Metrics by Time Period
    report_lines.extend([
        "---",
        "",
        "## Metrics by Time Period",
        "",
        "Time periods for Indian power grid:",
        "- **Peak:** 18:00-22:00 (evening peak demand)",
        "- **Off-Peak:** 22:00-06:00 (night, low demand)",
        "- **Shoulder:** 06:00-18:00 (daytime)",
        "",
    ])

    for name, results in all_results.items():
        if results.by_time_period:
            report_lines.extend([
                f"### {name}",
                "",
                "| Period | MAE | MAPE (%) | RMSE |",
                "|--------|-----|----------|------|",
            ])

            for period, metrics in results.by_time_period.items():
                mae = metrics.get("mae", {}).mean
                mape = metrics.get("mape", {}).mean
                rmse = metrics.get("rmse", {}).mean
                report_lines.append(f"| {period} | {mae:.2f} | {mape:.2f} | {rmse:.2f} |")

            report_lines.append("")

    # Metrics by Season
    report_lines.extend([
        "---",
        "",
        "## Metrics by Season",
        "",
        "Indian seasons:",
        "- **Summer:** March-June (extreme demand due to AC)",
        "- **Monsoon:** July-September (variable demand)",
        "- **Winter:** October-February (moderate demand)",
        "",
    ])

    for name, results in all_results.items():
        if results.by_season:
            report_lines.extend([
                f"### {name}",
                "",
                "| Season | MAE | MAPE (%) | RMSE |",
                "|--------|-----|----------|------|",
            ])

            for season, metrics in results.by_season.items():
                mae = metrics.get("mae", {}).mean
                mape = metrics.get("mape", {}).mean
                rmse = metrics.get("rmse", {}).mean
                report_lines.append(f"| {season} | {mae:.2f} | {mape:.2f} | {rmse:.2f} |")

            report_lines.append("")

    # Metrics by Day Type
    report_lines.extend([
        "---",
        "",
        "## Metrics by Day Type",
        "",
    ])

    for name, results in all_results.items():
        if results.by_day_type:
            report_lines.extend([
                f"### {name}",
                "",
                "| Day Type | MAE | MAPE (%) | RMSE |",
                "|----------|-----|----------|------|",
            ])

            for day_type, metrics in results.by_day_type.items():
                mae = metrics.get("mae", {}).mean
                mape = metrics.get("mape", {}).mean
                rmse = metrics.get("rmse", {}).mean
                report_lines.append(f"| {day_type} | {mae:.2f} | {mape:.2f} | {rmse:.2f} |")

            report_lines.append("")

    # Cross-Validation Results
    if cv_results:
        report_lines.extend([
            "---",
            "",
            "## Cross-Validation Results",
            "",
            f"**Configuration:** {len(list(cv_results.values())[0].folds)}-fold time series CV",
            "",
            "| Model | MAPE (%) | MAE | RMSE |",
            "|-------|----------|-----|------|",
        ])

        for name, results in cv_results.items():
            mape_mean = results.mean_metrics.get("mape", np.nan)
            mape_std = results.std_metrics.get("mape", np.nan)
            mae_mean = results.mean_metrics.get("mae", np.nan)
            mae_std = results.std_metrics.get("mae", np.nan)
            rmse_mean = results.mean_metrics.get("rmse", np.nan)
            rmse_std = results.std_metrics.get("rmse", np.nan)

            report_lines.append(
                f"| {name} | {mape_mean:.2f} ± {mape_std:.2f} | "
                f"{mae_mean:.2f} ± {mae_std:.2f} | {rmse_mean:.2f} ± {rmse_std:.2f} |"
            )

        report_lines.append("")

    # Plots
    if plots_dir and Path(plots_dir).exists():
        report_lines.extend([
            "---",
            "",
            "## Visualizations",
            "",
        ])

        for plot_file in Path(plots_dir).glob("*.png"):
            report_lines.append(f"![{plot_file.stem}]({plot_file.name})")
            report_lines.append("")

    # Recommendations
    report_lines.extend([
        "---",
        "",
        "## Recommendations",
        "",
    ])

    if tft_results:
        tft_mape = tft_results.overall.get("mape", {}).mean
        if tft_mape < 5:
            report_lines.extend([
                "1. ✅ **MAPE target achieved** - Model meets the <5% MAPE requirement",
                "",
            ])
        else:
            report_lines.extend([
                f"1. ❌ **MAPE target not met** ({tft_mape:.2f}% vs <5%) - Consider:",
                "   - Hyperparameter tuning (hidden_size, attention_heads)",
                "   - Adding more features (additional weather variables, grid frequency)",
                "   - Increasing training data or encoder length",
                "",
            ])

        # Check coverage
        coverage = tft_results.overall.get("coverage_90", {}).mean
        if coverage and coverage > 0.88:
            report_lines.extend([
                "2. ✅ **Coverage target achieved** - Prediction intervals are well-calibrated",
                "",
            ])
        elif coverage:
            report_lines.extend([
                f"2. ❌ **Coverage target not met** ({coverage * 100:.1f}% vs >88%) - Consider:",
                "   - Adjusting quantile predictions",
                "   - Using NormalizedQuantileLoss",
                "",
            ])

        # Check peak hour performance
        if tft_results.by_time_period:
            peak_mape = tft_results.by_time_period.get("peak", {}).get("mape", {}).mean
            if peak_mape and peak_mape > tft_mape * 1.5:
                report_lines.extend([
                    f"3. ⚠️ **Peak hour accuracy** ({peak_mape:.2f}%) is significantly worse than overall",
                    "   - Consider adding peak hour indicator features",
                    "   - Weight peak hours more heavily in loss function",
                    "",
                ])

    report_lines.extend([
        "---",
        "",
        "*Report generated by SHAKTI-CHAIN Evaluation Framework*",
    ])

    # Write report
    report_content = "\n".join(report_lines)

    with open(output_path, "w") as f:
        f.write(report_content)

    logger.info(f"Report saved to {output_path}")

    return output_path


def main():
    """Main evaluation function."""
    parser = argparse.ArgumentParser(description="Evaluate SHAKTI-CHAIN forecasting models")
    parser.add_argument("--data-path", type=str, default="data/processed/processed_data.parquet",
                        help="Path to processed data")
    parser.add_argument("--model-path", type=str, default=None,
                        help="Path to TFT model checkpoint")
    parser.add_argument("--config-path", type=str, default="configs/training/tft.yaml",
                        help="Path to model config")
    parser.add_argument("--test-start", type=str, default="2024-07-01",
                        help="Test period start date")
    parser.add_argument("--test-end", type=str, default="2024-12-31",
                        help="Test period end date")
    parser.add_argument("--n-cv-folds", type=int, default=5,
                        help="Number of cross-validation folds")
    parser.add_argument("--output-dir", type=str, default="evaluation_results",
                        help="Output directory for results")
    parser.add_argument("--skip-cv", action="store_true",
                        help="Skip cross-validation (faster)")
    parser.add_argument("--skip-tft", action="store_true",
                        help="Skip TFT evaluation")

    args = parser.parse_args()

    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    plots_dir = output_dir / "plots"
    plots_dir.mkdir(exist_ok=True)

    # Load data
    data = load_data(args.data_path)

    # Create evaluator
    evaluator = ForecastEvaluator(
        quantiles=[0.1, 0.5, 0.9],
        horizons=[1, 6, 24, 48],
    )

    # Evaluate TFT model
    tft_results = None
    if not args.skip_tft and args.model_path and Path(args.model_path).exists():
        try:
            tft_results = evaluate_tft_model(
                model_path=args.model_path,
                data=data,
                evaluator=evaluator,
                config_path=args.config_path,
            )
            logger.info(f"TFT MAPE: {tft_results.overall.get('mape', {}).mean:.2f}%")
        except Exception as e:
            logger.error(f"TFT evaluation failed: {e}")

    # Evaluate baselines
    baseline_results = evaluate_baselines(
        data=data,
        evaluator=evaluator,
        test_start=args.test_start,
        test_end=args.test_end,
    )

    # Run cross-validation
    cv_results = {}
    if not args.skip_cv:
        cv_results = run_cross_validation(
            data=data,
            evaluator=evaluator,
            n_splits=args.n_cv_folds,
        )

    # Generate plots
    try:
        all_results = {}
        if tft_results:
            all_results["TFT"] = tft_results
        all_results.update(baseline_results)

        if all_results:
            # Model comparison plot
            fig = plot_model_comparison(
                all_results,
                metrics=["mape", "mae", "rmse"],
                title="Model Comparison",
                save_path=str(plots_dir / "model_comparison.png"),
            )
            if fig:
                import matplotlib.pyplot as plt
                plt.close(fig)

        if cv_results:
            # CV results plot
            fig = plot_cv_results(
                cv_results,
                metric="mape",
                title="Cross-Validation Results (MAPE)",
                save_path=str(plots_dir / "cv_results.png"),
            )
            if fig:
                import matplotlib.pyplot as plt
                plt.close(fig)

    except Exception as e:
        logger.warning(f"Failed to generate plots: {e}")

    # Generate report
    report_path = generate_markdown_report(
        tft_results=tft_results,
        baseline_results=baseline_results,
        cv_results=cv_results,
        output_path=str(output_dir / "evaluation_report.md"),
        plots_dir=str(plots_dir),
    )

    logger.info(f"\nEvaluation complete! Results saved to {output_dir}")
    logger.info(f"Report: {report_path}")


if __name__ == "__main__":
    main()
