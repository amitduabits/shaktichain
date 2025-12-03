"""SHAKTI-CHAIN blockchain integration for ML pipeline.

Components:
- SubgraphClient: WebSocket subscriptions to The Graph
- BlockchainEventProcessor: Event processing and feature extraction
- HistoricalSync: Historical data synchronization
- OracleSubscriber: Price and grid oracle data
- ReliabilityLayer: Retry, DLQ, checkpoints
- BlockchainIntegration: Unified integration interface
"""

from .subgraph import (
    SubgraphClient,
    SubgraphConfig,
    GraphQLQuery,
    SubscriptionType,
)

from .processor import (
    BlockchainEventProcessor,
    TradeProcessor,
    AuctionProcessor,
    OracleProcessor,
    ProcessedEvent,
)

from .sync import (
    HistoricalSync,
    SyncCursor,
    SyncStatus,
    SyncProgress,
    CursorStorage,
)

from .oracles import (
    OracleSubscriber,
    PriceOracleClient,
    GridStatusClient,
    OracleUpdate,
    OracleType,
)

from .reliability import (
    ReliabilityLayer,
    RetryPolicy,
    RetryStrategy,
    DeadLetterQueue,
    DeadLetterItem,
    Checkpoint,
    CheckpointManager,
    CircuitBreaker,
)

from .monitor import (
    SyncMonitor,
    SyncAlert,
    SyncMetrics,
    AlertSeverity,
    AlertType,
    AlertHandler,
    SlackAlertHandler,
)

from .integration import (
    BlockchainIntegration,
    BlockchainIntegrationConfig,
    run_integration,
)

__all__ = [
    # Subgraph
    "SubgraphClient",
    "SubgraphConfig",
    "GraphQLQuery",
    "SubscriptionType",
    # Processor
    "BlockchainEventProcessor",
    "TradeProcessor",
    "AuctionProcessor",
    "OracleProcessor",
    "ProcessedEvent",
    # Sync
    "HistoricalSync",
    "SyncCursor",
    "SyncStatus",
    "SyncProgress",
    "CursorStorage",
    # Oracles
    "OracleSubscriber",
    "PriceOracleClient",
    "GridStatusClient",
    "OracleUpdate",
    "OracleType",
    # Reliability
    "ReliabilityLayer",
    "RetryPolicy",
    "RetryStrategy",
    "DeadLetterQueue",
    "DeadLetterItem",
    "Checkpoint",
    "CheckpointManager",
    "CircuitBreaker",
    # Monitor
    "SyncMonitor",
    "SyncAlert",
    "SyncMetrics",
    "AlertSeverity",
    "AlertType",
    "AlertHandler",
    "SlackAlertHandler",
    # Integration
    "BlockchainIntegration",
    "BlockchainIntegrationConfig",
    "run_integration",
]
