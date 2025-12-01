# SHAKTI-CHAIN AI Team Integration Guide

## Overview

This document provides the AI/ML team with all necessary information to integrate with SHAKTI-CHAIN smart contracts for:
- Price prediction models
- Trading agents
- Demand forecasting
- Anomaly detection

---

## Quick Start

### 1. Connect to Blockchain

```javascript
const { ethers } = require('ethers');

// Connect to Polygon
const provider = new ethers.JsonRpcProvider('https://polygon-rpc.com');

// Load contract ABIs (generated in artifacts/)
const auctionABI = require('./artifacts/contracts/trading/EnergyAuction.sol/EnergyAuction.json').abi;

// Contract addresses (replace with deployed addresses)
const CONTRACTS = {
  token: '0x...',
  auction: '0x...',
  escrow: '0x...',
  oracle: '0x...',
  pricing: '0x...',
  reputation: '0x...'
};

// Initialize contracts
const auction = new ethers.Contract(CONTRACTS.auction, auctionABI, provider);
```

### 2. Listen to Events

```javascript
// Listen for new orders
auction.on('BidPlaced', (roundId, orderId, bidder, quantity, price, event) => {
  console.log('New bid:', {
    roundId: roundId.toString(),
    orderId: orderId.toString(),
    bidder,
    quantity: ethers.formatEther(quantity), // kWh
    price: ethers.formatEther(price)  // SHAKTI/kWh
  });
});
```

---

## Contract Events (AI Consumption)

### EnergyAuction Events

| Event | Parameters | Description | AI Use Case |
|-------|------------|-------------|-------------|
| `AuctionRoundStarted` | `roundId, startTime, endTime` | New auction round begins | Trigger prediction models |
| `BidPlaced` | `roundId, orderId, bidder, quantity, maxPrice` | Buyer places bid | Order book analysis |
| `AskPlaced` | `roundId, orderId, seller, quantity, minPrice` | Seller places ask | Supply forecasting |
| `OrderCancelled` | `roundId, orderId, user` | Order withdrawn | Market sentiment |
| `OrdersMatched` | `roundId, matchCount, clearingPrice, totalVolume` | Trades executed | Price discovery data |
| `AuctionRoundEnded` | `roundId, totalBids, totalAsks, matchedVolume` | Round completed | Historical analysis |

**Event Signatures (for filtering):**
```javascript
// Topic0 hashes for event filtering
const EVENT_TOPICS = {
  BidPlaced: ethers.id('BidPlaced(uint256,uint256,address,uint256,uint256)'),
  AskPlaced: ethers.id('AskPlaced(uint256,uint256,address,uint256,uint256)'),
  OrdersMatched: ethers.id('OrdersMatched(uint256,uint256,uint256,uint256)'),
};
```

### PriceOracle Events

| Event | Parameters | Description | AI Use Case |
|-------|------------|-------------|-------------|
| `PriceUpdated` | `price, timestamp` | New IEX price | Feature input |
| `PriceDeviation` | `oldPrice, newPrice, deviation` | Unusual price move | Anomaly flag |
| `StalePriceDetected` | `lastUpdate, threshold` | Oracle stale | Fallback trigger |

### DynamicPricing Events

| Event | Parameters | Description | AI Use Case |
|-------|------------|-------------|-------------|
| `DemandMultiplierUpdated` | `oldMultiplier, newMultiplier` | Demand change | Demand modeling |
| `GridStressDetected` | `frequency, severity` | Grid imbalance | V2G opportunity |
| `PriceTierChanged` | `hour, tier, multiplier` | ToU change | Time series |

### ReputationSystem Events

| Event | Parameters | Description | AI Use Case |
|-------|------------|-------------|-------------|
| `ReputationUpdated` | `user, oldScore, newScore, reason` | Score change | User behavior |
| `TierChanged` | `user, oldTier, newTier` | Tier upgrade/downgrade | Segmentation |
| `UserBanned` | `user, reason, duration` | Bad actor | Fraud detection |

---

## Data Formats

### Order Structure

