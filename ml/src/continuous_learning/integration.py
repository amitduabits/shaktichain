"""
SHAKTI-CHAIN Continuous Learning - Integration Module.

Unified interface for the continuous learning pipeline that connects:
- Data collection and storage
- Data validation and drift detection
- Retraining triggers
- Training pipeline orchestration
- Evaluation gates
- Model deployment with canary rollout
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Callable, Awaitable
from pathlib import Path

from .collector import DataCollector, StorageBackend, DataLakeConfig
from .validator import DataValidator, DriftDetector, ValidationResult
from .triggers import RetrainingTrigger, TriggerConfig, TriggerEvent
from .pipeline import TrainingPipeline, PipelineConfig, PipelineStage, PipelineRun
from .evaluation import EvaluationGate, EvaluationConfig, ShadowTest
from .deployer import (
    ModelDeployer, DeploymentOrchestrator, ModelRegistry, InMemoryModelRegistry,
    MetricsCollector, InMemoryMetricsCollector, TrafficRouter, InMemoryTrafficRouter,
    ModelArtifact, DeploymentTarget, DeploymentStrategy, CanaryConfig, DeploymentRecord
)

logger = logging.getLogger(__name__)


class ContinuousLearningStatus(Enum):
    """Status of the continuous learning system."""
    IDLE = "idle"
    COLLECTING = "collecting"
    VALIDATING = "validating"
    TRIGGERED = "triggered"
    TRAINING = "training"
    EVALUATING = "evaluating"
    DEPLOYING = "deploying"
    MONITORING = "monitoring"
    ERROR = "error"


@dataclass
class ContinuousLearningConfig:
    """Configuration for continuous learning pipeline."""
    # Storage
    storage_path: str = "./continuous_learning"
    data_lake_path: str = "./data_lake"

    # Collection
    collection_interval_seconds: int = 60
    batch_size: int = 100

    # Validation
    min_samples_for_training: int = 1000
    drift_threshold: float = 0.05
    quality_threshold: float = 0.95

    # Triggers
    scheduled_interval_hours: int = 24
    performance_threshold: float = 0.1
    staleness_days: int = 7

    # Training
    training_timeout_hours: int = 4
    max_concurrent_runs: int = 1

    # Evaluation
    min_improvement_threshold: float = 0.01
    shadow_test_duration_hours: int = 24
    shadow_test_min_requests: int = 1000
    require_human_approval: bool = False

    # Deployment
    deployment_strategy: DeploymentStrategy = DeploymentStrategy.CANARY
    canary_stages: List[float] = field(default_factory=lambda: [0.1, 0.5, 1.0])
    canary_stage_duration_minutes: int = 60
    auto_rollback: bool = True

    # Monitoring
    monitoring_interval_seconds: int = 300
    alert_webhook: Optional[str] = None


@dataclass
class ModelStatus:
    """Status of a model in the continuous learning pipeline."""
    model_name: str
    current_version: Optional[str] = None
    candidate_version: Optional[str] = None
    status: ContinuousLearningStatus = ContinuousLearningStatus.IDLE
    last_training: Optional[datetime] = None
    last_evaluation: Optional[datetime] = None
    last_deployment: Optional[datetime] = None
    pending_triggers: List[TriggerEvent] = field(default_factory=list)
    active_pipeline_run: Optional[str] = None
    active_deployment: Optional[str] = None
    metrics: Dict[str, float] = field(default_factory=dict)


class ContinuousLearningPipeline:
    """
    Unified continuous learning pipeline.

    Orchestrates the full ML lifecycle:
    1. Data collection -> Data lake
    2. Data validation -> Drift detection
    3. Retraining triggers -> Pipeline execution
    4. Model training -> Artifact creation
    5. Evaluation gates -> Quality assurance
    6. Deployment -> Canary rollout

    Usage:
        pipeline = ContinuousLearningPipeline(config)
        await pipeline.start()

        # Record predictions and actuals
        await pipeline.record_prediction(model_name, features, prediction)
        await pipeline.record_actual(model_name, actual, timestamp)

        # Manual trigger
        await pipeline.trigger_retraining(model_name, reason="manual")

        # Stop
        await pipeline.stop()
    """

    def __init__(
        self,
        config: ContinuousLearningConfig,
        data_lake_config: Optional[DataLakeConfig] = None,
        model_registry: Optional[ModelRegistry] = None,
        metrics_collector: Optional[MetricsCollector] = None,
        traffic_router: Optional[TrafficRouter] = None
    ):
        self.config = config
        self._running = False
        self._tasks: List[asyncio.Task] = []
        self._model_status: Dict[str, ModelStatus] = {}

        # Initialize data lake config
        self.data_lake_config = data_lake_config or DataLakeConfig(
            backend=StorageBackend.LOCAL,
            bucket_name=config.data_lake_path,
            batch_size=config.batch_size
        )

        # Initialize components
        self.collector = DataCollector(
            config=self.data_lake_config
        )

        self.validator = DataValidator(
            drift_threshold=config.drift_threshold
        )

        # Triggers are created per-model in register_model
        self._triggers: Dict[str, RetrainingTrigger] = {}
        self._trigger_config = TriggerConfig(
            scheduled_interval_hours=config.scheduled_interval_hours,
            performance_threshold=config.performance_threshold,
            drift_threshold=config.drift_threshold,
            staleness_days=config.staleness_days
        )

        self.pipeline = TrainingPipeline(
            config=PipelineConfig(
                pipeline_name="shakti_chain_continuous_learning",
                storage_path=config.storage_path,
                timeout_hours=config.training_timeout_hours
            )
        )

        self.evaluation_gate = EvaluationGate(
            config=EvaluationConfig(
                min_improvement_threshold=config.min_improvement_threshold,
                require_human_approval=config.require_human_approval
            ),
            storage_path=config.storage_path
        )

        self.shadow_test = ShadowTest(
            storage_path=config.storage_path
        )

        # Initialize deployment components
        self.model_registry = model_registry or InMemoryModelRegistry()
        self.metrics_collector = metrics_collector or InMemoryMetricsCollector()
        self.traffic_router = traffic_router or InMemoryTrafficRouter()

        self.deployer = ModelDeployer(
            model_registry=self.model_registry,
            metrics_collector=self.metrics_collector,
            traffic_router=self.traffic_router,
            storage_path=f"{config.storage_path}/deployments",
            default_canary_config=CanaryConfig(
                stages=config.canary_stages,
                stage_duration_minutes=config.canary_stage_duration_minutes,
                auto_rollback=config.auto_rollback
            )
        )

        self.orchestrator = DeploymentOrchestrator(
            deployer=self.deployer,
            notification_webhook=config.alert_webhook
        )

        # Callbacks
        self._on_trigger_callbacks: List[Callable[[str, TriggerEvent], Awaitable[None]]] = []
        self._on_training_complete_callbacks: List[Callable[[str, PipelineRun], Awaitable[None]]] = []
        self._on_deployment_callbacks: List[Callable[[str, DeploymentRecord], Awaitable[None]]] = []

    def on_trigger(self, callback: Callable[[str, TriggerEvent], Awaitable[None]]):
        """Register callback for retraining triggers."""
        self._on_trigger_callbacks.append(callback)

    def on_training_complete(self, callback: Callable[[str, PipelineRun], Awaitable[None]]):
        """Register callback for training completion."""
        self._on_training_complete_callbacks.append(callback)

    def on_deployment(self, callback: Callable[[str, DeploymentRecord], Awaitable[None]]):
        """Register callback for deployments."""
        self._on_deployment_callbacks.append(callback)

    async def start(self):
        """Start the continuous learning pipeline."""
        if self._running:
            logger.warning("Pipeline already running")
            return

        self._running = True
        logger.info("Starting continuous learning pipeline")

        # Start background tasks
        self._tasks = [
            asyncio.create_task(self._collection_loop()),
            asyncio.create_task(self._trigger_loop()),
            asyncio.create_task(self._monitoring_loop())
        ]

        logger.info("Continuous learning pipeline started")

    async def stop(self):
        """Stop the continuous learning pipeline."""
        if not self._running:
            return

        self._running = False
        logger.info("Stopping continuous learning pipeline")

        # Cancel tasks
        for task in self._tasks:
            task.cancel()

        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks = []

        # Flush collector
        await self.collector.flush()

        logger.info("Continuous learning pipeline stopped")

    async def _collection_loop(self):
        """Background task for data collection."""
        while self._running:
            try:
                await asyncio.sleep(self.config.collection_interval_seconds)
                # Collection happens through record_prediction/record_actual calls
                # This loop just ensures periodic flushing
                await self.collector.flush()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Collection loop error: {e}")

    async def _trigger_loop(self):
        """Background task for checking retraining triggers."""
        while self._running:
            try:
                await asyncio.sleep(60)  # Check every minute

                # Check triggers for all registered models
                for model_name, trigger in self._triggers.items():
                    triggers = await trigger.check_all()

                    for trigger_event in triggers:
                        await self._handle_trigger(model_name, trigger_event)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Trigger loop error: {e}")

    async def _monitoring_loop(self):
        """Background task for monitoring."""
        while self._running:
            try:
                await asyncio.sleep(self.config.monitoring_interval_seconds)

                # Monitor active deployments
                active_deployments = await self.deployer.get_active_deployments()
                for deployment in active_deployments:
                    logger.debug(
                        f"Active deployment: {deployment.deployment_id} "
                        f"status={deployment.status.value} "
                        f"traffic={deployment.current_traffic_percentage:.0%}"
                    )

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Monitoring loop error: {e}")

    async def register_model(
        self,
        model_name: str,
        initial_version: Optional[str] = None,
        reference_data: Optional[List[Dict]] = None
    ):
        """
        Register a model for continuous learning.

        Args:
            model_name: Name of the model
            initial_version: Current production version
            reference_data: Reference data for drift detection
        """
        if model_name in self._model_status:
            logger.warning(f"Model {model_name} already registered")
            return

        self._model_status[model_name] = ModelStatus(
            model_name=model_name,
            current_version=initial_version
        )

        # Set reference data for drift detection
        if reference_data:
            self.validator.drift_detector.set_reference(reference_data)

        # Create trigger for this model
        self._triggers[model_name] = RetrainingTrigger(
            model_name=model_name,
            config=self._trigger_config,
            drift_detector=self.validator.drift_detector
        )

        logger.info(f"Registered model {model_name} (version={initial_version})")

    async def record_prediction(
        self,
        model_name: str,
        model_version: str,
        input_features: Dict[str, Any],
        prediction: Any,
        prediction_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Record a model prediction."""
        return await self.collector.record_prediction(
            model_name=model_name,
            model_version=model_version,
            input_features=input_features,
            prediction=prediction,
            prediction_id=prediction_id,
            metadata=metadata
        )

    async def record_actual(
        self,
        model_name: str,
        actual_value: Any,
        timestamp: datetime,
        prediction_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Record actual outcome."""
        return await self.collector.record_actual(
            model_name=model_name,
            actual_value=actual_value,
            timestamp=timestamp,
            prediction_id=prediction_id,
            metadata=metadata
        )

    async def trigger_retraining(
        self,
        model_name: str,
        reason: str = "manual"
    ) -> TriggerEvent:
        """Manually trigger retraining."""
        trigger = self._triggers.get(model_name)
        if not trigger:
            raise ValueError(f"Model {model_name} not registered")
        trigger_event = await trigger.trigger_manual(reason)
        await self._handle_trigger(model_name, trigger_event)
        return trigger_event

    async def _handle_trigger(self, model_name: str, trigger_event: TriggerEvent):
        """Handle a retraining trigger."""
        status = self._model_status.get(model_name)
        if not status:
            logger.warning(f"Model {model_name} not registered")
            return

        # Check if already training
        if status.status in [
            ContinuousLearningStatus.TRAINING,
            ContinuousLearningStatus.EVALUATING,
            ContinuousLearningStatus.DEPLOYING
        ]:
            logger.info(f"Model {model_name} already in pipeline, queuing trigger")
            status.pending_triggers.append(trigger_event)
            return

        logger.info(f"Handling trigger for {model_name}: {trigger_event.trigger_type}")

        # Notify callbacks
        for callback in self._on_trigger_callbacks:
            try:
                await callback(model_name, trigger_event)
            except Exception as e:
                logger.error(f"Trigger callback error: {e}")

        # Start pipeline
        await self._run_pipeline(model_name, trigger_event)

    async def _run_pipeline(self, model_name: str, trigger_event: TriggerEvent):
        """Run the full training pipeline."""
        status = self._model_status[model_name]
        status.status = ContinuousLearningStatus.VALIDATING

        try:
            # 1. Get training data
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=30)

            training_data = await self.collector.join_predictions_actuals(
                model_name=model_name,
                start_date=start_date,
                end_date=end_date
            )

            # 2. Validate data
            validation_result = self.validator.validate_for_training(
                data=training_data,
                min_samples=self.config.min_samples_for_training
            )

            if not validation_result.is_valid:
                logger.warning(
                    f"Training data validation failed for {model_name}: "
                    f"{validation_result.errors}"
                )
                status.status = ContinuousLearningStatus.IDLE
                return

            # 3. Run training pipeline
            status.status = ContinuousLearningStatus.TRAINING

            pipeline_run = await self.pipeline.run(
                trigger_type=trigger_event.trigger_type,
                model_name=model_name,
                config_overrides={
                    "training_data": training_data,
                    "trigger_event": trigger_event.to_dict()
                }
            )

            status.active_pipeline_run = pipeline_run.run_id
            status.last_training = datetime.utcnow()

            if pipeline_run.status.value != "completed":
                logger.error(f"Pipeline run failed for {model_name}: {pipeline_run.error}")
                status.status = ContinuousLearningStatus.ERROR
                return

            # 4. Evaluate candidate model
            status.status = ContinuousLearningStatus.EVALUATING

            candidate_version = pipeline_run.artifacts.get("model_version", "unknown")
            status.candidate_version = candidate_version

            # Get evaluation data
            eval_data = await self.collector.join_predictions_actuals(
                model_name=model_name,
                start_date=end_date - timedelta(days=7),
                end_date=end_date
            )

            baseline_predictions = [d.get("prediction") for d in eval_data]
            actuals = [d.get("actual") for d in eval_data]

            # Run evaluation (candidate predictions would come from pipeline)
            candidate_predictions = pipeline_run.artifacts.get(
                "candidate_predictions",
                baseline_predictions  # Placeholder
            )

            evaluation_result = await self.evaluation_gate.evaluate(
                baseline_model=f"{model_name}:{status.current_version}",
                candidate_model=f"{model_name}:{candidate_version}",
                baseline_predictions=baseline_predictions,
                candidate_predictions=candidate_predictions,
                actuals=actuals
            )

            status.last_evaluation = datetime.utcnow()

            if not evaluation_result.passed:
                logger.warning(
                    f"Evaluation failed for {model_name} candidate v{candidate_version}: "
                    f"{evaluation_result.failure_reason}"
                )
                status.status = ContinuousLearningStatus.IDLE
                return

            # Notify training complete
            for callback in self._on_training_complete_callbacks:
                try:
                    await callback(model_name, pipeline_run)
                except Exception as e:
                    logger.error(f"Training complete callback error: {e}")

            # 5. Deploy candidate
            status.status = ContinuousLearningStatus.DEPLOYING

            await self._deploy_model(model_name, candidate_version, pipeline_run)

        except Exception as e:
            logger.error(f"Pipeline error for {model_name}: {e}")
            status.status = ContinuousLearningStatus.ERROR
            raise

    async def _deploy_model(
        self,
        model_name: str,
        version: str,
        pipeline_run: PipelineRun
    ):
        """Deploy a model version."""
        status = self._model_status[model_name]

        # Create model artifact
        artifact = ModelArtifact(
            model_name=model_name,
            model_version=version,
            artifact_path=pipeline_run.artifacts.get("model_path", f"./models/{model_name}/{version}"),
            model_type=pipeline_run.artifacts.get("model_type", "unknown"),
            metadata={
                "pipeline_run_id": pipeline_run.run_id,
                "trigger_type": pipeline_run.trigger_type
            }
        )

        # Create deployment target
        target = DeploymentTarget(
            name=f"{model_name}-production",
            endpoint=f"https://api.shakti-chain.io/models/{model_name}",
            environment="production"
        )

        # Deploy
        deployment = await self.deployer.deploy(
            model_artifact=artifact,
            target=target,
            strategy=self.config.deployment_strategy,
            wait_for_completion=False  # Don't block
        )

        status.active_deployment = deployment.deployment_id

        # Monitor deployment in background
        asyncio.create_task(self._monitor_deployment(model_name, deployment))

    async def _monitor_deployment(self, model_name: str, deployment: DeploymentRecord):
        """Monitor a deployment until completion."""
        status = self._model_status[model_name]

        while True:
            await asyncio.sleep(30)

            current = await self.deployer.get_deployment_status(deployment.deployment_id)
            if not current:
                break

            if current.status.value in ["completed", "failed", "rolled_back"]:
                if current.status.value == "completed":
                    status.current_version = current.model_artifact.model_version
                    status.last_deployment = datetime.utcnow()
                    logger.info(
                        f"Deployment completed for {model_name} "
                        f"v{current.model_artifact.model_version}"
                    )

                status.status = ContinuousLearningStatus.IDLE
                status.active_deployment = None
                status.candidate_version = None

                # Notify callbacks
                for callback in self._on_deployment_callbacks:
                    try:
                        await callback(model_name, current)
                    except Exception as e:
                        logger.error(f"Deployment callback error: {e}")

                # Process pending triggers
                if status.pending_triggers:
                    next_trigger = status.pending_triggers.pop(0)
                    await self._handle_trigger(model_name, next_trigger)

                break

    async def get_model_status(self, model_name: str) -> Optional[ModelStatus]:
        """Get status of a model."""
        return self._model_status.get(model_name)

    async def get_all_model_status(self) -> Dict[str, ModelStatus]:
        """Get status of all models."""
        return dict(self._model_status)

    async def get_pipeline_history(
        self,
        model_name: Optional[str] = None,
        limit: int = 100
    ) -> List[PipelineRun]:
        """Get pipeline run history."""
        return await self.pipeline.get_run_history(limit=limit)

    async def get_deployment_history(
        self,
        model_name: Optional[str] = None,
        limit: int = 100
    ) -> List[DeploymentRecord]:
        """Get deployment history."""
        return await self.deployer.get_deployment_history(
            model_name=model_name,
            limit=limit
        )

    async def rollback_model(
        self,
        model_name: str,
        reason: str = "Manual rollback"
    ) -> Optional[DeploymentRecord]:
        """Rollback model to previous version."""
        status = self._model_status.get(model_name)
        if not status or not status.active_deployment:
            logger.warning(f"No active deployment for {model_name}")
            return None

        return await self.deployer.rollback_manual(
            deployment_id=status.active_deployment,
            reason=reason
        )


async def create_default_pipeline(
    storage_path: str = "./continuous_learning",
    alert_webhook: Optional[str] = None
) -> ContinuousLearningPipeline:
    """
    Create a default continuous learning pipeline.

    Args:
        storage_path: Path for storing pipeline data
        alert_webhook: Webhook URL for alerts

    Returns:
        Configured ContinuousLearningPipeline
    """
    config = ContinuousLearningConfig(
        storage_path=storage_path,
        data_lake_path=f"{storage_path}/data_lake",
        alert_webhook=alert_webhook
    )

    pipeline = ContinuousLearningPipeline(config)
    return pipeline


async def demo_continuous_learning():
    """Demonstrate the continuous learning pipeline."""
    print("=" * 60)
    print("SHAKTI-CHAIN Continuous Learning Pipeline Demo")
    print("=" * 60)

    # Create pipeline
    config = ContinuousLearningConfig(
        storage_path="./demo_continuous_learning",
        scheduled_interval_hours=1,  # Short for demo
        min_samples_for_training=10,  # Low for demo
        require_human_approval=False
    )

    pipeline = ContinuousLearningPipeline(config)

    # Register callbacks
    async def on_trigger(model_name: str, event: TriggerEvent):
        print(f"  [TRIGGER] {model_name}: {event.trigger_type} - {event.reason}")

    async def on_training(model_name: str, run: PipelineRun):
        print(f"  [TRAINING] {model_name}: {run.status.value}")

    async def on_deploy(model_name: str, record: DeploymentRecord):
        print(f"  [DEPLOY] {model_name}: {record.status.value}")

    pipeline.on_trigger(on_trigger)
    pipeline.on_training_complete(on_training)
    pipeline.on_deployment(on_deploy)

    # Register models
    print("\n1. Registering models...")
    await pipeline.register_model(
        model_name="price_predictor",
        initial_version="1.0.0",
        reference_data=[{"price": 0.15, "demand": 100} for _ in range(100)]
    )

    await pipeline.register_model(
        model_name="demand_forecaster",
        initial_version="1.0.0"
    )

    # Simulate predictions and actuals
    print("\n2. Recording predictions and actuals...")
    for i in range(20):
        pred_id = await pipeline.record_prediction(
            model_name="price_predictor",
            model_version="1.0.0",
            input_features={"hour": i % 24, "demand": 100 + i},
            prediction=0.15 + (i * 0.001)
        )

        await pipeline.record_actual(
            model_name="price_predictor",
            actual_value=0.145 + (i * 0.001),
            timestamp=datetime.utcnow(),
            prediction_id=pred_id
        )

    print(f"  Recorded 20 predictions and actuals")

    # Get model status
    print("\n3. Model status:")
    for model_name in ["price_predictor", "demand_forecaster"]:
        status = await pipeline.get_model_status(model_name)
        print(f"  {model_name}:")
        print(f"    Version: {status.current_version}")
        print(f"    Status: {status.status.value}")

    # Trigger manual retraining
    print("\n4. Triggering manual retraining...")
    trigger_event = await pipeline.trigger_retraining(
        model_name="price_predictor",
        reason="Demo retraining"
    )
    print(f"  Trigger event: {trigger_event.trigger_type}")

    # In a real scenario, the pipeline would run asynchronously
    # For demo, we just show the trigger

    print("\n" + "=" * 60)
    print("Demo complete!")
    print("\nIn production, call `await pipeline.start()` to run the")
    print("continuous learning loop with automatic trigger checking.")


if __name__ == "__main__":
    asyncio.run(demo_continuous_learning())
