"""Training pipeline orchestration for continuous learning.

Provides:
- Pipeline stages (validate, train, evaluate, deploy)
- DAG execution for Airflow/Kubeflow
- Progress tracking and logging
- Artifact management
"""

import asyncio
import logging
import json
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import uuid

logger = logging.getLogger(__name__)


class PipelineStage(Enum):
    """Stages of the training pipeline."""
    VALIDATE_DATA = "validate_data"
    PREPARE_DATA = "prepare_data"
    TRAIN_MODEL = "train_model"
    EVALUATE_MODEL = "evaluate_model"
    COMPARE_MODELS = "compare_models"
    SHADOW_TEST = "shadow_test"
    DEPLOY_MODEL = "deploy_model"
    CLEANUP = "cleanup"


class PipelineStatus(Enum):
    """Status of pipeline run."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"


@dataclass
class StageResult:
    """Result of a pipeline stage."""
    stage: PipelineStage
    status: PipelineStatus
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration_seconds: float = 0.0
    outputs: Dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None
    logs: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "stage": self.stage.value,
            "status": self.status.value,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_seconds": self.duration_seconds,
            "outputs": self.outputs,
            "error_message": self.error_message,
        }


@dataclass
class PipelineRun:
    """A single pipeline run."""
    run_id: str
    model_name: str
    trigger_type: str
    status: PipelineStatus
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    stages: Dict[str, StageResult] = field(default_factory=dict)
    config: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def duration_seconds(self) -> float:
        """Calculate total duration."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        elif self.started_at:
            return (datetime.now() - self.started_at).total_seconds()
        return 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "run_id": self.run_id,
            "model_name": self.model_name,
            "trigger_type": self.trigger_type,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_seconds": self.duration_seconds,
            "stages": {k: v.to_dict() for k, v in self.stages.items()},
            "config": self.config,
            "metadata": self.metadata,
        }


@dataclass
class PipelineConfig:
    """Configuration for training pipeline."""
    # Model
    model_name: str = "shakti_model"
    model_type: str = "tft"  # tft, lstm, xgboost

    # Data
    training_window_days: int = 90
    validation_split: float = 0.2
    min_samples: int = 10000

    # Training
    max_epochs: int = 100
    early_stopping_patience: int = 10
    batch_size: int = 64
    learning_rate: float = 0.001

    # Evaluation
    min_improvement_pct: float = 2.0
    max_regression_pct: float = 5.0
    shadow_test_hours: int = 24

    # Deployment
    deployment_strategy: str = "canary"  # canary, blue_green, direct
    canary_percentage: float = 10.0

    # Artifacts
    artifacts_path: str = "./artifacts"
    save_checkpoints: bool = True


