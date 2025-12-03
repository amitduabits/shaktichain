# Blockchain Integration Guide for SHAKTI-CHAIN ML

## Overview

This document specifies the integration points between the SHAKTI-CHAIN ML system and the blockchain layer. It serves as the handoff documentation for the blockchain team to understand ML requirements and implement the necessary smart contracts and event infrastructure.

## Table of Contents

1. [Integration Architecture](#integration-architecture)
2. [Smart Contract Requirements](#smart-contract-requirements)
3. [Event Specifications](#event-specifications)
4. [Data Format Standards](#data-format-standards)
5. [SLA Requirements](#sla-requirements)
6. [Testing & Mocks](#testing--mocks)
7. [Security Considerations](#security-considerations)
8. [Monitoring & Alerts](#monitoring--alerts)

## Integration Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                      SHAKTI-CHAIN SYSTEM                          │
└──────────────────────────────────────────────────────────────────┘

┌─────────────────────────┐              ┌──────────────────────────┐
│      ML Layer           │              │   Blockchain Layer       │
│                         │              │                          │
│  ┌──────────────────┐   │              │  ┌────────────────────┐  │
│  │ Trading Agent    │───┼──────────────┼─→│ TradeExecutor.sol  │  │
│  │ (PPO Policy)     │   │  Submit      │  │ (Smart Contract)   │  │
│  └──────────────────┘   │  Trade       │  └────────────────────┘  │
│           ↑             │              │           │              │
│           │             │              │           │ Emit Event   │
│           │ State       │              │           ↓              │
│           │ Update      │              │  ┌────────────────────┐  │
│  ┌──────────────────┐   │              │  │  Event Stream      │  │
│  │ Event Processor  │←──┼──────────────┼──│  (WebSocket/HTTP)  │  │
│  └──────────────────┘   │  Listen      │  └────────────────────┘  │
│           │             │  Events      │                          │
│           ↓             │              │  ┌────────────────────┐  │
│  ┌──────────────────┐   │              │  │  Grid Events       │  │
│  │ State Store      │   │              │  │  (Smart Contract)  │  │
│  │ (Redis/DB)       │   │              │  └────────────────────┘  │
│  └──────────────────┘   │              │                          │
│                         │              │                          │
│  ┌──────────────────┐   │              │  ┌────────────────────┐  │
│  │ Anomaly Detector │───┼──────────────┼─→│ AnomalyRegistry    │  │
│  └──────────────────┘   │  Report      │  │ (Smart Contract)   │  │
│                         │  Anomaly     │  └────────────────────┘  │
└─────────────────────────┘              └──────────────────────────┘

Communication Protocol:
- ML → Blockchain: JSON-RPC 2.0 (eth_sendTransaction)
- Blockchain → ML: WebSocket (eth_subscribe) or HTTP polling
```

## Smart Contract Requirements

### 1. TradeExecutor Contract

**Purpose**: Execute V2G energy trades submitted by ML trading agent

**Interface**:

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

interface ITradeExecutor {
    /// @notice Trade types
    enum TradeType {
        HOLD,       // 0: No action
        CHARGE,     // 1: Buy energy from grid
        DISCHARGE   // 2: Sell energy to grid
    }

    /// @notice Trade status
    enum TradeStatus {
        PENDING,    // 0: Submitted but not executed
        EXECUTED,   // 1: Successfully executed
        FAILED,     // 2: Execution failed
        CANCELLED   // 3: Cancelled by user/risk system
    }

    /// @notice Trade struct
    /// @dev All monetary values scaled by 1e18 (Wei-like precision)
    struct Trade {
        address trader;           // EV owner/agent address
        TradeType tradeType;      // CHARGE or DISCHARGE
        uint256 amountKWh;        // Energy amount (kWh * 1e18)
        uint256 pricePerKWh;      // Price in INR (INR/kWh * 1e18)
        uint256 timestamp;        // Block timestamp
        uint256 batterySOC;       // State of charge (0-100, scaled by 1e18)
        TradeStatus status;       // Current status
        bytes32 mlPredictionHash; // Hash of ML prediction (for audit)
    }

    /// @notice Submit a trade for execution
    /// @param trade Trade details
    /// @return tradeId Unique identifier for this trade
    function submitTrade(Trade calldata trade) external returns (uint256 tradeId);

    /// @notice Execute a pending trade
    /// @param tradeId Trade to execute
    function executeTrade(uint256 tradeId) external;

    /// @notice Cancel a pending trade
    /// @param tradeId Trade to cancel
    /// @param reason Cancellation reason
    function cancelTrade(uint256 tradeId, string calldata reason) external;

    /// @notice Get trade details
    /// @param tradeId Trade identifier
    /// @return trade Trade struct
    function getTrade(uint256 tradeId) external view returns (Trade memory trade);

    /// @notice Get all trades for a trader
    /// @param trader Trader address
    /// @return trades Array of trades
    function getTradesByTrader(address trader) external view returns (Trade[] memory trades);

    /// @notice Get trades in time range
    /// @param startTime Start timestamp
    /// @param endTime End timestamp
    /// @return trades Array of trades
    function getTradesByTimeRange(uint256 startTime, uint256 endTime)
        external
        view
        returns (Trade[] memory trades);

    /// Events
    event TradeSubmitted(
        uint256 indexed tradeId,
        address indexed trader,
        TradeType tradeType,
        uint256 amountKWh,
        uint256 pricePerKWh,
        uint256 timestamp
    );

    event TradeExecuted(
        uint256 indexed tradeId,
        address indexed trader,
        TradeType tradeType,
        uint256 amountKWh,
        uint256 totalValue,
        uint256 timestamp
    );

    event TradeFailed(
        uint256 indexed tradeId,
        address indexed trader,
        string reason,
        uint256 timestamp
    );

    event TradeCancelled(
        uint256 indexed tradeId,
        address indexed trader,
        string reason,
        uint256 timestamp
    );
}
```

### 2. GridEvents Contract

**Purpose**: Emit grid-level events that ML needs to process

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

interface IGridEvents {
    /// @notice Grid event types
    enum EventType {
        PRICE_UPDATE,     // Electricity price changed
        LOAD_ALERT,       // High/low load alert
        OUTAGE,           // Grid outage
        FREQUENCY_ALERT,  // Frequency deviation
        DEMAND_RESPONSE   // DR event triggered
    }

    /// @notice Grid event severity
    enum Severity {
        INFO,     // Informational
        WARNING,  // Warning level
        CRITICAL  // Critical alert
    }

    /// @notice Grid event struct
    struct GridEvent {
        EventType eventType;
        Severity severity;
        string city;              // City code (DEL, MUM, BLR, CHE, KOL)
        uint256 value;            // Event value (price, load, etc)
        uint256 timestamp;
        string metadata;          // JSON metadata
    }

    /// @notice Emit a grid event
    /// @param gridEvent Event details
    function emitGridEvent(GridEvent calldata gridEvent) external;

    /// @notice Get recent events
    /// @param limit Number of events
    /// @return events Array of recent events
    function getRecentEvents(uint256 limit)
        external
        view
        returns (GridEvent[] memory events);

    /// Events
    event GridEventEmitted(
        EventType indexed eventType,
        Severity indexed severity,
        string city,
        uint256 value,
        uint256 timestamp,
        string metadata
    );
}
```

### 3. AnomalyRegistry Contract

**Purpose**: Log anomalies detected by ML system on-chain

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

interface IAnomalyRegistry {
    /// @notice Anomaly type
    enum AnomalyType {
        PRICE_MANIPULATION,
        UNUSUAL_VOLUME,
        SUSPICIOUS_PATTERN,
        SYSTEM_ATTACK,
        DATA_CORRUPTION
    }

    /// @notice Anomaly struct
    struct Anomaly {
        uint256 anomalyId;
        AnomalyType anomalyType;
        address relatedAddress;   // Address involved (if any)
        uint256 tradeId;          // Related trade (if any)
        uint256 score;            // Anomaly score (0-100, scaled by 1e18)
        string description;
        uint256 timestamp;
        bool resolved;
    }

    /// @notice Report an anomaly
    /// @param anomaly Anomaly details
    /// @return anomalyId Unique identifier
    function reportAnomaly(Anomaly calldata anomaly) external returns (uint256 anomalyId);

    /// @notice Resolve an anomaly
    /// @param anomalyId Anomaly to resolve
    /// @param resolution Resolution notes
    function resolveAnomaly(uint256 anomalyId, string calldata resolution) external;

    /// @notice Get anomaly details
    /// @param anomalyId Anomaly identifier
    /// @return anomaly Anomaly struct
    function getAnomaly(uint256 anomalyId) external view returns (Anomaly memory anomaly);

    /// Events
    event AnomalyReported(
        uint256 indexed anomalyId,
        AnomalyType indexed anomalyType,
        address indexed relatedAddress,
        uint256 score,
        uint256 timestamp
    );

    event AnomalyResolved(
        uint256 indexed anomalyId,
        string resolution,
        uint256 timestamp
    );
}
```

## Event Specifications

### Event Structure

All events follow this standard structure:

```json
{
  "event": "EventName",
  "blockNumber": 12345678,
  "blockHash": "0xabcdef...",
  "transactionHash": "0x123456...",
  "transactionIndex": 0,
  "logIndex": 0,
  "removed": false,
  "address": "0xcontract...",
  "data": "0x...",
  "topics": ["0x..."],
  "args": {
    // Event-specific arguments
  },
  "timestamp": 1701612345
}
```

### TradeExecuted Event

```json
{
  "event": "TradeExecuted",
  "blockNumber": 12345678,
  "transactionHash": "0xabc123...",
  "args": {
    "tradeId": "42",
    "trader": "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb",
    "tradeType": 2,  // DISCHARGE
    "amountKWh": "30000000000000000000",  // 30 kWh (scaled by 1e18)
    "totalValue": "255000000000000000000",  // 255 INR (scaled by 1e18)
    "timestamp": 1701612345
  },
  "timestamp": 1701612345
}
```

**ML Processing**:
```python
def process_trade_executed(event):
    trade_id = int(event['args']['tradeId'])
    trader = event['args']['trader']
    trade_type = TradeType(event['args']['tradeType'])
    amount_kwh = int(event['args']['amountKWh']) / 1e18
    total_value_inr = int(event['args']['totalValue']) / 1e18

    # Update agent state
    update_trading_agent_state(
        trade_id=trade_id,
        amount_kwh=amount_kwh,
        value_inr=total_value_inr,
        trade_type=trade_type
    )

    # Record metrics
    metrics.track_trade(
        action_type=trade_type.name,
        volume_kwh=amount_kwh,
        value_inr=total_value_inr,
        profit=total_value_inr if trade_type == DISCHARGE else -total_value_inr
    )
```

### GridEventEmitted Event

```json
{
  "event": "GridEventEmitted",
  "blockNumber": 12345679,
  "transactionHash": "0xdef456...",
  "args": {
    "eventType": 0,  // PRICE_UPDATE
    "severity": 0,   // INFO
    "city": "DEL",
    "value": "8500000000000000000",  // 8.5 INR/kWh
    "timestamp": 1701612400,
    "metadata": "{\"source\": \"IEX\", \"market\": \"DAM\"}"
  },
  "timestamp": 1701612400
}
```

**ML Processing**:
```python
def process_grid_event(event):
    event_type = EventType(event['args']['eventType'])
    city = event['args']['city']
    value = int(event['args']['value']) / 1e18
    metadata = json.loads(event['args']['metadata'])

    if event_type == EventType.PRICE_UPDATE:
        # Update price in environment
        update_grid_price(city=city, price=value)

        # Trigger agent re-evaluation if significant change
        if abs(value - get_last_price(city)) > 2.0:
            trigger_agent_decision(city=city)
```

### AnomalyReported Event

```json
{
  "event": "AnomalyReported",
  "blockNumber": 12345680,
  "transactionHash": "0xghi789...",
  "args": {
    "anomalyId": "17",
    "anomalyType": 0,  // PRICE_MANIPULATION
    "relatedAddress": "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb",
    "score": "87500000000000000000",  // 87.5 (scaled by 1e18)
    "timestamp": 1701612450
  },
  "timestamp": 1701612450
}
```

## Data Format Standards

### Numeric Precision

**All monetary values and measurements use 18 decimal places** (Wei-like precision):

```
1 INR = 1e18 Wei-INR
1 kWh = 1e18 Wei-kWh

Examples:
- 8.5 INR/kWh → 8500000000000000000
- 30.25 kWh → 30250000000000000000
- 0.75 SOC (75%) → 750000000000000000
```

**Conversion**:
```python
# Solidity → Python
def from_wei(value: int, decimals: int = 18) -> float:
    return value / (10 ** decimals)

# Python → Solidity
def to_wei(value: float, decimals: int = 18) -> int:
    return int(value * (10 ** decimals))

# Usage
amount_kwh = from_wei(event['args']['amountKWh'])  # 30.0
amount_wei = to_wei(30.0)  # 30000000000000000000
```

### City Codes

```python
CITY_CODES = {
    "DEL": "Delhi",
    "MUM": "Mumbai",
    "BLR": "Bangalore",
    "CHE": "Chennai",
    "KOL": "Kolkata"
}
```

### Timestamps

- **Format**: Unix timestamp (seconds since epoch)
- **Timezone**: UTC
- **Range**: 1609459200 (2021-01-01) to 2147483647 (2038-01-19)

```python
# Current timestamp
timestamp = int(time.time())

# From datetime
timestamp = int(datetime.now().timestamp())

# To datetime
dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
```

## SLA Requirements

### Latency Requirements

| Operation | Target (P50) | Target (P99) | Max Acceptable |
|-----------|--------------|--------------|----------------|
| Trade submission | 2s | 5s | 15s |
| Trade confirmation | 30s | 60s | 120s |
| Event delivery | 15s | 45s | 90s |
| Event processing | 5s | 15s | 30s |
| Query response | 500ms | 2s | 5s |

### Availability

- **Blockchain RPC**: 99.9% uptime (< 43 minutes downtime/month)
- **Event stream**: 99.5% uptime (< 3.5 hours downtime/month)
- **Smart contracts**: 99.99% uptime (< 4 minutes downtime/month)

### Throughput

- **Trade submissions**: 100 TPS (transactions per second)
- **Event emissions**: 500 events/second
- **Query load**: 1000 queries/second

### Data Retention

- **On-chain**: Permanent (all transactions and events)
- **Event cache**: 30 days (for fast queries)
- **Archive node**: Full history queryable

## Testing & Mocks

### Mock Event Generator

**Purpose**: Generate realistic blockchain events for ML system testing

**File**: `tests/mocks/blockchain_event_generator.py`

```python
"""Mock blockchain event generator for testing ML system."""

import random
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any
import json


class BlockchainEventGenerator:
    """Generate mock blockchain events for testing."""

    def __init__(self, seed: int = 42):
        random.seed(seed)
        self.block_number = 12345000
        self.timestamp = int(datetime.now().timestamp())
        self.trade_id_counter = 1
        self.anomaly_id_counter = 1

    def generate_trade_executed(
        self,
        trader: str = None,
        trade_type: int = None,
        amount_kwh: float = None,
        price_per_kwh: float = None
    ) -> Dict[str, Any]:
        """Generate TradeExecuted event."""
        if trader is None:
            trader = f"0x{random.randbytes(20).hex()}"
        if trade_type is None:
            trade_type = random.choice([1, 2])  # CHARGE or DISCHARGE
        if amount_kwh is None:
            amount_kwh = random.uniform(10, 50)
        if price_per_kwh is None:
            price_per_kwh = random.uniform(6, 12)

        total_value = amount_kwh * price_per_kwh

        event = {
            "event": "TradeExecuted",
            "blockNumber": self.block_number,
            "blockHash": f"0x{random.randbytes(32).hex()}",
            "transactionHash": f"0x{random.randbytes(32).hex()}",
            "transactionIndex": 0,
            "logIndex": 0,
            "removed": False,
            "address": "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb",
            "args": {
                "tradeId": str(self.trade_id_counter),
                "trader": trader,
                "tradeType": trade_type,
                "amountKWh": str(int(amount_kwh * 1e18)),
                "totalValue": str(int(total_value * 1e18)),
                "timestamp": self.timestamp
            },
            "timestamp": self.timestamp
        }

        self.trade_id_counter += 1
        self.block_number += 1
        self.timestamp += random.randint(12, 18)  # ~15s per block

        return event

    def generate_grid_event(
        self,
        event_type: int = None,
        city: str = None,
        value: float = None
    ) -> Dict[str, Any]:
        """Generate GridEventEmitted event."""
        if event_type is None:
            event_type = 0  # PRICE_UPDATE
        if city is None:
            city = random.choice(["DEL", "MUM", "BLR", "CHE", "KOL"])
        if value is None:
            value = random.uniform(6, 12)  # Price range

        event = {
            "event": "GridEventEmitted",
            "blockNumber": self.block_number,
            "blockHash": f"0x{random.randbytes(32).hex()}",
            "transactionHash": f"0x{random.randbytes(32).hex()}",
            "transactionIndex": 0,
            "logIndex": 0,
            "removed": False,
            "address": "0x9876543210987654321098765432109876543210",
            "args": {
                "eventType": event_type,
                "severity": 0,  # INFO
                "city": city,
                "value": str(int(value * 1e18)),
                "timestamp": self.timestamp,
                "metadata": json.dumps({"source": "IEX", "market": "DAM"})
            },
            "timestamp": self.timestamp
        }

        self.block_number += 1
        self.timestamp += random.randint(12, 18)

        return event

    def generate_anomaly_reported(
        self,
        anomaly_type: int = None,
        score: float = None
    ) -> Dict[str, Any]:
        """Generate AnomalyReported event."""
        if anomaly_type is None:
            anomaly_type = random.choice([0, 1, 2, 3, 4])
        if score is None:
            score = random.uniform(50, 100)

        event = {
            "event": "AnomalyReported",
            "blockNumber": self.block_number,
            "blockHash": f"0x{random.randbytes(32).hex()}",
            "transactionHash": f"0x{random.randbytes(32).hex()}",
            "transactionIndex": 0,
            "logIndex": 0,
            "removed": False,
            "address": "0xabcdefabcdefabcdefabcdefabcdefabcdefabcd",
            "args": {
                "anomalyId": str(self.anomaly_id_counter),
                "anomalyType": anomaly_type,
                "relatedAddress": f"0x{random.randbytes(20).hex()}",
                "score": str(int(score * 1e18)),
                "timestamp": self.timestamp
            },
            "timestamp": self.timestamp
        }

        self.anomaly_id_counter += 1
        self.block_number += 1
        self.timestamp += random.randint(12, 18)

        return event

    def generate_scenario(
        self,
        duration_hours: int = 24,
        trades_per_hour: int = 10
    ) -> List[Dict[str, Any]]:
        """Generate a complete trading scenario."""
        events = []
        num_events = duration_hours * trades_per_hour

        for _ in range(num_events):
            # Mix of event types
            event_type = random.choice(["trade", "trade", "trade", "grid", "anomaly"])

            if event_type == "trade":
                events.append(self.generate_trade_executed())
            elif event_type == "grid":
                events.append(self.generate_grid_event())
            else:
                events.append(self.generate_anomaly_reported())

        return events


# Usage example
if __name__ == "__main__":
    generator = BlockchainEventGenerator()

    # Generate single event
    trade_event = generator.generate_trade_executed()
    print(json.dumps(trade_event, indent=2))

    # Generate 24-hour scenario
    scenario = generator.generate_scenario(duration_hours=24, trades_per_hour=10)
    print(f"Generated {len(scenario)} events for 24-hour scenario")
```

### Testing with Mocks

```python
# tests/integration/test_with_blockchain_mocks.py

import pytest
from tests.mocks.blockchain_event_generator import BlockchainEventGenerator
from src.blockchain.integration import BlockchainClient

def test_ml_system_with_mock_events():
    """Test ML system with mocked blockchain events."""
    # Initialize
    generator = BlockchainEventGenerator()
    blockchain_client = BlockchainClient(mock_mode=True)

    # Generate events
    events = generator.generate_scenario(duration_hours=1, trades_per_hour=5)

    # Process events through ML system
    for event in events:
        blockchain_client.inject_mock_event(event)
        # ML system processes event asynchronously
        time.sleep(0.1)

    # Verify ML system processed all events
    processed_count = blockchain_client.get_processed_event_count()
    assert processed_count == len(events), f"Expected {len(events)}, got {processed_count}"
```

## Security Considerations

### Authentication
- **ML → Blockchain**: Private key signing (ECDSA)
- **Event Stream**: API key or JWT token
- **Admin operations**: Multi-sig wallet

### Data Integrity
- **Trade data**: Hash of ML prediction included in transaction
- **Event replay**: Blockchain provides natural ordering
- **Anomaly reports**: Signed by ML service key

### Access Control
- **Trade submission**: Only authorized ML agent addresses
- **Event emission**: Only grid operator addresses
- **Anomaly reporting**: Only ML service address

### Rate Limiting
- **Trade submissions**: Max 100 per minute per address
- **Event queries**: Max 1000 per minute per API key
- **Anomaly reports**: Max 50 per hour

## Monitoring & Alerts

### Metrics to Track

```python
# Blockchain integration metrics
blockchain_rpc_latency_seconds
blockchain_event_processing_latency_seconds
blockchain_trade_submission_rate
blockchain_event_received_rate
blockchain_connection_failures_total
blockchain_transaction_gas_used
blockchain_block_lag_seconds

# Alerts
- RPC latency > 5s for 5 minutes → WARNING
- Event processing lag > 60s → CRITICAL
- Connection failures > 10 in 5 minutes → CRITICAL
- Trade submission failures > 5% → WARNING
```

### Blockchain Health Check

```python
async def check_blockchain_health():
    """Check blockchain connection and contract health."""
    checks = {
        "rpc_connected": False,
        "latest_block": None,
        "block_lag_seconds": None,
        "contract_accessible": False,
        "event_stream_active": False
    }

    try:
        # Check RPC connection
        checks["rpc_connected"] = await blockchain_client.is_connected()

        # Check block lag
        latest_block = await blockchain_client.get_latest_block()
        checks["latest_block"] = latest_block.number
        checks["block_lag_seconds"] = time.time() - latest_block.timestamp

        # Check contract
        checks["contract_accessible"] = await blockchain_client.check_contract()

        # Check event stream
        checks["event_stream_active"] = await blockchain_client.check_event_stream()

    except Exception as e:
        logger.error(f"Blockchain health check failed: {e}")

    return checks
```

## Contact & Support

### Blockchain Team
- **Lead**: blockchain-lead@shaktichain.io
- **Slack**: #blockchain-dev
- **Issues**: GitHub Issues (label: blockchain-integration)

### ML Team
- **Lead**: ml-lead@shaktichain.io
- **Slack**: #ml-engineering
- **Issues**: GitHub Issues (label: ml-blockchain)

### Integration Support
- **Slack**: #ml-blockchain-integration
- **Meetings**: Weekly sync (Wednesdays 3 PM IST)
- **On-call**: PagerDuty escalation

---

**Document Version**: 1.0
**Last Updated**: 2024-12-03
**Next Review**: 2025-01-03
**Owner**: ML & Blockchain Teams
