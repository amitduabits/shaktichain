# SHAKTI-CHAIN Smart Contract Reference

## Table of Contents

1. [ShaktiToken](#1-shaktitoken)
2. [StakingPool](#2-stakingpool)
3. [EnergyRegistry](#3-energyregistry)
4. [PriceOracle](#4-priceoracle)
5. [DynamicPricing](#5-dynamicpricing)
6. [EnergyAuction](#6-energyauction)
7. [EnergyEscrow](#7-energyescrow)
8. [Treasury](#8-treasury)
9. [ReputationSystem](#9-reputationsystem)
10. [EnergyVerification](#10-energyverification)
11. [ShaktiGovernor](#11-shaktigovernor)
12. [TimelockController](#12-timelockcontroller)

---

## 1. ShaktiToken

**Purpose**: ERC20 governance token with voting capabilities

**Inheritance**: ERC20, ERC20Burnable, ERC20Pausable, ERC20Votes, AccessControl

### Constants

| Name | Value | Description |
|------|-------|-------------|
| `MAX_SUPPLY` | 1,000,000,000 SHAKTI | Maximum token supply |
| `INITIAL_SUPPLY` | 1,000,000,000 SHAKTI | Initial minted amount |

### Roles

| Role | Description |
|------|-------------|
| `DEFAULT_ADMIN_ROLE` | Can grant/revoke roles |
| `MINTER_ROLE` | Can mint new tokens |
| `PAUSER_ROLE` | Can pause/unpause transfers |
| `BURNER_ROLE` | Can burn tokens |

### Functions

#### `mint(address to, uint256 amount)`
Mints new tokens (requires MINTER_ROLE)

**Parameters:**
- `to`: Recipient address
- `amount`: Amount to mint (in wei)

**Requirements:**
- Caller must have MINTER_ROLE
- Total supply must not exceed MAX_SUPPLY

#### `burn(uint256 amount)`
Burns tokens from caller's balance

**Parameters:**
- `amount`: Amount to burn (in wei)

#### `pause()` / `unpause()`
Pauses/unpauses all token transfers (requires PAUSER_ROLE)

### Events

```solidity
event Transfer(address indexed from, address indexed to, uint256 value);
event Approval(address indexed owner, address indexed spender, uint256 value);
event Paused(address account);
event Unpaused(address account);
```

---

## 2. StakingPool

**Purpose**: Staking mechanism with tiered lock periods and rewards

### Constants

| Name | Value | Description |
|------|-------|-------------|
| `MIN_STAKE` | 100 SHAKTI | Minimum stake amount |
| `BASE_RATE` | 800 (8%) | Annual reward rate in basis points |
| `LOCK_30_DAYS` | 30 days | Short lock period |
| `LOCK_90_DAYS` | 90 days | Medium lock period |
| `LOCK_180_DAYS` | 180 days | Long lock period |

### Lock Tier Multipliers

| Tier | Lock Period | Multiplier |
|------|-------------|------------|
| 0 | 30 days | 1.0x |
| 1 | 90 days | 1.25x |
| 2 | 180 days | 1.5x |

### Functions

#### `stake(uint256 amount, uint8 lockTier)`
Stakes tokens with specified lock period

**Parameters:**
- `amount`: Amount to stake (in wei)
- `lockTier`: 0=30 days, 1=90 days, 2=180 days

**Requirements:**
- Amount >= MIN_STAKE
- Token approval required

#### `unstake(uint256 stakeIndex)`
Unstakes tokens after lock period

**Parameters:**
- `stakeIndex`: Index of stake to withdraw

**Requirements:**
- Lock period must be expired
- Stake must exist

#### `claimRewards()`
Claims accumulated rewards for all stakes

#### `pendingRewards(address user) → uint256`
Returns pending rewards for user

### Events

```solidity
event Staked(address indexed user, uint256 amount, uint8 lockTier, uint256 lockEnd);
event Unstaked(address indexed user, uint256 amount, uint256 rewards);
event RewardsClaimed(address indexed user, uint256 rewards);
```

---

## 3. EnergyRegistry

**Purpose**: Prosumer and EV registration

### Structs

```solidity
struct Prosumer {
    string name;
    string prosumerType;  // "Residential", "Commercial", "Industrial"
    uint256 capacity;     // Maximum capacity in watts
    string location;      // State/region
    string coordinates;   // GPS coordinates
    bool isActive;
    uint256 registeredAt;
}

struct ElectricVehicle {
    string vehicleId;
    uint256 batteryCapacity;  // kWh
    uint256 maxDischarge;     // kW
    bool isActive;
}
```

### Functions

#### `registerProsumer(string name, string type, uint256 capacity, string location, string coordinates)`
Registers a new prosumer

**Requirements:**
- Not already registered
- Valid capacity > 0

#### `registerEV(string vehicleId, uint256 batteryCapacity, uint256 maxDischarge)`
Registers an EV for V2G

**Requirements:**
- Prosumer must be registered
- Max 10 EVs per prosumer

#### `updateProsumerStatus(address prosumer, bool isActive)`
Enables/disables prosumer (admin only)

### Events

```solidity
event ProsumerRegistered(address indexed prosumer, string name, string prosumerType);
event EVRegistered(address indexed owner, string vehicleId, uint256 batteryCapacity);
event ProsumerStatusChanged(address indexed prosumer, bool isActive);
```

---

## 4. PriceOracle

**Purpose**: Chainlink price feed integration

### Constants

| Name | Value | Description |
|------|-------|-------------|
| `MIN_PRICE` | 1 INR/kWh | Floor price |
| `MAX_PRICE` | 20 INR/kWh | Ceiling price |
| `STALENESS_THRESHOLD` | 3600 seconds | Max age of price |

### Functions

#### `getLatestPrice() → uint256`
Returns latest electricity price (8 decimals)

**Returns:**
- Price in INR/kWh with 8 decimal places

#### `isPriceStale() → bool`
Checks if price data is stale

#### `updatePriceFeed(address newFeed)`
Updates Chainlink feed address (admin only)

### Events

```solidity
event PriceUpdated(uint256 price, uint256 timestamp);
event PriceFeedUpdated(address oldFeed, address newFeed);
event StalePriceDetected(uint256 lastUpdate, uint256 threshold);
```

---

## 5. DynamicPricing

**Purpose**: Time-of-use and demand-based pricing

### Pricing Tiers

| Tier | Hours (IST) | Multiplier |
|------|-------------|------------|
| Off-Peak | 22:00-06:00 | 0.8x |
| Shoulder | 06:00-10:00, 14:00-17:00 | 1.0x |
| Peak | 10:00-14:00, 17:00-22:00 | 1.3x |

### Functions

#### `calculatePrice(uint256 quantity, uint256 duration) → uint256`
Calculates price for energy trade

**Parameters:**
- `quantity`: Energy amount in kWh (wei)
- `duration`: Delivery window in seconds

**Returns:**
- Total price in SHAKTI (wei)

#### `getDemandMultiplier() → uint256`
Returns current demand multiplier (basis points)

#### `getCurrentTier() → uint8`
Returns current pricing tier (0=off-peak, 1=shoulder, 2=peak)

### Events

```solidity
event DemandMultiplierUpdated(uint256 oldMultiplier, uint256 newMultiplier);
event GridStressDetected(uint256 frequency, uint8 severity);
```

---

## 6. EnergyAuction

**Purpose**: McAfee double auction for energy trading

### Constants

| Name | Value | Description |
|------|-------|-------------|
| `MIN_AUCTION_DURATION` | 5 minutes | Minimum round duration |
| `MAX_AUCTION_DURATION` | 60 minutes | Maximum round duration |
| `BATCH_SIZE` | 50 | Orders processed per batch |

### Structs

```solidity
struct Order {
    uint256 orderId;
    address user;
    uint256 quantity;      // kWh in wei
    uint256 price;         // SHAKTI/kWh in wei
    uint256 timestamp;
    uint256 deliveryWindow;
    OrderStatus status;    // Active, Matched, Cancelled
}

struct AuctionRound {
    uint256 startTime;
    uint256 endTime;
    uint256 clearingPrice;
    uint256 totalBidVolume;
    uint256 totalAskVolume;
    uint256 totalMatched;
    RoundStatus status;
}
```

### Functions

#### `startRound(uint256 duration)`
Starts new auction round (operator only)

**Parameters:**
- `duration`: Round duration in seconds

#### `placeBid(uint256 quantity, uint256 maxPrice, uint256 deliveryWindow)`
Places buy order

**Parameters:**
- `quantity`: kWh to buy (wei)
- `maxPrice`: Maximum price willing to pay (wei)
- `deliveryWindow`: Acceptable delivery time in seconds

**Requirements:**
- Token approval for quantity × maxPrice
- Price within bounds

#### `placeAsk(uint256 quantity, uint256 minPrice, uint256 deliveryWindow)`
Places sell order

**Parameters:**
- `quantity`: kWh to sell (wei)
- `minPrice`: Minimum price to accept (wei)
- `deliveryWindow`: Delivery commitment time

#### `cancelOrder(uint256 orderId)`
Cancels active order

#### `matchOrders()`
Executes McAfee matching algorithm (operator only)

### Events

```solidity
event AuctionRoundStarted(uint256 indexed roundId, uint256 startTime, uint256 endTime);
event BidPlaced(uint256 indexed roundId, uint256 orderId, address bidder, uint256 quantity, uint256 price);
event AskPlaced(uint256 indexed roundId, uint256 orderId, address seller, uint256 quantity, uint256 price);
event OrderCancelled(uint256 indexed roundId, uint256 orderId, address user);
event OrdersMatched(uint256 indexed roundId, uint256 matchCount, uint256 clearingPrice, uint256 totalVolume);
event AuctionRoundEnded(uint256 indexed roundId, uint256 totalBids, uint256 totalAsks, uint256 matchedVolume);
```

---

## 7. EnergyEscrow

**Purpose**: Secure trade settlement

### Constants

| Name | Value | Description |
|------|-------|-------------|
| `PLATFORM_FEE` | 200 (2%) | Platform fee in basis points |
| `FEE_BURN` | 3000 (30%) | Portion of fee burned |
| `DISPUTE_WINDOW` | 24 hours | Time to raise dispute |

### Functions

#### `createEscrow(uint256 tradeId, address seller, address buyer, uint256 amount)`
Creates escrow for matched trade (auction only)

#### `releaseEscrow(uint256 escrowId)`
Releases funds after successful delivery

#### `raiseDispute(uint256 escrowId, string reason)`
Raises dispute within dispute window

#### `resolveDispute(uint256 escrowId, address winner)`
Resolves dispute (arbiter only)

### Events

```solidity
event EscrowCreated(uint256 indexed escrowId, uint256 tradeId, address seller, address buyer, uint256 amount);
event EscrowReleased(uint256 indexed escrowId, address seller, uint256 amount, uint256 fee);
event DisputeRaised(uint256 indexed escrowId, address disputer, string reason);
event DisputeResolved(uint256 indexed escrowId, address winner, uint256 amount);
```

---

## 8. Treasury

**Purpose**: Protocol fee collection and management

### Constants

| Name | Value | Description |
|------|-------|-------------|
| `MAX_SIGNERS` | 5 | Required number of multisig signers |
| `REQUIRED_SIGNATURES` | 3 | Signatures needed for withdrawal |

### Functions

#### `deposit(uint256 amount)`
Deposits tokens to treasury

#### `proposeWithdrawal(address to, uint256 amount, string reason) → uint256`
Creates withdrawal proposal (signer only)

#### `approveWithdrawal(uint256 proposalId)`
Approves withdrawal (signer only)

#### `executeWithdrawal(uint256 proposalId)`
Executes approved withdrawal

### Events

```solidity
event Deposited(address indexed from, uint256 amount);
event WithdrawalProposed(uint256 indexed proposalId, address to, uint256 amount);
event WithdrawalApproved(uint256 indexed proposalId, address signer);
event WithdrawalExecuted(uint256 indexed proposalId, address to, uint256 amount);
```

---

## 9. ReputationSystem

**Purpose**: User reputation and tier management

### Constants

| Name | Value | Description |
|------|-------|-------------|
| `STARTING_REPUTATION` | 500 | Initial score |
| `MAX_REPUTATION` | 1000 | Maximum score |
| `MIN_REPUTATION` | 0 | Minimum score |

### Tier Thresholds

| Tier | Score Range | Fee Discount |
|------|-------------|--------------|
| Bronze | 0-299 | 0% |
| Silver | 300-499 | 20% |
| Gold | 500-699 | 40% |
| Platinum | 700-849 | 60% |
| Diamond | 850-1000 | 75% |

### Functions

#### `updateReputation(address user, int256 change, string reason)`
Updates user reputation (reporter only)

#### `getReputation(address user) → uint256`
Returns user's current reputation score

#### `getUserTier(address user) → uint8`
Returns user's tier (0-4)

#### `getFeeDiscount(address user) → uint256`
Returns fee discount in basis points

### Events

```solidity
event ReputationUpdated(address indexed user, uint256 oldScore, uint256 newScore, string reason);
event TierChanged(address indexed user, uint8 oldTier, uint8 newTier);
```

---

## 10. EnergyVerification

**Purpose**: Delivery verification and dispute resolution

### Constants

| Name | Value | Description |
|------|-------|-------------|
| `DELIVERY_WINDOW` | 4 hours | Time for delivery |
| `QUANTITY_TOLERANCE` | 500 (5%) | Acceptable variance |
| `NON_DELIVERY_SLASH` | 1000 (10%) | Penalty for failure |

### Verification Methods

| Method | Description |
|--------|-------------|
| DISCOMAttestation | Signed attestation from utility |
| SmartMeterOracle | Chainlink Functions reading |
| PeerAttestation | Buyer confirmation (small trades) |

### Functions

#### `registerTrade(uint256 tradeId, address seller, address buyer, uint256 quantity, uint256 value, address discom)`
Registers trade for verification (escrow only)

#### `reportDeliveryWithDISCOM(uint256 tradeId, uint256 deliveredQuantity, bytes signature)`
Reports delivery with DISCOM attestation

#### `raiseNonDelivery(uint256 tradeId)`
Raises non-delivery dispute (buyer only)

#### `resolveDelivery(uint256 tradeId, uint8 resolution, uint256 partialQuantity)`
Resolves dispute (arbiter only)

### Events

```solidity
event TradeRegistered(uint256 indexed tradeId, address seller, address buyer, uint256 quantity);
event DeliveryReported(uint256 indexed tradeId, address reporter, uint256 deliveredQuantity);
event DeliveryConfirmed(uint256 indexed tradeId, address confirmer);
event DeliveryDisputed(uint256 indexed tradeId, address disputer, string reason);
event SlashApplied(uint256 indexed tradeId, address user, uint256 amount, string reason);
```

---

## 11. ShaktiGovernor

**Purpose**: On-chain governance

### Parameters

| Name | Value | Description |
|------|-------|-------------|
| `votingDelay` | 1 block | Delay before voting starts |
| `votingPeriod` | 50400 blocks (~7 days) | Voting duration |
| `proposalThreshold` | 100,000 SHAKTI | Tokens needed to propose |
| `quorumNumerator` | 4% | Minimum participation |

### Functions

#### `propose(address[] targets, uint256[] values, bytes[] calldatas, string description) → uint256`
Creates governance proposal

#### `castVote(uint256 proposalId, uint8 support)`
Casts vote (0=Against, 1=For, 2=Abstain)

#### `queue(address[] targets, uint256[] values, bytes[] calldatas, bytes32 descriptionHash)`
Queues successful proposal

#### `execute(address[] targets, uint256[] values, bytes[] calldatas, bytes32 descriptionHash)`
Executes queued proposal

### Proposal States

| State | Value | Description |
|-------|-------|-------------|
| Pending | 0 | Waiting for voting delay |
| Active | 1 | Voting in progress |
| Canceled | 2 | Proposal canceled |
| Defeated | 3 | Did not reach quorum or failed |
| Succeeded | 4 | Passed, awaiting queue |
| Queued | 5 | In timelock |
| Expired | 6 | Timelock expired |
| Executed | 7 | Successfully executed |

---

## 12. TimelockController

**Purpose**: Delayed execution of governance actions

### Constants

| Name | Value | Description |
|------|-------|-------------|
| `minDelay` | 48 hours | Minimum execution delay |

### Roles

| Role | Description |
|------|-------------|
| `PROPOSER_ROLE` | Can schedule operations |
| `EXECUTOR_ROLE` | Can execute ready operations |
| `CANCELLER_ROLE` | Can cancel pending operations |

### Functions

#### `schedule(address target, uint256 value, bytes data, bytes32 predecessor, bytes32 salt, uint256 delay)`
Schedules operation

#### `execute(address target, uint256 value, bytes data, bytes32 predecessor, bytes32 salt)`
Executes ready operation

#### `cancel(bytes32 id)`
Cancels pending operation

---

## Error Codes

All contracts use custom errors for gas efficiency:

```solidity
// Common errors
error ZeroAddress();
error ZeroAmount();
error Unauthorized();
error InvalidParameter();
error AlreadyExists();
error NotFound();
error Expired();
error NotReady();

// Contract-specific errors
error InsufficientBalance();
error LockNotExpired();
error OrderNotActive();
error AuctionClosed();
error PriceOutOfBounds();
error DeliveryWindowExpired();
error DisputeWindowExpired();
```

---

## Gas Estimates

| Operation | Estimated Gas |
|-----------|---------------|
| Token transfer | ~65,000 |
| Stake tokens | ~150,000 |
| Place bid/ask | ~180,000 |
| Match orders (per pair) | ~200,000 |
| Release escrow | ~120,000 |
| Report delivery | ~100,000 |
| Cast vote | ~80,000 |

---

*Document Version: 1.0*
*Last Updated: December 2024*
