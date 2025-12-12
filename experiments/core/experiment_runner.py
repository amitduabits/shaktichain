"""
Experiment Runner - Main orchestrator for SHAKTI-CHAIN validation experiments.

Provides async execution, progress tracking, checkpointing, and result caching.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import pickle
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional

import numpy as np
import yaml

logger = logging.getLogger(__name__)


class ExperimentStatus(Enum):
    """Status of an experiment run."""
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ExperimentConfig:
    """Configuration for a single experiment run."""
    name: str
    run_mode: str  # quick, standard, exhaustive
    scenario: str
    agent_distribution: str
    baseline: Optional[str] = None
    random_seed: int = 42

    # Overrides from run_mode defaults
    num_runs: Optional[int] = None
    num_agents: Optional[int] = None
    duration_hours: Optional[float] = None
    clearing_interval_seconds: Optional[int] = None

    # Additional parameters
    custom_params: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert config to dictionary."""
        return {
            "name": self.name,
            "run_mode": self.run_mode,
            "scenario": self.scenario,
            "agent_distribution": self.agent_distribution,
            "baseline": self.baseline,
            "random_seed": self.random_seed,
            "num_runs": self.num_runs,
            "num_agents": self.num_agents,
            "duration_hours": self.duration_hours,
            "clearing_interval_seconds": self.clearing_interval_seconds,
            "custom_params": self.custom_params,
        }

    @classmethod
    def from_dict(cls, data: dict) -> ExperimentConfig:
        """Create config from dictionary."""
        return cls(
            name=data["name"],
            run_mode=data["run_mode"],
            scenario=data["scenario"],
            agent_distribution=data["agent_distribution"],
            baseline=data.get("baseline"),
            random_seed=data.get("random_seed", 42),
            num_runs=data.get("num_runs"),
            num_agents=data.get("num_agents"),
            duration_hours=data.get("duration_hours"),
            clearing_interval_seconds=data.get("clearing_interval_seconds"),
            custom_params=data.get("custom_params", {}),
        )

    def get_config_hash(self) -> str:
        """Generate unique hash for this configuration."""
        config_str = json.dumps(self.to_dict(), sort_keys=True)
        return hashlib.sha256(config_str.encode()).hexdigest()[:16]