class TrainingPipeline:
    """Orchestrate model training pipeline."""

    def __init__(
        self,
        config: Optional[PipelineConfig] = None,
        data_collector=None,
        data_validator=None,
        model_registry=None,
        deployer=None,
    ):
        """Initialize training pipeline.

        Args:
            config: Pipeline configuration
            data_collector: Data collector for training data
            data_validator: Data validator
            model_registry: Model registry for versioning
            deployer: Model deployer
        """
        self.config = config or PipelineConfig()
        self.data_collector = data_collector
        self.data_validator = data_validator
        self.model_registry = model_registry
        self.deployer = deployer

        # Stage handlers
        self._stage_handlers: Dict[PipelineStage, Callable] = {
            PipelineStage.VALIDATE_DATA: self._validate_data,
            PipelineStage.PREPARE_DATA: self._prepare_data,
            PipelineStage.TRAIN_MODEL: self._train_model,
            PipelineStage.EVALUATE_MODEL: self._evaluate_model,
            PipelineStage.COMPARE_MODELS: self._compare_models,
            PipelineStage.SHADOW_TEST: self._shadow_test,
            PipelineStage.DEPLOY_MODEL: self._deploy_model,
            PipelineStage.CLEANUP: self._cleanup,
        }

        # Pipeline state
        self._current_run: Optional[PipelineRun] = None
        self._run_history: List[PipelineRun] = []

        # Artifacts
        self._artifacts_path = Path(self.config.artifacts_path)
        self._artifacts_path.mkdir(parents=True, exist_ok=True)

        # Callbacks
        self._stage_callbacks: List[Callable[[PipelineStage, StageResult], None]] = []

    def on_stage_complete(self, callback: Callable[[PipelineStage, StageResult], None]):
        """Register callback for stage completion.

        Args:
            callback: Callback function
        """
        self._stage_callbacks.append(callback)

    async def run(
        self,
        trigger_type: str = "manual",
        stages: Optional[List[PipelineStage]] = None,
        config_overrides: Optional[Dict[str, Any]] = None,
    ) -> PipelineRun:
        """Run the training pipeline.

        Args:
            trigger_type: What triggered this run
            stages: Specific stages to run (None for all)
            config_overrides: Override config values

        Returns:
            PipelineRun with results
        """
        # Create run
        run_id = f"run-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"

        run = PipelineRun(
            run_id=run_id,
            model_name=self.config.model_name,
            trigger_type=trigger_type,
            status=PipelineStatus.PENDING,
            created_at=datetime.now(),
            config=config_overrides or {},
        )

        self._current_run = run
        run.status = PipelineStatus.RUNNING
        run.started_at = datetime.now()

        logger.info(f"Starting pipeline run: {run_id}")

        # Determine stages to run
        if stages is None:
            stages = [
                PipelineStage.VALIDATE_DATA,
                PipelineStage.PREPARE_DATA,
                PipelineStage.TRAIN_MODEL,
                PipelineStage.EVALUATE_MODEL,
                PipelineStage.COMPARE_MODELS,
                PipelineStage.DEPLOY_MODEL,
                PipelineStage.CLEANUP,
            ]

        # Run stages
        context: Dict[str, Any] = {}  # Shared context between stages

        for stage in stages:
            try:
                result = await self._run_stage(stage, context)
                run.stages[stage.value] = result

                # Dispatch callbacks
                for callback in self._stage_callbacks:
                    try:
                        if asyncio.iscoroutinefunction(callback):
                            await callback(stage, result)
                        else:
                            callback(stage, result)
                    except Exception as e:
                        logger.error(f"Stage callback error: {e}")

                # Stop on failure
                if result.status == PipelineStatus.FAILED:
                    run.status = PipelineStatus.FAILED
                    break

                # Update context with outputs
                context.update(result.outputs)

            except Exception as e:
                logger.error(f"Pipeline error at {stage.value}: {e}")
                run.stages[stage.value] = StageResult(
                    stage=stage,
                    status=PipelineStatus.FAILED,
                    started_at=datetime.now(),
                    completed_at=datetime.now(),
                    error_message=str(e),
                )
                run.status = PipelineStatus.FAILED
                break

        # Mark complete
        if run.status != PipelineStatus.FAILED:
            run.status = PipelineStatus.SUCCESS

        run.completed_at = datetime.now()
        self._run_history.append(run)
        self._current_run = None

        # Save run info
        await self._save_run(run)

        logger.info(f"Pipeline run completed: {run_id} - {run.status.value}")

        return run

    async def _run_stage(
        self,
        stage: PipelineStage,
        context: Dict[str, Any],
    ) -> StageResult:
        """Run a single pipeline stage.

        Args:
            stage: Stage to run
            context: Shared context

        Returns:
            StageResult
        """
        logger.info(f"Running stage: {stage.value}")

        result = StageResult(
            stage=stage,
            status=PipelineStatus.RUNNING,
            started_at=datetime.now(),
        )

        try:
            handler = self._stage_handlers.get(stage)
            if handler is None:
                raise ValueError(f"No handler for stage: {stage.value}")

            outputs = await handler(context)

            result.status = PipelineStatus.SUCCESS
            result.outputs = outputs or {}

        except Exception as e:
            logger.error(f"Stage {stage.value} failed: {e}")
            result.status = PipelineStatus.FAILED
            result.error_message = str(e)

        result.completed_at = datetime.now()
        result.duration_seconds = (result.completed_at - result.started_at).total_seconds()

        return result

    async def _validate_data(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Validate training data."""
        logger.info("Validating training data...")

        if not self.data_collector or not self.data_validator:
            logger.warning("No data collector/validator configured, skipping validation")
            return {"validation_skipped": True}

        # Get training data window
        end_date = datetime.now()
        start_date = end_date - timedelta(days=self.config.training_window_days)

        # Read predictions and actuals
        predictions = await self.data_collector.read_predictions(
            model_name=self.config.model_name,
            start_date=start_date,
            end_date=end_date,
        )

        actuals = await self.data_collector.read_actuals(
            model_name=self.config.model_name,
            start_date=start_date,
            end_date=end_date,
        )

        # Validate
        validation_result = self.data_validator.validate_for_training(
            [p.to_dict() for p in predictions],
            min_samples=self.config.min_samples,
        )

        if not validation_result.is_valid:
            raise ValueError(f"Data validation failed: {validation_result.issues}")

        return {
            "predictions_count": len(predictions),
            "actuals_count": len(actuals),
            "validation_result": validation_result.to_dict(),
        }

    async def _prepare_data(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare data for training."""
        logger.info("Preparing training data...")

        if not self.data_collector:
            # Generate mock data for demo
            return self._generate_mock_data()

        # Join predictions with actuals
        end_date = datetime.now()
        start_date = end_date - timedelta(days=self.config.training_window_days)

        joined_data = await self.data_collector.join_predictions_actuals(
            model_name=self.config.model_name,
            start_date=start_date,
            end_date=end_date,
        )

        # Filter to records with actuals
        labeled_data = [d for d in joined_data if d["has_actual"]]

        # Split into train/val
        n = len(labeled_data)
        split_idx = int(n * (1 - self.config.validation_split))

        train_data = labeled_data[:split_idx]
        val_data = labeled_data[split_idx:]

        # Save to artifacts
        train_path = self._artifacts_path / "train_data.json"
        val_path = self._artifacts_path / "val_data.json"

        with open(train_path, "w") as f:
            json.dump(train_data, f)
        with open(val_path, "w") as f:
            json.dump(val_data, f)

        return {
            "total_samples": len(labeled_data),
            "train_samples": len(train_data),
            "val_samples": len(val_data),
            "train_path": str(train_path),
            "val_path": str(val_path),
        }

    def _generate_mock_data(self) -> Dict[str, Any]:
        """Generate mock training data."""
        import random

        n_samples = 5000
        data = []

        for i in range(n_samples):
            data.append({
                "features": {
                    "hour": random.randint(0, 23),
                    "price": 50 + random.gauss(0, 5),
                    "load": 30000 + random.gauss(0, 2000),
                },
                "target": 50 + random.gauss(0, 3),
            })

        train_data = data[:int(n_samples * 0.8)]
        val_data = data[int(n_samples * 0.8):]

        return {
            "total_samples": n_samples,
            "train_samples": len(train_data),
            "val_samples": len(val_data),
            "mock_data": True,
        }

    async def _train_model(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Train the model."""
        logger.info("Training model...")

        # This would integrate with actual training code
        # For demo, we simulate training

        await asyncio.sleep(2)  # Simulate training time

        model_version = f"v{datetime.now().strftime('%Y%m%d%H%M%S')}"

        return {
            "model_version": model_version,
            "epochs_trained": self.config.max_epochs,
            "final_loss": 0.05,
            "training_completed": True,
        }

    async def _evaluate_model(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate the trained model."""
        logger.info("Evaluating model...")

        # Simulate evaluation
        await asyncio.sleep(1)

        return {
            "mape": 0.08,
            "rmse": 2.5,
            "mae": 1.8,
            "r2": 0.92,
        }

    async def _compare_models(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Compare new model with current production model."""
        logger.info("Comparing with production model...")

        new_mape = context.get("mape", 0.08)
        current_mape = 0.10  # Would get from production model

        improvement = (current_mape - new_mape) / current_mape * 100

        should_deploy = improvement >= self.config.min_improvement_pct

        return {
            "new_mape": new_mape,
            "current_mape": current_mape,
            "improvement_pct": improvement,
            "meets_threshold": should_deploy,
            "decision": "deploy" if should_deploy else "reject",
        }

    async def _shadow_test(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Run shadow testing for new model."""
        logger.info("Running shadow test...")

        if not context.get("meets_threshold", False):
            return {"skipped": True, "reason": "Model did not meet threshold"}

        # In production, this would run for shadow_test_hours
        # For demo, we simulate
        await asyncio.sleep(1)

        return {
            "shadow_test_completed": True,
            "shadow_mape": 0.075,
            "production_mape": 0.10,
            "shadow_requests": 1000,
        }

    async def _deploy_model(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Deploy the new model."""
        logger.info("Deploying model...")

        if not context.get("meets_threshold", False):
            return {"deployed": False, "reason": "Model did not meet threshold"}

        if self.deployer:
            deployment_result = await self.deployer.deploy(
                model_name=self.config.model_name,
                model_version=context.get("model_version"),
                strategy=self.config.deployment_strategy,
            )
            return {"deployed": True, "deployment": deployment_result}

        return {
            "deployed": True,
            "model_version": context.get("model_version"),
            "strategy": self.config.deployment_strategy,
        }

    async def _cleanup(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Clean up temporary artifacts."""
        logger.info("Cleaning up...")

        # Remove temporary files
        temp_files = list(self._artifacts_path.glob("*.tmp"))
        for f in temp_files:
            f.unlink()

        return {"cleaned_files": len(temp_files)}

    async def _save_run(self, run: PipelineRun):
        """Save run information to disk."""
        runs_path = self._artifacts_path / "runs"
        runs_path.mkdir(exist_ok=True)

        run_file = runs_path / f"{run.run_id}.json"
        with open(run_file, "w") as f:
            json.dump(run.to_dict(), f, indent=2)

    def get_run_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent run history.

        Args:
            limit: Maximum runs to return

        Returns:
            List of run dictionaries
        """
        return [r.to_dict() for r in self._run_history[-limit:]]

    def get_current_run(self) -> Optional[Dict[str, Any]]:
        """Get current running pipeline."""
        if self._current_run:
            return self._current_run.to_dict()
        return None

    def get_stats(self) -> Dict[str, Any]:
        """Get pipeline statistics."""
        success_count = sum(1 for r in self._run_history if r.status == PipelineStatus.SUCCESS)
        fail_count = sum(1 for r in self._run_history if r.status == PipelineStatus.FAILED)

        return {
            "total_runs": len(self._run_history),
            "successful_runs": success_count,
            "failed_runs": fail_count,
            "success_rate": success_count / len(self._run_history) if self._run_history else 0,
            "is_running": self._current_run is not None,
        }


def generate_airflow_dag(config: PipelineConfig) -> str:
    """Generate Airflow DAG code for the pipeline.

    Args:
        config: Pipeline configuration

    Returns:
        DAG Python code as string
    """
    dag_code = f'''
"""SHAKTI-CHAIN Model Retraining DAG.

Generated by continuous learning pipeline.
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator

default_args = {{
    'owner': 'shakti-ml',
    'depends_on_past': False,
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}}

def validate_production_data(**kwargs):
    """Validate production data for training."""
    from src.continuous_learning import DataCollector, DataValidator
    # Implementation here
    return {{"valid": True}}

def prepare_training_data(**kwargs):
    """Prepare training data."""
    # Implementation here
    return {{"prepared": True}}

def train_{config.model_type}_model(**kwargs):
    """Train {config.model_type} model."""
    # Implementation here
    return {{"trained": True}}

def evaluate_and_compare(**kwargs):
    """Evaluate model and compare with production."""
    # Implementation here
    return {{"should_deploy": True}}

def conditional_deploy(**kwargs):
    """Deploy if model is better."""
    ti = kwargs['ti']
    eval_result = ti.xcom_pull(task_ids='evaluate_model')
    if eval_result.get('should_deploy'):
        # Deploy model
        pass
    return {{"deployed": eval_result.get('should_deploy')}}

with DAG(
    'shakti_{config.model_name}_retraining',
    default_args=default_args,
    description='Retrain SHAKTI-CHAIN {config.model_name} model',
    schedule_interval='@weekly',
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=['ml', 'retraining', 'shakti'],
) as dag:

    validate_data = PythonOperator(
        task_id='validate_data',
        python_callable=validate_production_data,
    )

    prepare_data = PythonOperator(
        task_id='prepare_data',
        python_callable=prepare_training_data,
    )

    train_model = PythonOperator(
        task_id='train_model',
        python_callable=train_{config.model_type}_model,
    )

    evaluate_model = PythonOperator(
        task_id='evaluate_model',
        python_callable=evaluate_and_compare,
    )

    deploy_if_better = PythonOperator(
        task_id='deploy_if_better',
        python_callable=conditional_deploy,
    )

    validate_data >> prepare_data >> train_model >> evaluate_model >> deploy_if_better
'''
    return dag_code