```typescript
interface Order {
  orderId: bigint;        // Unique order ID
  roundId: bigint;        // Auction round
  user: string;           // Ethereum address (0x...)
  quantity: bigint;       // kWh in wei (1e18 = 1 kWh)
  price: bigint;          // SHAKTI/kWh in wei (1e18 = 1 SHAKTI)
  timestamp: bigint;      // Unix timestamp
  isBid: boolean;         // true = buy, false = sell
  status: number;         // 0=Active, 1=Matched, 2=Cancelled
}

// Example: Convert from contract response
const rawOrder = await auction.getOrder(roundId, orderId);
const order = {
  quantity: Number(ethers.formatEther(rawOrder.quantity)), // 50.0 kWh
  price: Number(ethers.formatEther(rawOrder.price)),       // 0.005 SHAKTI
};
```

### Trade Structure

```typescript
interface Trade {
  tradeId: bigint;
  roundId: bigint;
  seller: string;
  buyer: string;
  quantity: bigint;       // kWh traded
  price: bigint;          // Clearing price
  timestamp: bigint;
  status: number;         // 0=Pending, 1=Delivered, 2=Disputed, 3=Settled
}
```

### User Reputation

```typescript
interface UserReputation {
  address: string;
  score: number;          // 0-1000
  tier: number;           // 0=Bronze, 1=Silver, 2=Gold, 3=Platinum, 4=Diamond
  totalTrades: number;
  successRate: number;    // 0.0 - 1.0
  avgTradeSize: number;   // kWh
  lastActive: number;     // Unix timestamp
}
```

---

## API Endpoints (Read Functions)

### EnergyAuction

```javascript
// Get current auction state
const currentRound = await auction.currentRound();
const roundData = await auction.rounds(currentRound);
/*
  roundData = {
    startTime: 1701234567n,
    endTime: 1701235167n,
    clearingPrice: 5000000000000000n,  // 0.005 SHAKTI
    totalBidVolume: 1000000000000000000000n,  // 1000 kWh
    totalAskVolume: 800000000000000000000n,   // 800 kWh
    totalMatched: 750000000000000000000n,     // 750 kWh
    status: 1  // 0=Pending, 1=Open, 2=Closed, 3=Clearing, 4=Settled
  }
*/

// Get order book
const bids = await auction.getRoundBids(roundId);
const asks = await auction.getRoundAsks(roundId);

// Get user's orders
const userBids = await auction.getUserBids(userAddress);
const userAsks = await auction.getUserAsks(userAddress);

// Get historical clearing prices
const historicalPrices = [];
for (let i = 1; i <= currentRound; i++) {
  const round = await auction.rounds(i);
  historicalPrices.push({
    roundId: i,
    clearingPrice: Number(ethers.formatEther(round.clearingPrice)),
    volume: Number(ethers.formatEther(round.totalMatched))
  });
}
```

### PriceOracle

```javascript
// Get current price
const currentPrice = await oracle.getLatestPrice();
// Returns: 500000000n (5.00 INR with 8 decimals)

// Check if price is stale
const isStale = await oracle.isPriceStale();

// Get price bounds
const minPrice = await oracle.minPrice();
const maxPrice = await oracle.maxPrice();
```

### DynamicPricing

```javascript
// Calculate price for a trade
const price = await pricing.calculatePrice(
  ethers.parseEther("100"),  // 100 kWh
  4 * 3600  // 4 hour delivery window
);

// Get current demand multiplier
const demandMultiplier = await pricing.getDemandMultiplier();
// Returns: 120 (1.20x)

// Get current pricing tier
const tier = await pricing.getCurrentTier();
// Returns: 0=Off-peak, 1=Shoulder, 2=Peak

// Get grid frequency
const frequency = await gridOracle.getFrequency();
// Returns: 5000 (50.00 Hz)
```

### ReputationSystem

```javascript
// Get user reputation
const rep = await reputation.getReputation(userAddress);
// Returns: 750n (score)

// Get user tier
const tier = await reputation.getUserTier(userAddress);
// Returns: 3 (Platinum)

// Get full user stats
const stats = await reputation.getUserStats(userAddress);
/*
  stats = {
    totalTrades: 150,
    successfulTrades: 145,
    failedTrades: 5,
    totalVolume: 5000000000000000000000n,  // 5000 kWh
    joinedAt: 1698765432n
  }
*/
```

