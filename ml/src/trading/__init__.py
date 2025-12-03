"""SHAKTI-CHAIN trading agent blockchain integration.

Components:
- BlockchainTradingExecutor: Execute trades on smart contracts
- TradingAgent: RL-based trading decisions
- TransactionMonitor: Track and alert on transactions
- RiskManager: Safety limits and controls
- PnLTracker: Profit/loss tracking
"""

from .executor import (
    BlockchainTradingExecutor,
    ExecutorConfig,
    TradingAction,
    ActionType,
    TransactionResult,
    TransactionStatus,
)

from .agent import (
    TradingAgent,
    AgentConfig,
    AgentState,
    TradingDecision,
)

from .risk import (
    RiskManager,
    RiskConfig,
    RiskLimits,
    RiskCheck,
    RiskViolation,
)

from .monitor import (
    TransactionMonitor,
    TransactionRecord,
    MonitorConfig,
)

from .pnl import (
    PnLTracker,
    PnLReport,
    TradeRecord,
)

__all__ = [
    # Executor
    "BlockchainTradingExecutor",
    "ExecutorConfig",
    "TradingAction",
    "ActionType",
    "TransactionResult",
    "TransactionStatus",
    # Agent
    "TradingAgent",
    "AgentConfig",
    "AgentState",
    "TradingDecision",
    # Risk
    "RiskManager",
    "RiskConfig",
    "RiskLimits",
    "RiskCheck",
    "RiskViolation",
    # Monitor
    "TransactionMonitor",
    "TransactionRecord",
    "MonitorConfig",
    # P&L
    "PnLTracker",
    "PnLReport",
    "TradeRecord",
]
