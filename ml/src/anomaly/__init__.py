"""Anomaly Detection module for SHAKTI-CHAIN platform.

Detects various types of anomalies:
- Trading anomalies (wash trading, manipulation, spoofing)
- Delivery anomalies (false claims, non-delivery)
- Account anomalies (Sybil attacks, reputation manipulation)

Models:
- Isolation Forest for point anomalies
- LSTM Autoencoder for sequential patterns
- Graph Neural Network for network/collusion detection

Features:
- Trading, delivery, account, and graph feature extractors

Alert System:
- Tiered alerts (Critical > 0.9, High > 0.8, Medium > 0.6, Low > 0.4)
- Multiple handlers (logging, file, webhook, queue)
- Alert persistence and trending

Blockchain Integration:
- Real-time event streaming
- Event parsing and normalization
- Live anomaly monitoring
"""

from .detector import (
    AnomalyDetector,
    AnomalyScore,
    AnomalyType,
    AlertLevel,
    AnomalyReport,
)

from .models import (
    IsolationForestDetector,
    LSTMAutoencoder,
    GraphAnomalyDetector,
)

from .features import (
    TradeFeatures,
    DeliveryFeatures,
    AccountFeatures,
    GraphFeatures,
    TradingFeatureExtractor,
    DeliveryFeatureExtractor,
    AccountFeatureExtractor,
    GraphFeatureExtractor,
)

from .alerts import (
    Alert,
    AlertRule,
    AlertSeverity,
    AlertStatus,
    AlertCategory,
    AlertHandler,
    LoggingHandler,
    FileHandler,
    WebhookHandler,
    QueueHandler,
    AlertStore,
    AlertSystem,
)

from .blockchain import (
    BlockchainEvent,
    BlockchainEventType,
    EventFilter,
    EventParser,
    BlockchainEventStream,
    BlockchainAnomalyMonitor,
)

__all__ = [
    # Core detector
    "AnomalyDetector",
    "AnomalyScore",
    "AnomalyType",
    "AlertLevel",
    "AnomalyReport",
    # Models
    "IsolationForestDetector",
    "LSTMAutoencoder",
    "GraphAnomalyDetector",
    # Feature dataclasses
    "TradeFeatures",
    "DeliveryFeatures",
    "AccountFeatures",
    "GraphFeatures",
    # Feature extractors
    "TradingFeatureExtractor",
    "DeliveryFeatureExtractor",
    "AccountFeatureExtractor",
    "GraphFeatureExtractor",
    # Alert types
    "Alert",
    "AlertRule",
    "AlertSeverity",
    "AlertStatus",
    "AlertCategory",
    # Alert handlers
    "AlertHandler",
    "LoggingHandler",
    "FileHandler",
    "WebhookHandler",
    "QueueHandler",
    # Alert system
    "AlertStore",
    "AlertSystem",
    # Blockchain integration
    "BlockchainEvent",
    "BlockchainEventType",
    "EventFilter",
    "EventParser",
    "BlockchainEventStream",
    "BlockchainAnomalyMonitor",
]