---

## ML Model Inputs

### Feature Engineering

```python
import pandas as pd
from web3 import Web3

class ShaktiDataPipeline:
    def __init__(self, rpc_url, contracts):
        self.w3 = Web3(Web3.HTTPProvider(rpc_url))
        self.contracts = contracts

    def get_order_book_features(self, round_id):
        """Extract features from current order book"""
        bids = self.contracts['auction'].functions.getRoundBids(round_id).call()
        asks = self.contracts['auction'].functions.getRoundAsks(round_id).call()

        return {
            'bid_count': len(bids),
            'ask_count': len(asks),
            'bid_volume': sum(b['quantity'] for b in bids) / 1e18,
            'ask_volume': sum(a['quantity'] for a in asks) / 1e18,
            'bid_ask_ratio': len(bids) / max(len(asks), 1),
            'spread': self._calculate_spread(bids, asks),
            'vwap_bid': self._calculate_vwap(bids),
            'vwap_ask': self._calculate_vwap(asks),
        }

    def get_market_features(self):
        """Get current market state"""
        price = self.contracts['oracle'].functions.getLatestPrice().call()
        multiplier = self.contracts['pricing'].functions.getDemandMultiplier().call()
        frequency = self.contracts['grid'].functions.getFrequency().call()

        return {
            'base_price': price / 1e8,
            'demand_multiplier': multiplier / 100,
            'grid_frequency': frequency / 100,
            'hour_of_day': datetime.now().hour,
            'day_of_week': datetime.now().weekday(),
            'is_peak': 17 <= datetime.now().hour <= 21,
        }

    def get_user_features(self, address):
        """Get user-specific features"""
        rep = self.contracts['reputation'].functions.getReputation(address).call()
        stats = self.contracts['reputation'].functions.getUserStats(address).call()

        return {
            'reputation_score': rep,
            'tier': self._score_to_tier(rep),
            'total_trades': stats[0],
            'success_rate': stats[1] / max(stats[0], 1),
            'avg_trade_size': stats[4] / max(stats[0], 1) / 1e18,
        }
```

### Training Data Schema

```python
# Historical trade data for ML training
TRAINING_SCHEMA = {
    'trade_id': 'int64',
    'round_id': 'int64',
    'timestamp': 'datetime64[ns]',
    'clearing_price': 'float64',      # SHAKTI/kWh
    'volume': 'float64',              # kWh
    'bid_count': 'int32',
    'ask_count': 'int32',
    'bid_volume': 'float64',
    'ask_volume': 'float64',
    'base_price': 'float64',          # Oracle price
    'demand_multiplier': 'float64',
    'grid_frequency': 'float64',
    'hour': 'int8',
    'day_of_week': 'int8',
    'is_weekend': 'bool',
    'is_peak': 'bool',
}
```

---

## Oracle Endpoints

### Price Oracle Integration

The AI team can provide price predictions to the oracle:

```solidity
// Oracle interface for AI predictions
interface IAIPriceOracle {
    // Update price with AI prediction
    function updatePredictedPrice(
        uint256 predictedPrice,
        uint256 confidence,     // 0-100
        bytes calldata proof    // Optional ZK proof
    ) external;

    // Get AI prediction
    function getPredictedPrice() external view returns (
        uint256 price,
        uint256 confidence,
        uint256 timestamp
    );
}
```

### Grid Oracle Integration

```solidity
// Grid frequency feed
interface IGridOracle {
    function getFrequency() external view returns (uint256);  // Hz * 100
    function getGridStress() external view returns (uint8);    // 0-100
    function getV2GIncentive() external view returns (uint256); // SHAKTI/kWh bonus
}
```

---

## Mock Contracts for Testing

For AI team testing, use these mock contracts:

### MockPriceFeed.sol

```solidity
contract MockPriceFeed {
    int256 public price;
    uint8 public decimals = 8;

    function updatePrice(int256 _price) external {
        price = _price;
    }

    function latestRoundData() external view returns (
        uint80 roundId,
        int256 answer,
        uint256 startedAt,
        uint256 updatedAt,
        uint80 answeredInRound
    ) {
        return (1, price, block.timestamp, block.timestamp, 1);
    }
}
```

