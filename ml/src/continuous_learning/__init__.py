"""SHAKTI-CHAIN Continuous Learning Pipeline.

Architecture:
[Production] → [Data Lake] → [Validation] → [Training] → [Evaluation] → [Deployment]

Components:
- DataCollector: Stream predictions and actuals to data lake
- DataValidator: Schema validation, drift detection, quality checks
- RetrainingTrigger: Scheduled, performance-based, drift-based triggers
- TrainingPipeline: Orchestrated model training
- EvaluationGate: Model comparison and approval gates
- ModelDeployer: Blue-green and canary deployments
- ContinuousLearningPipeline: Unified integration of all components
"""

from .collector import (
    DataCollector,
    PredictionRecord,
    ActualRecord,
    DataPartition,
    DataLakeConfig,
    StorageBackend,
)

from .validator import (
    DataValidator,
    ValidationResult,
    DriftDetector,
    DriftReport,
    SchemaValidator,
    QualityChecker,
)

from .triggers import (
    RetrainingTrigger,
    TriggerType,
    TriggerConfig,
    TriggerEvent,
    ScheduledTrigger,
    PerformanceTrigger,
    DriftTrigger,
    StalenessTrigger,
)

from .pipeline import (
    TrainingPipeline,
    PipelineConfig,
    PipelineStage,
    PipelineRun,
    PipelineStatus,
    generate_airflow_dag,
)

from .evaluation import (
    EvaluationGate,
    EvaluationConfig,
    EvaluationResult,
    MetricComparison,
    SegmentResult,
    ShadowTest,
    ShadowTestResult,
    ApprovalStatus,
)

from .deployer import (
    ModelDeployer,
    DeploymentOrchestrator,
    DeploymentStrategy,
    DeploymentStatus,
    DeploymentRecord,
    CanaryConfig,
    CanaryStageResult,
    ModelArtifact,
    DeploymentTarget,
    RollbackReason,
    DeploymentMetrics,
    ModelRegistry,
    InMemoryModelRegistry,
    MetricsCollector,
    InMemoryMetricsCollector,
    TrafficRouter,
    InMemoryTrafficRouter,
)

from .integration import (
    ContinuousLearningPipeline,
    ContinuousLearningConfig,
    ContinuousLearningStatus,
    ModelStatus,
    create_default_pipeline,
)

__all__ = [
    # Collector
    "DataCollector",
    "PredictionRecord",
    "ActualRecord",
    "DataPartition",
    "DataLakeConfig",
    "StorageBackend",
    # Validator
    "DataValidator",
    "ValidationResult",
    "DriftDetector",
    "DriftReport",
    "SchemaValidator",
    "QualityChecker",
    # Triggers
    "RetrainingTrigger",
    "TriggerType",
    "TriggerConfig",
    "TriggerEvent",
    "ScheduledTrigger",
    "PerformanceTrigger",
    "DriftTrigger",
    "StalenessTrigger",
    # Pipeline
    "TrainingPipeline",
    "PipelineConfig",
    "PipelineStage",
    "PipelineRun",
    "PipelineStatus",
    "generate_airflow_dag",
    # Evaluation
    "EvaluationGate",
    "EvaluationConfig",
    "EvaluationResult",
    "MetricComparison",
    "SegmentResult",
    "ShadowTest",
    "ShadowTestResult",
    "ApprovalStatus",
    # Deployer
    "ModelDeployer",
    "DeploymentOrchestrator",
    "DeploymentStrategy",
    "DeploymentStatus",
    "DeploymentRecord",
    "CanaryConfig",
    "CanaryStageResult",
    "ModelArtifact",
    "DeploymentTarget",
    "RollbackReason",
    "DeploymentMetrics",
    "ModelRegistry",
    "InMemoryModelRegistry",
    "MetricsCollector",
    "InMemoryMetricsCollector",
    "TrafficRouter",
    "InMemoryTrafficRouter",
    # Integration
    "ContinuousLearningPipeline",
    "ContinuousLearningConfig",
    "ContinuousLearningStatus",
    "ModelStatus",
    "create_default_pipeline",
]
