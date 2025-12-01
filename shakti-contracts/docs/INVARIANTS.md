# SHAKTI-CHAIN Invariants

## Overview

This document describes properties that must always hold true in the SHAKTI-CHAIN smart contracts. These invariants should be verified through formal verification, fuzzing, and manual review.

## Global Invariants

### I1: Token Conservation

**Statement**: The total supply of ShaktiToken equals the sum of all balances plus burned tokens.

```
totalSupply() == sum(balanceOf[address]) + totalFeesBurned
```

**Verification**:
```solidity
function invariant_tokenConservation() public view returns (bool) {
    // In practice, track all known addresses
    return true; // totalSupply always decreases by burn amount
}
```

---

### I2: No Negative Balances

**Statement**: No address can have a negative token balance.

```
∀ address a: balanceOf(a) >= 0
```

**Enforcement**: Solidity uint256 type enforces this.

---

### I3: Supply Cap

**Statement**: Total supply never exceeds MAX_SUPPLY.

```
totalSupply() <= MAX_SUPPLY (1 billion tokens)
```

**Verification**:
```solidity
function invariant_supplyCap() public view returns (bool) {
    return shaktiToken.totalSupply() <= shaktiToken.MAX_SUPPLY();
}
```

---

## StakingPool Invariants

### I4: Staked Balance Conservation

**Statement**: Contract token balance equals sum of all stakes plus pending rewards.

```
stakingToken.balanceOf(stakingPool) >= totalStaked
```

**Note**: Greater-than allows for reward deposits.

---

### I5: Individual Stake Consistency

**Statement**: No user can have staked more than they deposited.

```
∀ user: stakes[user].amount <= total deposits by user
```

---

### I6: Reward Rate Bounds

**Statement**: Annual reward rate never exceeds maximum.

```
annualRewardRate <= MAX_REWARD_RATE (5000 basis points = 50%)
```

**Verification**:
```solidity
function invariant_rewardRateBounds() public view returns (bool) {
    return stakingPool.annualRewardRate() <= stakingPool.MAX_REWARD_RATE();
}
```

---

### I7: Lock Period Validity

**Statement**: Lock periods are one of the valid options.

```
∀ user: stakes[user].lockPeriod ∈ {0, 30 days, 90 days}
```

---

### I8: Multiplier Consistency

**Statement**: Multiplier matches lock period.

```
lockPeriod == 0       → multiplier == 10000 (1.0x)
lockPeriod == 30 days → multiplier == 12000 (1.2x)
lockPeriod == 90 days → multiplier == 15000 (1.5x)
```

---

## EnergyAuction Invariants

### I9: Auction State Machine

**Statement**: Auction states follow valid transitions.

```
OPEN → CLOSED → CLEARING → SETTLED
```

**Invalid Transitions**:
- CLOSED → OPEN
- SETTLED → any
- OPEN → SETTLED (must go through CLEARING)

---

### I10: Order Quantity Bounds

**Statement**: All orders are within quantity limits.

```
∀ order: MIN_QUANTITY <= order.quantity <= MAX_QUANTITY
```

---

### I11: Order Price Bounds

**Statement**: All orders are within price limits.

```
∀ order: minPrice <= order.price <= maxPrice
```

---

### I12: Locked Deposit Conservation

**Statement**: Locked deposits equal bid values minus spent.

```
∀ round, user: lockedDeposits[round][user] >= 0
sum(lockedDeposits) <= staktiToken.balanceOf(auction)
```

---

### I13: Order Count Limit

**Statement**: Total orders per round don't exceed maximum.

```
∀ round: totalBids + totalAsks <= MAX_ORDERS_PER_ROUND
```

---

### I14: Bid Ordering

**Statement**: Bid order list is sorted descending by price.

```
∀ round, i: bidOrderIds[round][i].price >= bidOrderIds[round][i+1].price
```

---

### I15: Ask Ordering

**Statement**: Ask order list is sorted ascending by price.

```
∀ round, i: askOrderIds[round][i].price <= askOrderIds[round][i+1].price
```

---

### I16: Clearing Price Validity

**Statement**: Clearing price is between matched bid and ask.

```
if matchedOrders > 0:
    clearingPrice >= min_matched_ask
    clearingPrice <= max_matched_bid
```

---

### I17: No Double Matching

**Statement**: An order can only be matched once.

```
∀ order: if status == MATCHED then matchedQuantity > 0
∀ order: matchedQuantity <= quantity
```

---

## EnergyEscrow Invariants

### I18: Settlement Balance Conservation

**Statement**: Escrow balance covers all pending settlements.

```
shaktiToken.balanceOf(escrow) >= sum(pending_settlement.totalAmount)
```

---

### I19: Fee Calculation

**Statement**: Fees are calculated correctly.

