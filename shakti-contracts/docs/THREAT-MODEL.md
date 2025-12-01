# SHAKTI-CHAIN Threat Model

## Overview

This document describes potential attack vectors and their mitigations for the SHAKTI-CHAIN V2G trading platform.

## Attack Surface

```
                           ┌──────────────────┐
                           │    Attacker      │
                           └────────┬─────────┘
                                    │
         ┌──────────────────────────┼──────────────────────────┐
         │                          │                          │
         ▼                          ▼                          ▼
┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐
│  Smart Contract │      │     Oracle      │      │    Frontend     │
│    Exploits     │      │  Manipulation   │      │    Attacks      │
└─────────────────┘      └─────────────────┘      └─────────────────┘
```

## Threat Categories

### 1. Smart Contract Exploits

#### 1.1 Reentrancy Attacks

**Threat**: Recursive calls to drain funds.

**Attack Vector**:
```
Attacker.receive() -> StakingPool.unstake() -> token.transfer() -> Attacker.receive() ...
```

**Mitigation**:
- `ReentrancyGuard` on all external state-changing functions
- CEI (Checks-Effects-Interactions) pattern
- SafeERC20 for token transfers

**Residual Risk**: Low - comprehensive protection implemented.

---

#### 1.2 Integer Overflow/Underflow

**Threat**: Manipulate balances through arithmetic bugs.

**Attack Vector**:
```solidity
// Old Solidity: balance = balance - amount; // Underflows if amount > balance
```

**Mitigation**:
- Solidity 0.8.24 with built-in overflow protection
- `unchecked` only used where mathematically safe

**Residual Risk**: Very Low - compiler-enforced.

---

#### 1.3 Access Control Bypass

**Threat**: Unauthorized access to privileged functions.

**Attack Vector**:
1. Exploit missing access modifier
2. Role escalation through grant/revoke bugs
3. `tx.origin` authentication bypass

**Mitigation**:
- OpenZeppelin AccessControl
- All admin functions require specific roles
- No `tx.origin` used

**Residual Risk**: Low - standardized implementation.

---

#### 1.4 Flash Loan Attacks

**Threat**: Borrow large amounts to manipulate market.

**Attack Scenarios**:

| Target          | Attack                                | Mitigation                    |
|-----------------|---------------------------------------|-------------------------------|
| StakingPool     | Flash stake for rewards               | Time-weighted rewards, locks  |
| EnergyAuction   | Manipulate clearing price             | Deposits locked during round  |
| ReputationSystem| Instant reputation gain               | Stake requirement, time decay |
| DynamicPricing  | Oracle price manipulation             | Price bounds, rate limits     |

**Residual Risk**: Low-Medium - economic constraints prevent profitability.

---

### 2. Economic Attacks

#### 2.1 Auction Manipulation

**Threat**: Game the auction mechanism for profit.

**Attack Vectors**:
1. **Wash Trading**: Self-trade to manipulate prices
2. **Order Book Spoofing**: Place/cancel orders to mislead
3. **Front-Running**: Submit better order after seeing mempool

**Mitigations**:
- McAfee uniform clearing price (no execution advantage)
- Cancellation only during OPEN state
- Time-bounded rounds limit manipulation window
- Minimum order quantities prevent dust manipulation

**Residual Risk**: Medium - inherent to any auction system.

---

#### 2.2 Price Oracle Manipulation

**Threat**: Corrupt price feeds for profit.

**Attack Vectors**:
1. Compromise oracle data source
2. Flashloan to manipulate DEX prices
3. Block timestamp manipulation

**Mitigations**:
- Price bounds (absolute min/max)
- Daily change limits (20%)
- Multiple oracle sources (recommended)
- On-chain validation of data staleness

**Residual Risk**: Medium - external dependency.

---

#### 2.3 Stake Grinding

**Threat**: Optimize stake timing for maximum rewards.

**Attack Vector**:
```
1. Observe reward rate changes
2. Stake right before increase
3. Unstake right before decrease
```

**Mitigations**:
- Minimum stake amounts
- Lock periods with multipliers
- Time-weighted reward calculation
- Governance timelocks on rate changes (recommended)

**Residual Risk**: Low - incentive aligned with long-term staking.

---

### 3. Denial of Service (DoS)

#### 3.1 Gas Griefing

**Threat**: Make functions too expensive to execute.

**Attack Vectors**:
1. Fill order book with max orders
2. Create many small stakes
3. Register many reputation accounts

**Mitigations**:
- `MAX_ORDERS_PER_ROUND = 500`
- `BATCH_SIZE = 50` for clearing
- `MINIMUM_STAKE = 100 SHAKTI`
- `MIN_QUANTITY = 1000 Wh`

**Residual Risk**: Low - bounded by design.

---

#### 3.2 Block Stuffing

**Threat**: Delay transactions by filling blocks.

**Attack Vector**: Submit high-gas transactions to prevent others.

