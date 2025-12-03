"""
SHAKTI-CHAIN Continuous Learning - Model Deployment with Canary Rollout.

Handles model deployment strategies including:
- Canary rollout (gradual traffic shifting)
- Blue-green deployment
- Automatic rollback on metric degradation
"""

import asyncio
import json
import logging
import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable, Awaitable

logger = logging.getLogger(__name__)


class DeploymentStrategy(Enum):
    """Deployment strategy types."""
    DIRECT = "direct"  # Immediate full replacement
    CANARY = "canary"  # Gradual traffic shift
    BLUE_GREEN = "blue_green"  # Switch between environments
    SHADOW = "shadow"  # Run in parallel without serving


class DeploymentStatus(Enum):
    """Status of a deployment."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    CANARY_PHASE = "canary_phase"
    VALIDATING = "validating"
    COMPLETED = "completed"
    ROLLED_BACK = "rolled_back"
    FAILED = "failed"


class RollbackReason(Enum):
    """Reasons for rollback."""
    METRIC_DEGRADATION = "metric_degradation"
    ERROR_RATE_HIGH = "error_rate_high"
    LATENCY_HIGH = "latency_high"
    MANUAL = "manual"
    HEALTH_CHECK_FAILED = "health_check_failed"
    TIMEOUT = "timeout"


@dataclass
class CanaryConfig:
    """Configuration for canary deployment."""
    stages: List[float] = field(default_factory=lambda: [0.1, 0.25, 0.5, 1.0])
    stage_duration_minutes: int = 30
    min_requests_per_stage: int = 100
    success_threshold: float = 0.95
    latency_threshold_ms: float = 100.0
    metric_degradation_threshold: float = 0.05  # Max allowed degradation
    auto_rollback: bool = True

    def __post_init__(self):
        if not self.stages or self.stages[-1] != 1.0:
            self.stages = list(self.stages) + [1.0]
        self.stages = sorted(set(self.stages))


@dataclass
class DeploymentTarget:
    """Target environment for deployment."""
    name: str
    endpoint: str
    environment: str  # "production", "staging", "canary"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ModelArtifact:
    """Model artifact for deployment."""
    model_name: str
    model_version: str
    artifact_path: str
    model_type: str
    framework: str = "pytorch"
    size_bytes: int = 0
    checksum: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def compute_checksum(self) -> str:
        """Compute checksum of model artifact."""
        path = Path(self.artifact_path)
        if path.exists():
            with open(path, 'rb') as f:
                return hashlib.sha256(f.read()).hexdigest()
        return ""


@dataclass
class DeploymentMetrics:
    """Metrics collected during deployment."""
    requests_total: int = 0
    requests_success: int = 0
    requests_error: int = 0
    latency_p50_ms: float = 0.0
    latency_p95_ms: float = 0.0
    latency_p99_ms: float = 0.0
    model_metric_value: float = 0.0  # Primary model metric (e.g., MAE)
    baseline_metric_value: float = 0.0

    @property
    def success_rate(self) -> float:
        if self.requests_total == 0:
            return 1.0
        return self.requests_success / self.requests_total

    @property
    def error_rate(self) -> float:
        return 1.0 - self.success_rate

    @property
    def metric_degradation(self) -> float:
        """Calculate metric degradation compared to baseline."""
        if self.baseline_metric_value == 0:
            return 0.0
        return (self.model_metric_value - self.baseline_metric_value) / abs(self.baseline_metric_value)


@dataclass
class CanaryStageResult:
    """Result of a canary stage."""
    stage_index: int
    traffic_percentage: float
    started_at: datetime
    ended_at: Optional[datetime] = None
    metrics: DeploymentMetrics = field(default_factory=DeploymentMetrics)
    passed: bool = False
    failure_reason: Optional[str] = None


@dataclass
class DeploymentRecord:
    """Record of a deployment."""
    deployment_id: str
    model_artifact: ModelArtifact
    strategy: DeploymentStrategy
    status: DeploymentStatus
    target: DeploymentTarget
    started_at: datetime
    completed_at: Optional[datetime] = None
    current_traffic_percentage: float = 0.0
    canary_stages: List[CanaryStageResult] = field(default_factory=list)
    final_metrics: Optional[DeploymentMetrics] = None
    rollback_reason: Optional[RollbackReason] = None
    rollback_details: Optional[str] = None
    previous_version: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class MetricsCollector(ABC):
    """Abstract base class for collecting deployment metrics."""

    @abstractmethod
    async def get_metrics(
        self,
        model_version: str,
        start_time: datetime,
        end_time: datetime
    ) -> DeploymentMetrics:
        """Get metrics for a model version."""
        pass

    @abstractmethod
    async def get_baseline_metrics(
        self,
        model_name: str,
        start_time: datetime,
        end_time: datetime
    ) -> DeploymentMetrics:
        """Get baseline metrics for comparison."""
        pass


class InMemoryMetricsCollector(MetricsCollector):
    """In-memory metrics collector for testing."""

    def __init__(self):
        self._metrics: Dict[str, List[Dict]] = {}
        self._baseline_metrics: Dict[str, DeploymentMetrics] = {}

    def record_request(
        self,
        model_version: str,
        success: bool,
        latency_ms: float,
        model_metric: float = 0.0
    ):
        """Record a request metric."""
        if model_version not in self._metrics:
            self._metrics[model_version] = []

        self._metrics[model_version].append({
            "timestamp": datetime.utcnow(),
            "success": success,
            "latency_ms": latency_ms,
            "model_metric": model_metric
        })

    def set_baseline(self, model_name: str, metrics: DeploymentMetrics):
        """Set baseline metrics."""
        self._baseline_metrics[model_name] = metrics

    async def get_metrics(
        self,
        model_version: str,
        start_time: datetime,
        end_time: datetime
    ) -> DeploymentMetrics:
        """Get metrics for a model version."""
        records = self._metrics.get(model_version, [])
        filtered = [
            r for r in records
            if start_time <= r["timestamp"] <= end_time
        ]

        if not filtered:
            return DeploymentMetrics()

        latencies = sorted([r["latency_ms"] for r in filtered])
        n = len(latencies)

        return DeploymentMetrics(
            requests_total=n,
            requests_success=sum(1 for r in filtered if r["success"]),
            requests_error=sum(1 for r in filtered if not r["success"]),
            latency_p50_ms=latencies[int(n * 0.5)] if n > 0 else 0,
            latency_p95_ms=latencies[int(n * 0.95)] if n > 0 else 0,
            latency_p99_ms=latencies[int(n * 0.99)] if n > 0 else 0,
            model_metric_value=sum(r["model_metric"] for r in filtered) / n if n > 0 else 0,
            baseline_metric_value=0.0
        )

    async def get_baseline_metrics(
        self,
        model_name: str,
        start_time: datetime,
        end_time: datetime
    ) -> DeploymentMetrics:
        """Get baseline metrics."""
        return self._baseline_metrics.get(model_name, DeploymentMetrics())


class TrafficRouter(ABC):
    """Abstract base class for traffic routing."""

    @abstractmethod
    async def set_traffic_split(
        self,
        target: DeploymentTarget,
        canary_version: str,
        baseline_version: str,
        canary_percentage: float
    ) -> bool:
        """Set traffic split between versions."""
        pass

    @abstractmethod
    async def route_all_traffic(
        self,
        target: DeploymentTarget,
        version: str
    ) -> bool:
        """Route all traffic to a specific version."""
        pass

    @abstractmethod
    async def get_current_split(
        self,
        target: DeploymentTarget
    ) -> Dict[str, float]:
        """Get current traffic split."""
        pass


class InMemoryTrafficRouter(TrafficRouter):
    """In-memory traffic router for testing."""

    def __init__(self):
        self._splits: Dict[str, Dict[str, float]] = {}

    async def set_traffic_split(
        self,
        target: DeploymentTarget,
        canary_version: str,
        baseline_version: str,
        canary_percentage: float
    ) -> bool:
        """Set traffic split."""
        self._splits[target.name] = {
            canary_version: canary_percentage,
            baseline_version: 1.0 - canary_percentage
        }
        logger.info(
            f"Traffic split for {target.name}: "
            f"{canary_version}={canary_percentage:.1%}, "
            f"{baseline_version}={1-canary_percentage:.1%}"
        )
        return True

    async def route_all_traffic(
        self,
        target: DeploymentTarget,
        version: str
    ) -> bool:
        """Route all traffic to version."""
        self._splits[target.name] = {version: 1.0}
        logger.info(f"All traffic routed to {version} for {target.name}")
        return True

    async def get_current_split(
        self,
        target: DeploymentTarget
    ) -> Dict[str, float]:
        """Get current split."""
        return self._splits.get(target.name, {})


class ModelRegistry(ABC):
    """Abstract base class for model registry."""

    @abstractmethod
    async def register_model(
        self,
        artifact: ModelArtifact
    ) -> str:
        """Register a model artifact."""
        pass

    @abstractmethod
    async def get_model(
        self,
        model_name: str,
        version: Optional[str] = None
    ) -> Optional[ModelArtifact]:
        """Get model artifact (latest if version not specified)."""
        pass

    @abstractmethod
    async def get_production_version(
        self,
        model_name: str
    ) -> Optional[str]:
        """Get current production version."""
        pass

    @abstractmethod
    async def set_production_version(
        self,
        model_name: str,
        version: str
    ) -> bool:
        """Set production version."""
        pass

    @abstractmethod
    async def list_versions(
        self,
        model_name: str
    ) -> List[str]:
        """List all versions of a model."""
        pass


class InMemoryModelRegistry(ModelRegistry):
    """In-memory model registry for testing."""

    def __init__(self):
        self._models: Dict[str, Dict[str, ModelArtifact]] = {}
        self._production: Dict[str, str] = {}

    async def register_model(
        self,
        artifact: ModelArtifact
    ) -> str:
        """Register model."""
        if artifact.model_name not in self._models:
            self._models[artifact.model_name] = {}

        self._models[artifact.model_name][artifact.model_version] = artifact
        logger.info(f"Registered model {artifact.model_name} v{artifact.model_version}")
        return artifact.model_version

    async def get_model(
        self,
        model_name: str,
        version: Optional[str] = None
    ) -> Optional[ModelArtifact]:
        """Get model."""
        if model_name not in self._models:
            return None

        if version:
            return self._models[model_name].get(version)

        # Get latest
        versions = list(self._models[model_name].keys())
        if not versions:
            return None
        return self._models[model_name][sorted(versions)[-1]]

    async def get_production_version(
        self,
        model_name: str
    ) -> Optional[str]:
        """Get production version."""
        return self._production.get(model_name)

    async def set_production_version(
        self,
        model_name: str,
        version: str
    ) -> bool:
        """Set production version."""
        self._production[model_name] = version
        logger.info(f"Production version for {model_name} set to {version}")
        return True

    async def list_versions(
        self,
        model_name: str
    ) -> List[str]:
        """List versions."""
        if model_name not in self._models:
            return []
        return sorted(self._models[model_name].keys())


class ModelDeployer:
    """
    Model deployer with canary rollout support.

    Handles:
    - Canary deployment with gradual traffic shifting
    - Blue-green deployment
    - Automatic rollback on metric degradation
    - Deployment tracking and history
    """

    def __init__(
        self,
        model_registry: ModelRegistry,
        metrics_collector: MetricsCollector,
        traffic_router: TrafficRouter,
        storage_path: str = "./deployments",
        default_canary_config: Optional[CanaryConfig] = None
    ):
        self.registry = model_registry
        self.metrics = metrics_collector
        self.router = traffic_router
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.default_canary_config = default_canary_config or CanaryConfig()

        self._active_deployments: Dict[str, DeploymentRecord] = {}
        self._deployment_history: List[DeploymentRecord] = []
        self._rollback_callbacks: List[Callable[[DeploymentRecord], Awaitable[None]]] = []
        self._deployment_callbacks: List[Callable[[DeploymentRecord], Awaitable[None]]] = []

    def add_rollback_callback(
        self,
        callback: Callable[[DeploymentRecord], Awaitable[None]]
    ):
        """Add callback for rollback events."""
        self._rollback_callbacks.append(callback)

    def add_deployment_callback(
        self,
        callback: Callable[[DeploymentRecord], Awaitable[None]]
    ):
        """Add callback for deployment completion events."""
        self._deployment_callbacks.append(callback)

    async def deploy(
        self,
        model_artifact: ModelArtifact,
        target: DeploymentTarget,
        strategy: DeploymentStrategy = DeploymentStrategy.CANARY,
        canary_config: Optional[CanaryConfig] = None,
        wait_for_completion: bool = True
    ) -> DeploymentRecord:
        """
        Deploy a model with specified strategy.

        Args:
            model_artifact: Model to deploy
            target: Deployment target
            strategy: Deployment strategy
            canary_config: Canary configuration (for canary strategy)
            wait_for_completion: Whether to wait for deployment to complete

        Returns:
            DeploymentRecord with deployment status
        """
        # Register model if not already registered
        await self.registry.register_model(model_artifact)

        # Get current production version
        previous_version = await self.registry.get_production_version(model_artifact.model_name)

        # Create deployment record
        deployment_id = f"deploy-{model_artifact.model_name}-{model_artifact.model_version}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

        record = DeploymentRecord(
            deployment_id=deployment_id,
            model_artifact=model_artifact,
            strategy=strategy,
            status=DeploymentStatus.PENDING,
            target=target,
            started_at=datetime.utcnow(),
            previous_version=previous_version
        )

        self._active_deployments[deployment_id] = record

        logger.info(
            f"Starting {strategy.value} deployment: {deployment_id} "
            f"(model={model_artifact.model_name}, version={model_artifact.model_version})"
        )

        try:
            if strategy == DeploymentStrategy.DIRECT:
                await self._deploy_direct(record)
            elif strategy == DeploymentStrategy.CANARY:
                config = canary_config or self.default_canary_config
                if wait_for_completion:
                    await self._deploy_canary(record, config)
                else:
                    # Start canary deployment in background
                    asyncio.create_task(self._deploy_canary(record, config))
            elif strategy == DeploymentStrategy.BLUE_GREEN:
                await self._deploy_blue_green(record)
            elif strategy == DeploymentStrategy.SHADOW:
                await self._deploy_shadow(record)
        except Exception as e:
            record.status = DeploymentStatus.FAILED
            record.completed_at = datetime.utcnow()
            record.metadata["error"] = str(e)
            logger.error(f"Deployment {deployment_id} failed: {e}")

        return record

    async def _deploy_direct(self, record: DeploymentRecord):
        """Direct deployment - immediate full traffic switch."""
        record.status = DeploymentStatus.IN_PROGRESS

        # Route all traffic to new version
        success = await self.router.route_all_traffic(
            record.target,
            record.model_artifact.model_version
        )

        if success:
            record.current_traffic_percentage = 1.0
            record.status = DeploymentStatus.COMPLETED
            record.completed_at = datetime.utcnow()

            # Update production version
            await self.registry.set_production_version(
                record.model_artifact.model_name,
                record.model_artifact.model_version
            )

            await self._notify_deployment_complete(record)
            logger.info(f"Direct deployment completed: {record.deployment_id}")
        else:
            record.status = DeploymentStatus.FAILED
            record.completed_at = datetime.utcnow()
            logger.error(f"Direct deployment failed: {record.deployment_id}")

    async def _deploy_canary(self, record: DeploymentRecord, config: CanaryConfig):
        """Canary deployment with gradual traffic shifting."""
        record.status = DeploymentStatus.CANARY_PHASE

        baseline_version = record.previous_version
        canary_version = record.model_artifact.model_version

        if not baseline_version:
            logger.warning("No baseline version, using direct deployment")
            await self._deploy_direct(record)
            return

        for stage_idx, traffic_pct in enumerate(config.stages):
            stage_result = CanaryStageResult(
                stage_index=stage_idx,
                traffic_percentage=traffic_pct,
                started_at=datetime.utcnow()
            )
            record.canary_stages.append(stage_result)
            record.current_traffic_percentage = traffic_pct

            logger.info(
                f"Canary stage {stage_idx + 1}/{len(config.stages)}: "
                f"{traffic_pct:.0%} traffic to {canary_version}"
            )

            # Set traffic split
            await self.router.set_traffic_split(
                record.target,
                canary_version,
                baseline_version,
                traffic_pct
            )

            # Wait for stage duration
            stage_end = datetime.utcnow() + timedelta(minutes=config.stage_duration_minutes)

            while datetime.utcnow() < stage_end:
                await asyncio.sleep(60)  # Check every minute

                # Get metrics
                metrics = await self.metrics.get_metrics(
                    canary_version,
                    stage_result.started_at,
                    datetime.utcnow()
                )

                baseline_metrics = await self.metrics.get_baseline_metrics(
                    record.model_artifact.model_name,
                    stage_result.started_at,
                    datetime.utcnow()
                )

                metrics.baseline_metric_value = baseline_metrics.model_metric_value
                stage_result.metrics = metrics

                # Check if we have enough requests
                if metrics.requests_total < config.min_requests_per_stage:
                    continue

                # Check for rollback conditions
                should_rollback, reason = self._check_rollback_conditions(
                    metrics, config
                )

                if should_rollback and config.auto_rollback:
                    stage_result.passed = False
                    stage_result.failure_reason = reason
                    stage_result.ended_at = datetime.utcnow()

                    await self._rollback(record, RollbackReason.METRIC_DEGRADATION, reason)
                    return

            # Stage completed successfully
            stage_result.passed = True
            stage_result.ended_at = datetime.utcnow()

            # Final stage check
            if traffic_pct == 1.0:
                break

        # All stages passed - deployment complete
        record.status = DeploymentStatus.COMPLETED
        record.completed_at = datetime.utcnow()
        record.current_traffic_percentage = 1.0

        # Update production version
        await self.registry.set_production_version(
            record.model_artifact.model_name,
            record.model_artifact.model_version
        )

        # Get final metrics
        record.final_metrics = await self.metrics.get_metrics(
            canary_version,
            record.started_at,
            datetime.utcnow()
        )

        await self._notify_deployment_complete(record)
        logger.info(f"Canary deployment completed: {record.deployment_id}")

    async def _deploy_blue_green(self, record: DeploymentRecord):
        """Blue-green deployment with instant switch."""
        record.status = DeploymentStatus.IN_PROGRESS

        # In blue-green, we deploy to inactive environment first
        # then switch all traffic instantly

        # For simplicity, treat similar to direct but with validation
        record.status = DeploymentStatus.VALIDATING

        # Run validation/smoke tests (simulated)
        await asyncio.sleep(1)

        # Switch traffic
        success = await self.router.route_all_traffic(
            record.target,
            record.model_artifact.model_version
        )

        if success:
            record.current_traffic_percentage = 1.0
            record.status = DeploymentStatus.COMPLETED
            record.completed_at = datetime.utcnow()

            await self.registry.set_production_version(
                record.model_artifact.model_name,
                record.model_artifact.model_version
            )

            await self._notify_deployment_complete(record)
            logger.info(f"Blue-green deployment completed: {record.deployment_id}")
        else:
            record.status = DeploymentStatus.FAILED
            record.completed_at = datetime.utcnow()

    async def _deploy_shadow(self, record: DeploymentRecord):
        """Shadow deployment - run in parallel without serving."""
        record.status = DeploymentStatus.IN_PROGRESS

        # Shadow deployment doesn't change traffic
        # Just marks the model as deployed for shadow testing
        record.current_traffic_percentage = 0.0
        record.status = DeploymentStatus.COMPLETED
        record.completed_at = datetime.utcnow()
        record.metadata["shadow_mode"] = True

        logger.info(f"Shadow deployment completed: {record.deployment_id}")

    def _check_rollback_conditions(
        self,
        metrics: DeploymentMetrics,
        config: CanaryConfig
    ) -> tuple[bool, str]:
        """Check if rollback conditions are met."""
        # Check success rate
        if metrics.success_rate < config.success_threshold:
            return True, f"Success rate {metrics.success_rate:.2%} below threshold {config.success_threshold:.2%}"

        # Check latency
        if metrics.latency_p95_ms > config.latency_threshold_ms:
            return True, f"P95 latency {metrics.latency_p95_ms:.1f}ms exceeds threshold {config.latency_threshold_ms:.1f}ms"

        # Check metric degradation
        if metrics.metric_degradation > config.metric_degradation_threshold:
            return True, f"Metric degradation {metrics.metric_degradation:.2%} exceeds threshold {config.metric_degradation_threshold:.2%}"

        return False, ""

    async def _rollback(
        self,
        record: DeploymentRecord,
        reason: RollbackReason,
        details: str
    ):
        """Rollback a deployment."""
        logger.warning(
            f"Rolling back deployment {record.deployment_id}: {reason.value} - {details}"
        )

        record.status = DeploymentStatus.ROLLED_BACK
        record.rollback_reason = reason
        record.rollback_details = details
        record.completed_at = datetime.utcnow()

        # Restore previous version
        if record.previous_version:
            await self.router.route_all_traffic(
                record.target,
                record.previous_version
            )
            record.current_traffic_percentage = 0.0

        # Notify callbacks
        for callback in self._rollback_callbacks:
            try:
                await callback(record)
            except Exception as e:
                logger.error(f"Rollback callback error: {e}")

        self._save_deployment_record(record)

    async def rollback_manual(
        self,
        deployment_id: str,
        reason: str = "Manual rollback"
    ) -> Optional[DeploymentRecord]:
        """Manually rollback a deployment."""
        record = self._active_deployments.get(deployment_id)
        if not record:
            # Check history
            for r in self._deployment_history:
                if r.deployment_id == deployment_id:
                    record = r
                    break

        if not record:
            logger.error(f"Deployment not found: {deployment_id}")
            return None

        if record.status == DeploymentStatus.ROLLED_BACK:
            logger.warning(f"Deployment already rolled back: {deployment_id}")
            return record

        await self._rollback(record, RollbackReason.MANUAL, reason)
        return record

    async def _notify_deployment_complete(self, record: DeploymentRecord):
        """Notify callbacks of deployment completion."""
        for callback in self._deployment_callbacks:
            try:
                await callback(record)
            except Exception as e:
                logger.error(f"Deployment callback error: {e}")

        self._save_deployment_record(record)

    def _save_deployment_record(self, record: DeploymentRecord):
        """Save deployment record to storage."""
        # Move from active to history
        if record.deployment_id in self._active_deployments:
            del self._active_deployments[record.deployment_id]
        self._deployment_history.append(record)

        # Save to file
        record_path = self.storage_path / f"{record.deployment_id}.json"
        record_data = {
            "deployment_id": record.deployment_id,
            "model_name": record.model_artifact.model_name,
            "model_version": record.model_artifact.model_version,
            "strategy": record.strategy.value,
            "status": record.status.value,
            "target": record.target.name,
            "started_at": record.started_at.isoformat(),
            "completed_at": record.completed_at.isoformat() if record.completed_at else None,
            "previous_version": record.previous_version,
            "rollback_reason": record.rollback_reason.value if record.rollback_reason else None,
            "rollback_details": record.rollback_details,
            "canary_stages": [
                {
                    "stage_index": s.stage_index,
                    "traffic_percentage": s.traffic_percentage,
                    "passed": s.passed,
                    "failure_reason": s.failure_reason
                }
                for s in record.canary_stages
            ]
        }

        with open(record_path, 'w') as f:
            json.dump(record_data, f, indent=2)

    async def get_deployment_status(
        self,
        deployment_id: str
    ) -> Optional[DeploymentRecord]:
        """Get status of a deployment."""
        if deployment_id in self._active_deployments:
            return self._active_deployments[deployment_id]

        for record in self._deployment_history:
            if record.deployment_id == deployment_id:
                return record

        return None

    async def get_active_deployments(self) -> List[DeploymentRecord]:
        """Get all active deployments."""
        return list(self._active_deployments.values())

    async def get_deployment_history(
        self,
        model_name: Optional[str] = None,
        limit: int = 100
    ) -> List[DeploymentRecord]:
        """Get deployment history."""
        history = self._deployment_history

        if model_name:
            history = [
                r for r in history
                if r.model_artifact.model_name == model_name
            ]

        return sorted(
            history,
            key=lambda r: r.started_at,
            reverse=True
        )[:limit]


class DeploymentOrchestrator:
    """
    Orchestrates the full deployment workflow.

    Coordinates:
    - Model registration
    - Evaluation gates
    - Deployment execution
    - Monitoring and alerting
    """

    def __init__(
        self,
        deployer: ModelDeployer,
        notification_webhook: Optional[str] = None
    ):
        self.deployer = deployer
        self.notification_webhook = notification_webhook

        # Add rollback notification
        self.deployer.add_rollback_callback(self._on_rollback)
        self.deployer.add_deployment_callback(self._on_deployment_complete)

    async def deploy_with_approval(
        self,
        model_artifact: ModelArtifact,
        target: DeploymentTarget,
        strategy: DeploymentStrategy = DeploymentStrategy.CANARY,
        require_approval: bool = True,
        approvers: Optional[List[str]] = None
    ) -> DeploymentRecord:
        """
        Deploy with optional human approval.

        Args:
            model_artifact: Model to deploy
            target: Deployment target
            strategy: Deployment strategy
            require_approval: Whether to require human approval
            approvers: List of approver emails/usernames

        Returns:
            DeploymentRecord
        """
        if require_approval:
            logger.info(
                f"Deployment requires approval from: {approvers or ['any approver']}"
            )
            # In a real implementation, this would:
            # 1. Send notification to approvers
            # 2. Wait for approval via API/webhook
            # 3. Proceed or reject based on response

            # For now, we auto-approve after logging
            logger.info("Auto-approving deployment (approval system not configured)")

        return await self.deployer.deploy(
            model_artifact=model_artifact,
            target=target,
            strategy=strategy
        )

    async def promote_to_production(
        self,
        model_name: str,
        model_version: str,
        canary_config: Optional[CanaryConfig] = None
    ) -> DeploymentRecord:
        """
        Promote a model version to production.

        Args:
            model_name: Name of the model
            model_version: Version to promote
            canary_config: Canary configuration

        Returns:
            DeploymentRecord
        """
        # Get model artifact
        artifact = await self.deployer.registry.get_model(model_name, model_version)
        if not artifact:
            raise ValueError(f"Model not found: {model_name} v{model_version}")

        # Create production target
        target = DeploymentTarget(
            name=f"{model_name}-production",
            endpoint=f"https://api.shakti-chain.io/models/{model_name}",
            environment="production"
        )

        # Deploy with canary
        config = canary_config or CanaryConfig(
            stages=[0.1, 0.5, 1.0],
            stage_duration_minutes=60,
            min_requests_per_stage=1000
        )

        return await self.deployer.deploy(
            model_artifact=artifact,
            target=target,
            strategy=DeploymentStrategy.CANARY,
            canary_config=config
        )

    async def _on_rollback(self, record: DeploymentRecord):
        """Handle rollback event."""
        logger.warning(
            f"ROLLBACK: {record.model_artifact.model_name} "
            f"v{record.model_artifact.model_version} "
            f"-> v{record.previous_version}"
        )

        if self.notification_webhook:
            await self._send_notification({
                "type": "rollback",
                "deployment_id": record.deployment_id,
                "model_name": record.model_artifact.model_name,
                "version": record.model_artifact.model_version,
                "previous_version": record.previous_version,
                "reason": record.rollback_reason.value if record.rollback_reason else "unknown",
                "details": record.rollback_details
            })

    async def _on_deployment_complete(self, record: DeploymentRecord):
        """Handle deployment completion."""
        logger.info(
            f"DEPLOYMENT COMPLETE: {record.model_artifact.model_name} "
            f"v{record.model_artifact.model_version}"
        )

        if self.notification_webhook:
            await self._send_notification({
                "type": "deployment_complete",
                "deployment_id": record.deployment_id,
                "model_name": record.model_artifact.model_name,
                "version": record.model_artifact.model_version,
                "status": record.status.value,
                "duration_minutes": (
                    (record.completed_at - record.started_at).total_seconds() / 60
                    if record.completed_at else 0
                )
            })

    async def _send_notification(self, payload: Dict[str, Any]):
        """Send notification webhook."""
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                await session.post(
                    self.notification_webhook,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=10)
                )
        except ImportError:
            logger.warning("aiohttp not available for notifications")
        except Exception as e:
            logger.error(f"Failed to send notification: {e}")


async def demo_canary_deployment():
    """Demonstrate canary deployment workflow."""
    print("=" * 60)
    print("SHAKTI-CHAIN Canary Deployment Demo")
    print("=" * 60)

    # Create components
    registry = InMemoryModelRegistry()
    metrics = InMemoryMetricsCollector()
    router = InMemoryTrafficRouter()

    deployer = ModelDeployer(
        model_registry=registry,
        metrics_collector=metrics,
        traffic_router=router,
        default_canary_config=CanaryConfig(
            stages=[0.1, 0.5, 1.0],
            stage_duration_minutes=1,  # Short for demo
            min_requests_per_stage=10
        )
    )

    # Register baseline model
    baseline = ModelArtifact(
        model_name="price_predictor",
        model_version="1.0.0",
        artifact_path="/models/price_predictor_v1.pt",
        model_type="regression"
    )
    await registry.register_model(baseline)
    await registry.set_production_version("price_predictor", "1.0.0")

    # Set baseline metrics
    metrics.set_baseline("price_predictor", DeploymentMetrics(
        requests_total=10000,
        requests_success=9800,
        latency_p95_ms=45.0,
        model_metric_value=0.05  # MAE
    ))

    # Create candidate model
    candidate = ModelArtifact(
        model_name="price_predictor",
        model_version="1.1.0",
        artifact_path="/models/price_predictor_v1.1.pt",
        model_type="regression"
    )

    # Create target
    target = DeploymentTarget(
        name="price-predictor-prod",
        endpoint="https://api.shakti-chain.io/models/price_predictor",
        environment="production"
    )

    print(f"\nDeploying {candidate.model_name} v{candidate.model_version}")
    print(f"Baseline: v{baseline.model_version}")
    print(f"Strategy: Canary (10% -> 50% -> 100%)")
    print("-" * 60)

    # Simulate metrics during deployment
    async def simulate_metrics():
        for i in range(50):
            await asyncio.sleep(0.1)
            metrics.record_request(
                candidate.model_version,
                success=True,
                latency_ms=40 + (i % 10),
                model_metric=0.048  # Slightly better than baseline
            )

    # Start metrics simulation
    metrics_task = asyncio.create_task(simulate_metrics())

    # Deploy
    record = await deployer.deploy(
        model_artifact=candidate,
        target=target,
        strategy=DeploymentStrategy.CANARY,
        canary_config=CanaryConfig(
            stages=[0.1, 0.5, 1.0],
            stage_duration_minutes=0.1,  # Very short for demo
            min_requests_per_stage=5
        )
    )

    await metrics_task

    print(f"\nDeployment Status: {record.status.value}")
    print(f"Final Traffic: {record.current_traffic_percentage:.0%}")

    if record.canary_stages:
        print("\nCanary Stages:")
        for stage in record.canary_stages:
            status = "✓" if stage.passed else "✗"
            print(f"  {status} Stage {stage.stage_index + 1}: {stage.traffic_percentage:.0%} traffic")
            if stage.failure_reason:
                print(f"      Reason: {stage.failure_reason}")

    # Check production version
    prod_version = await registry.get_production_version("price_predictor")
    print(f"\nProduction Version: {prod_version}")

    print("\n" + "=" * 60)
    print("Demo complete!")


if __name__ == "__main__":
    asyncio.run(demo_canary_deployment())
