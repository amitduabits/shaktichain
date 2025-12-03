"""Real-time feature pipeline for SHAKTI-CHAIN.

Architecture:
[Blockchain Events] → [Redis Streams] → [Feature Processor] → [Feature Store] → [Model Service]
[Grid API] → [Collector] →

Components:
- Event Ingestion: Blockchain subscriptions, Grid API polling
- Streaming Features: Rolling statistics, VWAP, order book imbalance
- Feature Store: Redis with TTL, historical features
- Feature Serving: Low-latency feature retrieval for inference
- Orchestrator: Pipeline coordination and lifecycle management
"""

from .events import (
    Event,
    EventType,
    TradeEvent,
    PriceEvent,
    AuctionEvent,
    GridEvent,
    WeatherEvent,
    EventParser,
)

from .ingestion import (
    BlockchainIngester,
    GridAPIIngester,
    EventQueue,
    RedisEventQueue,
)

from .processor import (
    StreamingFeatureProcessor,
    RollingStatistics,
    VWAPCalculator,
    OrderBookImbalance,
)

from .store import (
    FeatureStore,
    RedisFeatureStore,
    InMemoryFeatureStore,
    FeatureKey,
    FeatureValue,
    FeatureCategory,
    FeatureStoreWriter,
)

from .refresher import (
    FeatureRefresher,
    RefreshSchedule,
    RefreshTrigger,
    RefreshThreshold,
    ModelTriggerHandler,
)

from .serving import (
    FeatureServer,
    FeatureVector,
    FeatureSpec,
    FeatureSet,
    FeatureStatus,
    FeatureClient,
)

from .orchestrator import (
    FeaturePipelineOrchestrator,
    PipelineConfig,
    run_pipeline,
)

__all__ = [
    # Events
    "Event",
    "EventType",
    "TradeEvent",
    "PriceEvent",
    "AuctionEvent",
    "GridEvent",
    "WeatherEvent",
    "EventParser",
    # Ingestion
    "BlockchainIngester",
    "GridAPIIngester",
    "EventQueue",
    "RedisEventQueue",
    # Processing
    "StreamingFeatureProcessor",
    "RollingStatistics",
    "VWAPCalculator",
    "OrderBookImbalance",
    # Store
    "FeatureStore",
    "RedisFeatureStore",
    "InMemoryFeatureStore",
    "FeatureKey",
    "FeatureValue",
    "FeatureCategory",
    "FeatureStoreWriter",
    # Refresher
    "FeatureRefresher",
    "RefreshSchedule",
    "RefreshTrigger",
    "RefreshThreshold",
    "ModelTriggerHandler",
    # Serving
    "FeatureServer",
    "FeatureVector",
    "FeatureSpec",
    "FeatureSet",
    "FeatureStatus",
    "FeatureClient",
    # Orchestrator
    "FeaturePipelineOrchestrator",
    "PipelineConfig",
    "run_pipeline",
]