**Mitigations**:
- Polygon's low block time (2s)
- Time-bounded auctions allow recovery
- Emergency pause available

**Residual Risk**: Low - economically expensive attack.

---

#### 3.3 Griefing via External Calls

**Threat**: Malicious contract causes revert.

**Attack Vector**:
```solidity
// Attacker contract
receive() external payable {
    revert("griefing");
}
```

**Mitigations**:
- No ETH transfers (SHAKTI token only)
- SafeERC20 handles non-standard tokens
- Pull pattern for withdrawals

**Residual Risk**: Very Low.

---

### 4. Governance Attacks

#### 4.1 Admin Key Compromise

**Threat**: Attacker gains control of admin keys.

**Impact**:
- Pause all contracts
- Change fee rates
- Upgrade to malicious implementation
- Drain treasury

**Mitigations**:
- Multi-sig for admin roles (recommended)
- Timelock on critical changes (recommended)
- Role separation (different keys for different functions)

**Residual Risk**: High if single key, Low with multi-sig.

---

#### 4.2 Malicious Upgrade

**Threat**: Deploy malicious contract upgrade.

**Attack Vector**:
1. Gain upgrade authority
2. Deploy malicious implementation
3. Call `upgradeTo()`

**Mitigations**:
- `_authorizeUpgrade` requires admin role
- Timelock on upgrades (recommended)
- Proxy admin separation
- Transparent upgrade process

**Residual Risk**: Medium - requires governance reform.

---

### 5. Front-End Attacks

#### 5.1 Phishing

**Threat**: Fake frontend steals private keys.

**Mitigations**:
- ENS/DNS verification
- Contract address verification in docs
- Wallet connect best practices

**Residual Risk**: Medium - user education required.

---

#### 5.2 Man-in-the-Middle

**Threat**: Intercept and modify transactions.

**Mitigations**:
- HTTPS enforcement
- Transaction simulation in wallet
- EIP-712 typed signing

**Residual Risk**: Low with proper infrastructure.

---

### 6. MEV (Miner Extractable Value)

#### 6.1 Transaction Ordering

**Threat**: Validators reorder for profit.

**Scenarios**:
| MEV Type        | Risk in SHAKTI                       |
|-----------------|--------------------------------------|
| Sandwich Attack | Low - uniform clearing price         |
| Back-running    | Low - no immediate price impact      |
| Front-running   | Medium - order visibility            |

**Mitigations**:
- Batch auction (all orders execute at same price)
- Private transaction pools (Flashbots, etc.)
- Minimum order sizes

**Residual Risk**: Low-Medium.

---

## Risk Matrix

| Threat                    | Likelihood | Impact   | Risk Level | Status      |
|---------------------------|------------|----------|------------|-------------|
| Reentrancy                | Low        | Critical | Medium     | Mitigated   |
| Integer Overflow          | Very Low   | High     | Low        | Mitigated   |
| Access Control Bypass     | Low        | Critical | Medium     | Mitigated   |
| Flash Loan Attack         | Medium     | High     | Medium     | Mitigated   |
| Auction Manipulation      | Medium     | Medium   | Medium     | Partial     |
| Oracle Manipulation       | Medium     | High     | Medium     | Partial     |
| Gas Griefing              | Low        | Low      | Low        | Mitigated   |
| Admin Key Compromise      | Low        | Critical | High       | Needs Action|
| Malicious Upgrade         | Low        | Critical | High       | Needs Action|
| MEV Extraction            | Medium     | Low      | Low-Medium | Partial     |

## Recommendations

### Critical Priority

1. **Multi-Signature Admin**
   - Deploy Gnosis Safe
   - Transfer admin roles
   - 3-of-5 threshold recommended

2. **Timelock Controller**
   - 48-hour delay on parameter changes
   - 7-day delay on upgrades

### High Priority

3. **Oracle Improvements**
   - Multiple price sources
   - TWAP for price feeds
   - Fallback mechanisms

4. **Monitoring**
   - Set up Tenderly/Forta monitors
   - Alert on unusual activities
   - Track large transactions

### Medium Priority

5. **Bug Bounty Program**
   - Immunefi or similar
   - Clear scope and rewards
   - Responsible disclosure process

6. **Rate Limiting**
   - Per-address order limits
   - Cooldowns on certain operations

## Incident Response Plan

### 1. Detection
- Automated monitoring alerts
- Community reports
- Audit findings

### 2. Assessment
- Severity classification
- Funds at risk calculation
- Attack vector analysis

### 3. Response
```
IF severity = CRITICAL:
    PAUSE all contracts
    ACTIVATE circuit breaker
    NOTIFY community
    PREPARE fix
ELSE IF severity = HIGH:
    PREPARE fix
    NOTIFY security council
    PLAN deployment
ELSE:
    DOCUMENT issue
    SCHEDULE fix
```

### 4. Recovery
- Deploy fix
- Verify security
- Unpause contracts
- Post-mortem report