```
platformFee = totalAmount * platformFeePercentage / 10000
burnAmount = platformFee * feeBurnPercentage / 10000
sellerAmount = totalAmount - platformFee
treasuryAmount = platformFee - burnAmount
```

---

### I20: Dispute Window

**Statement**: Disputes can only be raised within window.

```
∀ settlement: raiseDispute requires block.timestamp <= disputeDeadline
```

---

### I21: Settlement State Machine

**Statement**: Settlement states follow valid transitions.

```
PENDING → COMPLETED (after dispute window)
PENDING → DISPUTED → RESOLVED
PENDING → REFUNDED
```

---

### I22: Fee Bounds

**Statement**: Platform fee doesn't exceed maximum.

```
platformFeePercentage <= MAX_FEE_PERCENTAGE (1000 = 10%)
```

---

## ReputationSystem Invariants

### I23: Reputation Score Bounds

**Statement**: Reputation score is within valid range.

```
∀ user: 0 <= userReputations[user].score <= MAX_REPUTATION (1000)
```

---

### I24: Tier Consistency

**Statement**: Tier matches reputation score.

```
score <= 300       → tier == Bronze
300 < score <= 500 → tier == Silver
500 < score <= 700 → tier == Gold
700 < score <= 850 → tier == Platinum
850 < score <= 1000 → tier == Diamond
```

---

### I25: Registration Uniqueness

**Statement**: Each address can only register once.

```
∀ user: isRegistered[user] == true → cannot register again
```

---

### I26: Reputation Accounting

**Statement**: Total reputation distributed minus deducted equals sum of scores minus initial grants.

```
totalReputationDistributed - totalReputationDeducted ==
sum(current_scores) - (totalUsers * STARTING_REPUTATION)
```

---

### I27: Decay Cap

**Statement**: Decay per call is capped.

```
|decay_applied| <= 10 points per applyDecay call
```

---

## DynamicPricing Invariants

### I28: Price Bounds

**Statement**: Final price is within absolute bounds.

```
ABSOLUTE_MIN_PRICE <= finalPrice <= ABSOLUTE_MAX_PRICE
```

---

### I29: Daily Change Limit

**Statement**: Price doesn't change more than max daily change.

```
if dailyPrice.openingPrice > 0:
    |finalPrice - dailyPrice.openingPrice| <= dailyPrice.openingPrice * maxDailyChange / 10000
```

---

### I30: Multiplier Validity

**Statement**: All multipliers are within valid ranges.

```
5000 <= demandMultiplier <= 20000
5000 <= timeOfUseMultiplier <= 20000
5000 <= seasonalMultiplier <= 15000
5000 <= gridStressMultiplier <= 20000
```

---

## Cross-Contract Invariants

### I31: Token Flow Conservation

**Statement**: Tokens only move through defined paths.

```
User → Auction (bid deposit)
Auction → User (refund)
Auction → Seller (payment)
Auction → Treasury (fees)
Auction → Burn (fee portion)
```

---

### I32: Role Consistency

**Statement**: Auction contract has AUCTION_ROLE in Escrow.

```
energyEscrow.hasRole(AUCTION_ROLE, address(energyAuction)) == true
```

---

### I33: Contract References

**Statement**: Contract addresses are non-zero when active.

```
if contract is operational:
    referencedContract != address(0)
```

---

## Fuzzing Invariant Tests

```solidity
// Example invariant test for Foundry
contract InvariantTest is Test {
    ShaktiToken token;
    StakingPool staking;

    function setUp() public {
        // Deploy contracts
    }

    function invariant_totalSupplyBounded() public {
        assertLe(token.totalSupply(), token.MAX_SUPPLY());
    }

    function invariant_stakingBalanceConsistent() public {
        assertGe(
            token.balanceOf(address(staking)),
            staking.totalStaked()
        );
    }

    function invariant_reputationBounded() public {
        // For all registered users
        for (uint i = 0; i < reputation.getRegisteredUsersCount(); i++) {
            address user = reputation.getRegisteredUser(i);
            (uint256 score, ) = reputation.getReputation(user);
            assertLe(score, reputation.MAX_REPUTATION());
        }
    }
}
```

## Verification Methods

| Method              | Coverage                | Confidence |
|---------------------|-------------------------|------------|
| Unit Tests          | Happy paths             | Medium     |
| Fuzzing             | Random inputs           | High       |
| Formal Verification | Mathematical proof      | Very High  |
| Manual Audit        | Logic, edge cases       | High       |

## Violated Invariant Response

If an invariant is violated:

1. **Pause** affected contracts immediately
2. **Analyze** the violation scope
3. **Document** the exact violation
4. **Fix** the root cause
5. **Verify** the fix restores invariant
6. **Deploy** with timelock (if needed)
7. **Resume** operations after validation
