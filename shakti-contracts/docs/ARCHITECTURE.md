# SHAKTI-CHAIN Architecture

## System Overview

SHAKTI-CHAIN is a decentralized Vehicle-to-Grid (V2G) energy trading platform built on Polygon. The system enables electric vehicle owners to sell excess energy back to the grid through a transparent, efficient double-auction mechanism.

```
┌─────────────────────────────────────────────────────────────────┐
│                        FRONTEND (React)                         │
│  - Dashboard  - Auction UI  - Wallet Connect  - Analytics       │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      BACKEND (FastAPI)                          │
│  - Simulation Engine  - Price History  - Event Sync             │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    BLOCKCHAIN (Polygon)                         │
│  ┌───────────────┐ ┌───────────────┐ ┌───────────────┐         │
│  │ ShaktiToken   │ │ EnergyAuction │ │ StakingPool   │         │
│  └───────────────┘ └───────────────┘ └───────────────┘         │
│  ┌───────────────┐ ┌───────────────┐ ┌───────────────┐         │
│  │ EnergyEscrow  │ │ Reputation    │ │ DynamicPricing│         │
│  └───────────────┘ └───────────────┘ └───────────────┘         │
│  ┌───────────────┐ ┌───────────────┐ ┌───────────────┐         │
│  │ PriceOracle   │ │ GridOracle    │ │ Treasury      │         │
│  └───────────────┘ └───────────────┘ └───────────────┘         │
└─────────────────────────────────────────────────────────────────┘
```

## Core Contracts

### 1. ShaktiToken (ERC20)

**Purpose**: Native utility token for the SHAKTI-CHAIN ecosystem.

**Key Features**:
- ERC20 with EIP-2612 Permit (gasless approvals)
- Burnable (deflationary mechanics)
- Pausable (emergency stop)
- Role-based access control (MINTER, PAUSER, BURNER)

**Storage Layout**:
```solidity
// Inherited from ERC20
mapping(address => uint256) private _balances;
mapping(address => mapping(address => uint256)) private _allowances;
uint256 private _totalSupply;

// Custom
uint256 public totalFeesBurned;
```

**External Interactions**:
- Staking: Users stake SHAKTI for rewards
- Auction: Payment for energy trades
- Escrow: Settlement of trades

---

### 2. EnergyAuction

**Purpose**: McAfee double auction for energy trading.

**Key Features**:
- Time-bound auction rounds (5-60 minutes)
- Batch order processing for gas efficiency
- Uniform clearing price mechanism
- Max 500 orders per round

**Auction Flow**:
```
1. createAuctionRound(duration)
   └─> State: OPEN

2. submitBid(quantity, maxPrice)   ─┐
   submitAsk(quantity, minPrice)   ─┤─> During OPEN period
   cancelOrder(roundId, orderId)   ─┘

3. closeAuction(roundId)
   └─> State: CLOSED

4. clearMarket(roundId)  (can be called multiple times for batching)
   └─> State: CLEARING -> SETTLED

5. settleRefunds(roundId)
   └─> Users reclaim unmatched deposits
```

**McAfee Algorithm**:
```
1. Sort bids descending by price
2. Sort asks ascending by price
3. Find k where bid[k] >= ask[k] but bid[k+1] < ask[k+1]
4. Clearing price = (bid[k] + ask[k+1]) / 2
5. All matched pairs trade at clearing price
```

**Storage Layout**:
```solidity
IERC20 public immutable shaktiToken;
uint256 public currentRoundId;
uint128 public minPrice;
uint128 public maxPrice;
mapping(uint256 => AuctionRound) public auctionRounds;
mapping(uint256 => mapping(uint256 => Order)) public orders;
mapping(uint256 => uint256[]) public bidOrderIds;
mapping(uint256 => uint256[]) public askOrderIds;
mapping(address => mapping(uint256 => uint256)) public lockedDeposits;
```

---

### 3. StakingPool

**Purpose**: Staking mechanism with tiered APY.

**Key Features**:
- 8% base APY (configurable)
- Lock period multipliers:
  - No lock: 1.0x
  - 30 days: 1.2x
  - 90 days: 1.5x
- Compound rewards option
- Emergency withdrawal (forfeits rewards)

**Reward Calculation**:
```
rewardPerToken = stored + (totalStaked * rate * elapsed) / (secondsPerYear * totalStaked)
userReward = (userStake * rewardPerToken - rewardDebt) * multiplier
```

**Storage Layout**:
```solidity
IERC20 public immutable stakingToken;
mapping(address => StakeInfo) public stakes;
uint256 public totalStaked;
uint256 public rewardPerTokenStored;
uint256 public lastUpdateTime;
uint256 public annualRewardRate;
```

---

### 4. EnergyEscrow

**Purpose**: Secure settlement of energy trades.

**Key Features**:
- 2% platform fee (70% treasury, 30% burned)
- 24-hour dispute window
- Arbiter-based dispute resolution
- Circuit breaker for emergencies