### MockAuction.sol (Simplified)

```solidity
contract MockAuction {
    struct Order {
        address user;
        uint256 quantity;
        uint256 price;
        bool isBid;
    }

    Order[] public orders;

    function placeOrder(uint256 quantity, uint256 price, bool isBid) external {
        orders.push(Order(msg.sender, quantity, price, isBid));
        emit OrderPlaced(orders.length - 1, msg.sender, quantity, price, isBid);
    }

    function getOrders() external view returns (Order[] memory) {
        return orders;
    }

    event OrderPlaced(uint256 indexed orderId, address user, uint256 quantity, uint256 price, bool isBid);
}
```

---

## WebSocket Event Streaming

For real-time ML inference:

```javascript
const WebSocket = require('ws');
const { ethers } = require('ethers');

class EventStreamer {
  constructor(wsUrl, contracts) {
    this.provider = new ethers.WebSocketProvider(wsUrl);
    this.contracts = contracts;
  }

  async streamOrderEvents(callback) {
    const auction = new ethers.Contract(
      this.contracts.auction,
      auctionABI,
      this.provider
    );

    auction.on('BidPlaced', (roundId, orderId, bidder, qty, price) => {
      callback({
        type: 'bid',
        roundId: roundId.toString(),
        orderId: orderId.toString(),
        user: bidder,
        quantity: ethers.formatEther(qty),
        price: ethers.formatEther(price),
        timestamp: Date.now()
      });
    });

    auction.on('AskPlaced', (roundId, orderId, seller, qty, price) => {
      callback({
        type: 'ask',
        roundId: roundId.toString(),
        orderId: orderId.toString(),
        user: seller,
        quantity: ethers.formatEther(qty),
        price: ethers.formatEther(price),
        timestamp: Date.now()
      });
    });
  }
}

// Usage
const streamer = new EventStreamer(WS_URL, CONTRACTS);
streamer.streamOrderEvents((event) => {
  // Feed to ML model
  mlModel.processEvent(event);
});
```

---

## Rate Limits & Best Practices

### RPC Rate Limits

| Provider | Free Tier | Notes |
|----------|-----------|-------|
| Alchemy | 300 req/s | Recommended |
| Infura | 100 req/s | Good backup |
| QuickNode | 25 req/s | Premium only |
| Public RPC | 10 req/s | Development only |

### Optimization Tips

1. **Batch Calls**: Use multicall for reading multiple values
```javascript
const multicall = new ethers.Contract(MULTICALL_ADDRESS, multicallABI, provider);
const results = await multicall.aggregate([
  [auction.address, auction.interface.encodeFunctionData('currentRound')],
  [oracle.address, oracle.interface.encodeFunctionData('getLatestPrice')],
]);
```

2. **Cache Immutable Data**: Contract addresses, constants
3. **Use Filters**: Only subscribe to relevant events
4. **Pagination**: Use offset/limit for large queries

---

## Deployment Addresses

### Polygon Amoy Testnet (Chain ID: 80002)

```json
{
  "ShaktiToken": "0x...",
  "StakingPool": "0x...",
  "EnergyRegistry": "0x...",
  "PriceOracle": "0x...",
  "DynamicPricing": "0x...",
  "EnergyAuction": "0x...",
  "EnergyEscrow": "0x...",
  "Treasury": "0x...",
  "ReputationSystem": "0x...",
  "EnergyVerification": "0x...",
  "TimelockController": "0x...",
  "ShaktiGovernor": "0x..."
}
```

### Polygon Mainnet (Chain ID: 137)

```json
{
  "ShaktiToken": "TBD",
  "StakingPool": "TBD",
  "...": "..."
}
```

---

## Contact & Support

- **Smart Contract Questions**: blockchain-team@shakti.energy
- **API Issues**: api-support@shakti.energy
- **Documentation**: docs.shakti.energy

---

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2024-12 | Initial release |

---

*Document Version: 1.0*
*Last Updated: December 2024*