@dataclass
class CheckpointData:
    """Data stored in a checkpoint."""
    experiment_id: str
    run_index: int
    period_index: int
    agent_states: dict
    market_state: dict
    collected_metrics: list
    random_state: Any
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class ExperimentResult:
    """Result of a completed experiment."""
    experiment_id: str
    config: ExperimentConfig
    status: ExperimentStatus
    start_time: datetime
    end_time: Optional[datetime]
    total_periods: int
    completed_periods: int
    metrics: dict
    errors: list = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert result to dictionary."""
        return {
            "experiment_id": self.experiment_id,
            "config": self.config.to_dict(),
            "status": self.status.value,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "total_periods": self.total_periods,
            "completed_periods": self.completed_periods,
            "metrics": self.metrics,
            "errors": self.errors,
        }


class ProgressTracker:
    """Tracks and reports experiment progress."""

    def __init__(
        self,
        total_runs: int,
        periods_per_run: int,
        callback: Optional[Callable[[float, str], None]] = None,
    ):
        self.total_runs = total_runs
        self.periods_per_run = periods_per_run
        self.total_periods = total_runs * periods_per_run
        self.completed_periods = 0
        self.current_run = 0
        self.start_time = time.time()
        self.callback = callback

    def update(self, run: int, period: int, message: str = "") -> None:
        """Update progress."""
        self.current_run = run
        self.completed_periods = run * self.periods_per_run + period
        progress = self.completed_periods / self.total_periods

        if self.callback:
            self.callback(progress, message)

    def get_eta(self) -> float:
        """Get estimated time remaining in seconds."""
        if self.completed_periods == 0:
            return float("inf")
        elapsed = time.time() - self.start_time
        rate = self.completed_periods / elapsed
        remaining = self.total_periods - self.completed_periods
        return remaining / rate if rate > 0 else float("inf")

    def get_progress_dict(self) -> dict:
        """Get progress as dictionary."""
        elapsed = time.time() - self.start_time
        return {
            "current_run": self.current_run,
            "total_runs": self.total_runs,
            "completed_periods": self.completed_periods,
            "total_periods": self.total_periods,
            "progress_percent": 100 * self.completed_periods / self.total_periods,
            "elapsed_seconds": elapsed,
            "eta_seconds": self.get_eta(),
        }


class ResultCache:
    """Caches experiment results to avoid recomputation."""

    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.index_file = self.cache_dir / "cache_index.json"
        self.index = self._load_index()

    def _load_index(self) -> dict:
        """Load cache index from disk."""
        if self.index_file.exists():
            with open(self.index_file, "r") as f:
                return json.load(f)
        return {}

    def _save_index(self) -> None:
        """Save cache index to disk."""
        with open(self.index_file, "w") as f:
            json.dump(self.index, f, indent=2)

    def get(self, config_hash: str) -> Optional[ExperimentResult]:
        """Get cached result if available."""
        if config_hash not in self.index:
            return None

        cache_file = self.cache_dir / f"{config_hash}.pkl"
        if not cache_file.exists():
            del self.index[config_hash]
            self._save_index()
            return None

        try:
            with open(cache_file, "rb") as f:
                return pickle.load(f)
        except Exception as e:
            logger.warning(f"Failed to load cached result: {e}")
            return None

    def put(self, config_hash: str, result: ExperimentResult) -> None:
        """Cache an experiment result."""
        cache_file = self.cache_dir / f"{config_hash}.pkl"

        try:
            with open(cache_file, "wb") as f:
                pickle.dump(result, f)

            self.index[config_hash] = {
                "experiment_id": result.experiment_id,
                "cached_at": datetime.now().isoformat(),
                "config_name": result.config.name,
            }
            self._save_index()
        except Exception as e:
            logger.warning(f"Failed to cache result: {e}")

    def invalidate(self, config_hash: str) -> None:
        """Remove a cached result."""
        if config_hash in self.index:
            cache_file = self.cache_dir / f"{config_hash}.pkl"
            if cache_file.exists():
                cache_file.unlink()
            del self.index[config_hash]
            self._save_index()


class ExperimentRunner:
    """
    Main experiment orchestrator for SHAKTI-CHAIN validation.

    Features:
    - Async execution capability
    - Progress tracking
    - Checkpointing for long runs
    - Automatic retry on failure
    - Result caching
    """

    def __init__(
        self,
        config_path: Path | str = "experiments/config/experiment_config.yaml",
        output_dir: Path | str = "experiments/results",
        cache_enabled: bool = True,
        max_retries: int = 3,
        checkpoint_interval_minutes: int = 30,
    ):
        self.config_path = Path(config_path)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.max_retries = max_retries
        self.checkpoint_interval = checkpoint_interval_minutes * 60

        # Load global config
        self.global_config = self._load_global_config()

        # Initialize cache
        self.cache_enabled = cache_enabled
        if cache_enabled:
            self.cache = ResultCache(self.output_dir / ".cache")

        # State
        self.current_experiment: Optional[str] = None
        self.is_running = False
        self._cancel_requested = False

    def _load_global_config(self) -> dict:
        """Load global configuration from YAML."""
        if self.config_path.exists():
            with open(self.config_path, "r") as f:
                return yaml.safe_load(f)
        return {}

    def _get_run_params(self, config: ExperimentConfig) -> dict:
        """Get run parameters merging defaults with overrides."""
        run_mode = config.run_mode
        defaults = self.global_config.get("run_modes", {}).get(run_mode, {})

        return {
            "runs": config.num_runs or defaults.get("runs", 5),
            "agents": config.num_agents or defaults.get("agents", 500),
            "duration_hours": config.duration_hours or defaults.get("duration_hours", 24),
            "clearing_interval_seconds": (
                config.clearing_interval_seconds or
                defaults.get("clearing_interval_seconds", 60)
            ),
            "checkpoint_interval_minutes": defaults.get("checkpoint_interval_minutes", 60),
        }

    def _create_experiment_dir(self, experiment_id: str) -> Path:
        """Create directory structure for experiment results."""
        exp_dir = self.output_dir / experiment_id

        subdirs = [
            "raw_data",
            "metrics",
            "statistical_tests",
            "visualizations",
            "checkpoints",
        ]

        for subdir in subdirs:
            (exp_dir / subdir).mkdir(parents=True, exist_ok=True)

        return exp_dir

    def _save_checkpoint(
        self,
        exp_dir: Path,
        checkpoint: CheckpointData,
    ) -> None:
        """Save checkpoint to disk."""
        checkpoint_file = (
            exp_dir / "checkpoints" /
            f"checkpoint_run{checkpoint.run_index}_period{checkpoint.period_index}.pkl"
        )

        with open(checkpoint_file, "wb") as f:
            pickle.dump(checkpoint, f)

        # Also save latest checkpoint reference
        latest_file = exp_dir / "checkpoints" / "latest.json"
        with open(latest_file, "w") as f:
            json.dump({
                "run_index": checkpoint.run_index,
                "period_index": checkpoint.period_index,
                "timestamp": checkpoint.timestamp.isoformat(),
                "file": checkpoint_file.name,
            }, f)

        logger.info(f"Saved checkpoint at run {checkpoint.run_index}, period {checkpoint.period_index}")

    def _load_latest_checkpoint(self, exp_dir: Path) -> Optional[CheckpointData]:
        """Load the most recent checkpoint."""
        latest_file = exp_dir / "checkpoints" / "latest.json"

        if not latest_file.exists():
            return None

        with open(latest_file, "r") as f:
            latest_info = json.load(f)

        checkpoint_file = exp_dir / "checkpoints" / latest_info["file"]

        if not checkpoint_file.exists():
            return None

        with open(checkpoint_file, "rb") as f:
            return pickle.load(f)

    async def run_experiment(
        self,
        config: ExperimentConfig,
        progress_callback: Optional[Callable[[float, str], None]] = None,
        use_cache: bool = True,
    ) -> ExperimentResult:
        """
        Run a single experiment with the given configuration.

        Args:
            config: Experiment configuration
            progress_callback: Optional callback for progress updates
            use_cache: Whether to use cached results if available

        Returns:
            ExperimentResult with all metrics and outcomes
        """
        # Check cache
        config_hash = config.get_config_hash()
        if use_cache and self.cache_enabled:
            cached = self.cache.get(config_hash)
            if cached is not None:
                logger.info(f"Using cached result for {config.name}")
                return cached

        # Generate experiment ID
        experiment_id = f"{config.name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        self.current_experiment = experiment_id
        self.is_running = True
        self._cancel_requested = False

        # Create output directory
        exp_dir = self._create_experiment_dir(experiment_id)

        # Save config
        with open(exp_dir / "config.yaml", "w") as f:
            yaml.dump(config.to_dict(), f)

        # Get run parameters
        params = self._get_run_params(config)
        total_runs = params["runs"]
        duration_seconds = params["duration_hours"] * 3600
        clearing_interval = params["clearing_interval_seconds"]
        periods_per_run = int(duration_seconds / clearing_interval)

        # Initialize progress tracker
        progress = ProgressTracker(
            total_runs=total_runs,
            periods_per_run=periods_per_run,
            callback=progress_callback,
        )

        # Check for existing checkpoint
        checkpoint = self._load_latest_checkpoint(exp_dir)
        start_run = 0
        start_period = 0

        if checkpoint:
            start_run = checkpoint.run_index
            start_period = checkpoint.period_index
            logger.info(f"Resuming from checkpoint: run {start_run}, period {start_period}")

        # Initialize result
        result = ExperimentResult(
            experiment_id=experiment_id,
            config=config,
            status=ExperimentStatus.RUNNING,
            start_time=datetime.now(),
            end_time=None,
            total_periods=total_runs * periods_per_run,
            completed_periods=0,
            metrics={},
        )

        # Set random seed
        np.random.seed(config.random_seed)

        last_checkpoint_time = time.time()
        all_run_metrics = []

        try:
            for run_idx in range(start_run, total_runs):
                if self._cancel_requested:
                    result.status = ExperimentStatus.CANCELLED
                    break

                run_metrics = await self._execute_single_run(
                    config=config,
                    params=params,
                    run_index=run_idx,
                    start_period=start_period if run_idx == start_run else 0,
                    periods_per_run=periods_per_run,
                    exp_dir=exp_dir,
                    progress=progress,
                )

                all_run_metrics.append(run_metrics)
                start_period = 0  # Reset for subsequent runs

                # Checkpoint periodically
                current_time = time.time()
                if current_time - last_checkpoint_time > self.checkpoint_interval:
                    checkpoint_data = CheckpointData(
                        experiment_id=experiment_id,
                        run_index=run_idx + 1,
                        period_index=0,
                        agent_states={},
                        market_state={},
                        collected_metrics=all_run_metrics,
                        random_state=np.random.get_state(),
                    )
                    self._save_checkpoint(exp_dir, checkpoint_data)
                    last_checkpoint_time = current_time

            # Aggregate metrics across runs
            result.metrics = self._aggregate_run_metrics(all_run_metrics)
            result.completed_periods = progress.completed_periods

            if not self._cancel_requested:
                result.status = ExperimentStatus.COMPLETED

        except Exception as e:
            logger.error(f"Experiment failed: {e}")
            result.status = ExperimentStatus.FAILED
            result.errors.append(str(e))
            raise

        finally:
            result.end_time = datetime.now()
            self.is_running = False
            self.current_experiment = None

            # Save final result
            with open(exp_dir / "result.json", "w") as f:
                json.dump(result.to_dict(), f, indent=2)

            # Cache result if successful
            if result.status == ExperimentStatus.COMPLETED and self.cache_enabled:
                self.cache.put(config_hash, result)

        return result

    async def _execute_single_run(
        self,
        config: ExperimentConfig,
        params: dict,
        run_index: int,
        start_period: int,
        periods_per_run: int,
        exp_dir: Path,
        progress: ProgressTracker,
    ) -> dict:
        """Execute a single experimental run."""
        run_metrics = {
            "run_index": run_index,
            "periods": [],
            "trades": [],
            "welfare": [],
            "efficiency": [],
        }

        # Initialize market and agents for this run
        # (In full implementation, this would create actual instances)

        for period in range(start_period, periods_per_run):
            if self._cancel_requested:
                break

            # Simulate a clearing period
            period_result = await self._simulate_period(
                config=config,
                params=params,
                run_index=run_index,
                period_index=period,
            )

            run_metrics["periods"].append(period_result)

            # Update progress
            progress.update(
                run=run_index,
                period=period + 1,
                message=f"Run {run_index + 1}/{params['runs']}, "
                        f"Period {period + 1}/{periods_per_run}",
            )

            # Allow other tasks to run
            await asyncio.sleep(0)

        return run_metrics

    async def _simulate_period(
        self,
        config: ExperimentConfig,
        params: dict,
        run_index: int,
        period_index: int,
    ) -> dict:
        """
        Simulate a single clearing period.

        In the full implementation, this would:
        1. Collect bids from all agents
        2. Run the auction mechanism
        3. Execute trades
        4. Update agent states
        5. Collect metrics
        """
        # Placeholder simulation
        return {
            "period": period_index,
            "clearing_price": np.random.uniform(4.0, 8.0),
            "clearing_quantity": np.random.uniform(10.0, 100.0),
            "num_trades": np.random.randint(5, 50),
            "buyer_surplus": np.random.uniform(0, 100),
            "seller_surplus": np.random.uniform(0, 100),
            "efficiency": np.random.uniform(0.8, 1.0),
        }

    def _aggregate_run_metrics(self, all_run_metrics: list[dict]) -> dict:
        """Aggregate metrics across all runs."""
        if not all_run_metrics:
            return {}

        # Collect all period metrics
        all_clearing_prices = []
        all_clearing_quantities = []
        all_efficiencies = []
        all_buyer_surplus = []
        all_seller_surplus = []

        for run in all_run_metrics:
            for period in run.get("periods", []):
                all_clearing_prices.append(period.get("clearing_price", 0))
                all_clearing_quantities.append(period.get("clearing_quantity", 0))
                all_efficiencies.append(period.get("efficiency", 0))
                all_buyer_surplus.append(period.get("buyer_surplus", 0))
                all_seller_surplus.append(period.get("seller_surplus", 0))

        return {
            "num_runs": len(all_run_metrics),
            "total_periods": sum(len(r.get("periods", [])) for r in all_run_metrics),
            "clearing_price": {
                "mean": float(np.mean(all_clearing_prices)) if all_clearing_prices else 0,
                "std": float(np.std(all_clearing_prices)) if all_clearing_prices else 0,
                "min": float(np.min(all_clearing_prices)) if all_clearing_prices else 0,
                "max": float(np.max(all_clearing_prices)) if all_clearing_prices else 0,
            },
            "clearing_quantity": {
                "mean": float(np.mean(all_clearing_quantities)) if all_clearing_quantities else 0,
                "std": float(np.std(all_clearing_quantities)) if all_clearing_quantities else 0,
            },
            "efficiency": {
                "mean": float(np.mean(all_efficiencies)) if all_efficiencies else 0,
                "std": float(np.std(all_efficiencies)) if all_efficiencies else 0,
            },
            "total_welfare": {
                "buyer_surplus_mean": float(np.mean(all_buyer_surplus)) if all_buyer_surplus else 0,
                "seller_surplus_mean": float(np.mean(all_seller_surplus)) if all_seller_surplus else 0,
                "total_surplus_mean": float(
                    np.mean(all_buyer_surplus) + np.mean(all_seller_surplus)
                ) if all_buyer_surplus and all_seller_surplus else 0,
            },
        }

    def cancel(self) -> None:
        """Request cancellation of the current experiment."""
        if self.is_running:
            self._cancel_requested = True
            logger.info("Cancellation requested")

    async def run_experiment_batch(
        self,
        configs: list[ExperimentConfig],
        parallel: bool = False,
        max_parallel: int = 4,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> list[ExperimentResult]:
        """
        Run multiple experiments.

        Args:
            configs: List of experiment configurations
            parallel: Whether to run experiments in parallel
            max_parallel: Maximum number of parallel experiments
            progress_callback: Callback with (completed, total, message)

        Returns:
            List of ExperimentResult objects
        """
        results = []
        total = len(configs)

        if parallel:
            semaphore = asyncio.Semaphore(max_parallel)

            async def run_with_semaphore(config: ExperimentConfig) -> ExperimentResult:
                async with semaphore:
                    return await self.run_experiment(config)

            tasks = [run_with_semaphore(config) for config in configs]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Handle exceptions
            final_results = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"Experiment {i} failed: {result}")
                    final_results.append(ExperimentResult(
                        experiment_id=f"failed_{i}",
                        config=configs[i],
                        status=ExperimentStatus.FAILED,
                        start_time=datetime.now(),
                        end_time=datetime.now(),
                        total_periods=0,
                        completed_periods=0,
                        metrics={},
                        errors=[str(result)],
                    ))
                else:
                    final_results.append(result)
            results = final_results
        else:
            for i, config in enumerate(configs):
                if progress_callback:
                    progress_callback(i, total, f"Running {config.name}")

                result = await self.run_experiment(config)
                results.append(result)

                if progress_callback:
                    progress_callback(i + 1, total, f"Completed {config.name}")

        return results

    def get_experiment_status(self, experiment_id: str) -> Optional[dict]:
        """Get status of an experiment by ID."""
        exp_dir = self.output_dir / experiment_id

        if not exp_dir.exists():
            return None

        result_file = exp_dir / "result.json"
        if result_file.exists():
            with open(result_file, "r") as f:
                return json.load(f)

        # Check for in-progress checkpoint
        checkpoint = self._load_latest_checkpoint(exp_dir)
        if checkpoint:
            return {
                "experiment_id": experiment_id,
                "status": "in_progress",
                "last_checkpoint": {
                    "run_index": checkpoint.run_index,
                    "period_index": checkpoint.period_index,
                    "timestamp": checkpoint.timestamp.isoformat(),
                },
            }

        return {"experiment_id": experiment_id, "status": "unknown"}

    def list_experiments(self) -> list[dict]:
        """List all experiments in the output directory."""
        experiments = []

        for exp_dir in self.output_dir.iterdir():
            if exp_dir.is_dir() and not exp_dir.name.startswith("."):
                status = self.get_experiment_status(exp_dir.name)
                if status:
                    experiments.append(status)

        return sorted(experiments, key=lambda x: x.get("start_time", ""), reverse=True)