**Settlement Flow**:
```
1. deposit(roundId, amount)
   └─> Locks buyer funds

2. createSettlement(roundId, buyer, seller, quantity, price)
   └─> Called by auction contract

3. Dispute Window (24h)
   ├─> No dispute: completeSettlement()
   └─> Dispute: raiseDispute() -> resolveDispute()

4. Funds distributed:
   ├─> Seller: amount - fee
   ├─> Treasury: fee * 70%
   └─> Burned: fee * 30%
```

---

### 5. ReputationSystem

**Purpose**: Trust and reputation management.

**Tier Structure**:
| Tier     | Score   | Fee Rate | Features                    |
|----------|---------|----------|-----------------------------|
| Bronze   | 0-300   | 2.5%     | Basic access                |
| Silver   | 300-500 | 2.0%     | Standard access             |
| Gold     | 500-700 | 1.5%     | Priority matching           |
| Platinum | 700-850 | 1.0%     | Premium features            |
| Diamond  | 850-1000| 0.5%     | Governance multiplier, rebates |

**Reputation Changes**:
```
Successful trade:     +5 to +10 (based on size)
Failed delivery:      -50
Dispute lost:         -30
Dispute won:          +10
Weekly inactivity:    -1 (capped at -10 per call)
```

**Sybil Resistance**:
- Minimum 100 SHAKTI stake to build reputation
- KYC verified accounts get 1.5x reputation gains
- Suspicious patterns flagged for review

---

### 6. DynamicPricing

**Purpose**: Market-responsive pricing engine.

**Pricing Formula**:
```
FinalPrice = BasePrice
           × DemandMultiplier
           × TimeOfUseMultiplier
           × GridStressMultiplier
           × SeasonalMultiplier
```

**Demand Levels**:
| Level        | Ratio  | Multiplier |
|--------------|--------|------------|
| Surplus      | <0.5   | 0.7x       |
| Low Demand   | 0.5-0.8| 0.85x      |
| Balanced     | 0.8-1.2| 1.0x       |
| Moderate High| 1.2-1.5| 1.15x      |
| High Demand  | 1.5-2.0| 1.3x       |
| Surge        | >2.0   | 1.5x       |

**Time-of-Use (IST)**:
- Peak: 18:00-22:00 (+30%)
- Shoulder: 06:00-10:00, 14:00-18:00 (+10%)
- Off-peak: 22:00-06:00 (-20%)

---

### 7. Oracles

**PriceOracle**:
- Fetches current energy prices
- Supports Chainlink integration
- Peak hour pricing adjustments

**GridStatusOracle**:
- Monitors grid frequency (target: 50.000 Hz)
- Under-frequency (<49.5 Hz): +50% multiplier
- Over-frequency (>50.5 Hz): -30% multiplier
- V2G incentive calculations

---

## Contract Interactions

```
User                  ShaktiToken          EnergyAuction         EnergyEscrow
  │                       │                     │                     │
  │ approve(auction)      │                     │                     │
  ├──────────────────────>│                     │                     │
  │                       │                     │                     │
  │ submitBid(qty, price) │                     │                     │
  ├──────────────────────────────────────────>  │                     │
  │                       │  transferFrom       │                     │
  │                       │<────────────────────┤                     │
  │                       │                     │                     │
  │                       │        clearMarket()│                     │
  │                       │<────────────────────┤                     │
  │                       │   transfer(seller)  │                     │
  │                       ├────────────────────>│                     │
  │                       │                     │                     │
```

## Upgrade Strategy

The contracts use OpenZeppelin's UUPS proxy pattern for upgradeability:

1. **Proxy Contract**: Stores state, delegates calls
2. **Implementation**: Contains logic, no state
3. **Upgrade**: Deploy new implementation, update proxy

**Upgrade-Safe Contracts**:
- ShaktiTokenUpgradeable
- EnergyAuctionUpgradeable
- StakingPoolUpgradeable

**Upgrade Process**:
```
1. Deploy new implementation
2. Call upgradeToAndCall() on proxy
3. Verify new logic
4. Emit upgrade event
```

## Gas Optimization Summary

| Optimization          | Location                    | Savings Est. |
|-----------------------|-----------------------------|--------------|
| Custom errors         | All contracts               | ~200 gas/error |
| Packed structs        | Order, StakeInfo, Settlement| ~2000 gas/write |
| Unchecked math        | Where overflow impossible   | ~20 gas/op   |
| Batch processing      | EnergyAuction.clearMarket() | ~30% overall |
| SafeERC20             | All token transfers         | Security trade-off |

## Dependencies

| Package                    | Version | Purpose              |
|----------------------------|---------|----------------------|
| @openzeppelin/contracts    | 5.0.0   | Standard contracts   |
| @openzeppelin/contracts-upgradeable | 5.0.0 | Upgradeable patterns |

## Network Configuration

| Network        | Chain ID | RPC                              |
|----------------|----------|----------------------------------|
| Polygon Mainnet| 137      | https://polygon-rpc.com          |
| Polygon Amoy   | 80002    | https://rpc-amoy.polygon.technology |
| Hardhat Local  | 31337    | http://127.0.0.1:8545            |
