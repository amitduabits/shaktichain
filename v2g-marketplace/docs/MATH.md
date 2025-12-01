# Mathematical Foundations

This document explains the economic mechanisms and mathematical models underlying the V2G Marketplace.

---

## Table of Contents

- [McAfee Double Auction](#mcafee-double-auction)
- [Nash Equilibrium Analysis](#nash-equilibrium-analysis)
- [SHAKTI Token Model](#shakti-token-model)
- [Demand Modeling](#demand-modeling)
- [Agent Decision Model](#agent-decision-model)
- [References](#references)

---

## McAfee Double Auction

The V2G Marketplace uses the McAfee double auction mechanism for energy trading. This mechanism is **incentive-compatible**, meaning participants are incentivized to bid their true valuations.

### Overview

In a double auction:
- **Buyers** submit bids specifying quantity and maximum price they're willing to pay
- **Sellers** submit asks specifying quantity and minimum price they're willing to accept
- The **auctioneer** (market) determines a clearing price and which trades execute

### Algorithm

**Step 1: Sort Bids**

```
Buyers:  Sort in DESCENDING order by price (highest first)
Sellers: Sort in ASCENDING order by price (lowest first)
```

Let:
- `b₁ ≥ b₂ ≥ ... ≥ bₙ` be buyer bids
- `s₁ ≤ s₂ ≤ ... ≤ sₘ` be seller asks

**Step 2: Find Critical Index k**

Find the largest index `k` such that:
```
bₖ ≥ sₖ  (buyer willing to pay at least seller's ask)
```

**Step 3: Determine Clearing Price and Quantity**

**Case A**: If `k+1` exists and `bₖ₊₁ ≥ sₖ₊₁`:
```
Clearing Price p = (bₖ₊₁ + sₖ₊₁) / 2
Trade k units
```

**Case B**: Otherwise:
```
Clearing Price p = (bₖ + sₖ) / 2
Trade k-1 units
```

### Example

```
┌───────────────────────────────────────────────────────────────────┐
│                  McAfee Auction Example                           │
├───────────────────────────────────────────────────────────────────┤
│                                                                   │
│  INPUTS:                                                          │
│  ┌─────────────────┐    ┌─────────────────┐                      │
│  │  Buyer Bids     │    │  Seller Asks    │                      │
│  ├─────────────────┤    ├─────────────────┤                      │
│  │  EV1: ₹12/kWh   │    │  EV5: ₹6/kWh    │                      │
│  │  EV2: ₹11/kWh   │    │  EV6: ₹7/kWh    │                      │
│  │  EV3: ₹10/kWh   │    │  EV7: ₹8/kWh    │                      │
│  │  EV4: ₹9/kWh    │    │  EV8: ₹9/kWh    │                      │
│  │  EV5: ₹7/kWh    │    │  EV9: ₹11/kWh   │                      │
│  └─────────────────┘    └─────────────────┘                      │
│                                                                   │
│  STEP 1: After Sorting                                            │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │  i    Buyer bᵢ    Seller sᵢ    bᵢ ≥ sᵢ?                    │ │
│  │  1      ₹12          ₹6          ✓ (gain-from-trade)        │ │
│  │  2      ₹11          ₹7          ✓                          │ │
│  │  3      ₹10          ₹8          ✓                          │ │
│  │  4      ₹9           ₹9          ✓ ← Critical index k=4     │ │
│  │  5      ₹7           ₹11         ✗ (no trade possible)      │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  STEP 2: k = 4 (last index where bₖ ≥ sₖ)                        │
│                                                                   │
│  STEP 3: Check k+1 = 5                                            │
│          b₅ = ₹7, s₅ = ₹11                                       │
│          b₅ < s₅, so we use Case B                                │
│                                                                   │
│  RESULT:                                                          │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │  Clearing Price p = (b₄ + s₄) / 2 = (₹9 + ₹9) / 2 = ₹9.00  │ │
│  │  Trades Executed: 3 (indices 1, 2, 3)                       │ │
│  │  Index 4 excluded to ensure budget balance                   │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                   │
└───────────────────────────────────────────────────────────────────┘
```

### Properties

The McAfee mechanism guarantees:

| Property | Description |
|----------|-------------|
| **Incentive Compatibility** | Truthful bidding is a dominant strategy |
| **Individual Rationality** | No participant is worse off than not participating |
| **Budget Balance** | Payments from buyers ≥ payments to sellers |
| **Efficiency** | Near-optimal allocation (at most one unit lost) |

### Mathematical Formulation

**Buyer's Utility**:
```
U_buyer = v_buyer - p   if matched
        = 0             otherwise

where v_buyer is true valuation, p is clearing price
```

**Seller's Utility**:
```
U_seller = p - c_seller   if matched
         = 0              otherwise

where c_seller is true cost
```

**Incentive Compatibility Proof Sketch**:

For a buyer with true value `v`:
- If bidding `b > v`: Risk winning at price `p > v` (negative utility)
- If bidding `b < v`: Risk losing trade that would have positive utility
- Bidding `b = v`: Maximizes expected utility

---

## Nash Equilibrium Analysis

### Setup

Consider a V2G market with:
- N prosumer agents (EV owners)
- Each agent i has:
  - True valuation `vᵢ` for energy
  - Battery state of charge `SOCᵢ`
  - Strategy space: bid price `bᵢ`

### Nash Equilibrium in McAfee Auction

**Theorem**: In the McAfee double auction, truthful bidding (`bᵢ = vᵢ`) is a **weakly dominant strategy Nash equilibrium**.

**Intuition**:

```
┌───────────────────────────────────────────────────────────────────┐
│                 Why Truthful Bidding is Optimal                   │
├───────────────────────────────────────────────────────────────────┤
│                                                                   │
│  Consider a buyer with true value v = ₹10/kWh                    │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │  Strategy 1: Bid truthfully (b = ₹10)                       │ │
│  │                                                             │ │
│  │  • If clearing price p ≤ ₹10: WIN, utility = 10 - p ≥ 0    │ │
│  │  • If clearing price p > ₹10: LOSE, utility = 0            │ │
│  │                                                             │ │
│  │  → Always non-negative utility                              │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │  Strategy 2: Overbid (b = ₹12)                              │ │
│  │                                                             │ │
│  │  • May win when p is between ₹10 and ₹12                   │ │
│  │  • Utility = 10 - p < 0 (NEGATIVE!)                        │ │
│  │                                                             │ │
│  │  → Risk of negative utility                                 │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │  Strategy 3: Underbid (b = ₹8)                              │ │
│  │                                                             │ │
│  │  • May lose when p is between ₹8 and ₹10                   │ │
│  │  • Miss profitable trades where utility = 10 - p > 0        │ │
│  │                                                             │ │
│  │  → Foregone positive utility                                │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  CONCLUSION: Truthful bidding (b = v) weakly dominates           │
│  all other strategies                                             │
│                                                                   │
└───────────────────────────────────────────────────────────────────┘
```

### Market Equilibrium

At equilibrium, the market clearing price reflects:

```
p* = f(Supply, Demand, Time, Season, Region)
```

Where price discovery occurs through:

1. **Demand curve**: Aggregated buyer bids
2. **Supply curve**: Aggregated seller asks
3. **Intersection**: Market clearing price

```
Price
  │
₹12│                     ╱
  │                   ╱
₹10│      Demand    ╱   Supply
  │        ╲      ╱
₹8 │         ╲  ╱  ← Equilibrium (p* = ₹8.50)
  │          ╳
₹6 │        ╱  ╲
  │      ╱      ╲
₹4 │    ╱
  └────────────────────────────────────────── Quantity
       100    200    300    400    500
```

---

## SHAKTI Token Model

The SHAKTI token is the native currency of the V2G Marketplace, with a velocity-based pricing model.

### Token Parameters

| Parameter | Symbol | Value | Description |
|-----------|--------|-------|-------------|
| Initial Supply | M₀ | 10,000,000 | Starting token supply |
| Initial Price | P₀ | ₹1.00 | Starting price per token |
| Base Velocity | V₀ | 12 | Annual turnover rate |
| Transaction Fee | φ | 2% | Fee on each transaction |
| Burn Rate | β | 30% | Portion of fees burned |
| Staking Reward | r | 8% | Annual staking APY |

### Price Model

The token price is determined by the **Equation of Exchange**:

```
M × V = P_E × Q
```

Where:
- M = Token supply in circulation
- V = Token velocity (turnover rate)
- P_E = Energy price (INR/kWh)
- Q = Energy quantity traded (kWh)

**Token Price Formula**:

```
        P_E × Q × 24
P_T = ─────────────────
      M × (1 - σ) × V
```

Where:
- P_T = Token price (INR)
- σ = Staking rate (portion of tokens staked)
- 24 = Hours per day (normalization factor)

### Velocity Model

Token velocity adjusts based on market conditions:

```
V = V₀ × (1 - σ)^0.5 × exp(-0.1 × Q/Q_max)
```

**Intuition**:
- Higher staking (σ) → Lower velocity (tokens move less)
- Higher trading volume (Q) → Lower velocity (tokens held for trading)

### Token Dynamics

```
┌───────────────────────────────────────────────────────────────────┐
│                    Token Flow Diagram                             │
├───────────────────────────────────────────────────────────────────┤
│                                                                   │
│                    ┌─────────────────┐                            │
│                    │   Total Supply  │                            │
│                    │    M = 10M      │                            │
│                    └────────┬────────┘                            │
│                             │                                     │
│              ┌──────────────┴──────────────┐                      │
│              │                             │                      │
│              ▼                             ▼                      │
│    ┌─────────────────┐           ┌─────────────────┐             │
│    │   Circulating   │           │     Staked      │             │
│    │   M × (1 - σ)   │           │     M × σ       │             │
│    └────────┬────────┘           └────────┬────────┘             │
│             │                             │                      │
│             │                             │ Rewards (8% APY)     │
│             │                             │ r × M × σ            │
│             ▼                             │                      │
│    ┌─────────────────┐                    │                      │
│    │  Transactions   │                    │                      │
│    │    Volume V     │◄───────────────────┘                      │
│    └────────┬────────┘                                           │
│             │                                                     │
│             │ Fee: 2% of transaction                              │
│             ▼                                                     │
│    ┌─────────────────┐                                           │
│    │   Fee Pool      │                                           │
│    │   φ × V = 2%V   │                                           │
│    └────────┬────────┘                                           │
│             │                                                     │
│      ┌──────┴──────┐                                             │
│      │             │                                             │
│      ▼             ▼                                             │
│  ┌───────┐    ┌───────┐                                          │
│  │ Burn  │    │Treasury│                                         │
│  │ 30%   │    │  70%   │                                         │
│  │ β×φ×V │    │(1-β)×φV│                                         │
│  └───┬───┘    └────────┘                                         │
│      │                                                            │
│      ▼                                                            │
│  ┌─────────────────┐                                             │
│  │   Destroyed     │  ← Deflationary pressure                    │
│  │   (Burned)      │                                             │
│  └─────────────────┘                                             │
│                                                                   │
└───────────────────────────────────────────────────────────────────┘
```

### Supply Dynamics

**Burn Mechanism**:
```
ΔM_burn = β × φ × Transaction_Volume
        = 0.30 × 0.02 × V
        = 0.006 × V  (0.6% of transaction volume burned)
```

**Mint Mechanism** (Staking Rewards):
```
ΔM_mint = r × M × σ / 365  (daily minting)
        = 0.08 × M × σ / 365
```

**Net Supply Change**:
```
dM/dt = ΔM_mint - ΔM_burn
```

If burning exceeds minting → **deflationary**
If minting exceeds burning → **inflationary**

### Example Calculation

```
Given:
  - Energy price P_E = ₹8/kWh
  - Daily volume Q = 10,000 kWh
  - Token supply M = 10,000,000
  - Staking rate σ = 40%
  - Velocity V = 10

Token Price:
  P_T = (8 × 10,000 × 24) / (10,000,000 × 0.6 × 10)
      = 1,920,000 / 60,000,000
      = ₹0.032 per token

Transaction in tokens:
  1 kWh @ ₹8 = 8 / 0.032 = 250 SHAKTI tokens
```

---

## Demand Modeling

The platform models realistic Indian electricity demand using multiplicative factors.

### Demand Formula

```
D(t, d, s, r) = D_base × H(t) × W(d) × S(s) × R(r)
```

Where:
- D_base = Base demand (MW)
- H(t) = Hourly multiplier
- W(d) = Day-of-week multiplier
- S(s) = Seasonal multiplier
- R(r) = Regional multiplier

### Hourly Profile H(t)

```
Hour │ Multiplier │ Description
─────┼────────────┼─────────────────────
0-5  │    0.5-0.6 │ Night (low demand)
6-9  │    1.1-1.5 │ Morning peak
10-16│    0.9-1.0 │ Daytime
17-21│    1.4-1.8 │ Evening peak (V2G opportunity!)
22-23│    0.8-0.9 │ Late evening
```

```
Demand
  │                      ▄▄▄▄▄
  │                    ▄█████████▄
1.8│                   █████████████
  │        ▄▄▄        ████████████████
1.4│      ▄████▄     ▄████████████████▄
  │    ▄████████▄   ██████████████████████
1.0│▄▄▄██████████▄▄████████████████████████▄▄
  │████████████████████████████████████████████
0.6│████████████████████████████████████████████
  └────────────────────────────────────────────────
    0  2  4  6  8  10 12 14 16 18 20 22 24   Hour
         Morning Peak        Evening Peak
```

### Day-of-Week Profile W(d)

| Day | Multiplier | Notes |
|-----|------------|-------|
| Monday-Friday | 1.10 | Business/industrial load |
| Saturday | 0.95 | Reduced commercial |
| Sunday | 0.85 | Lowest demand |

### Seasonal Profile S(s)

| Season | Months | Multiplier | Reason |
|--------|--------|------------|--------|
| Summer | Apr-Jun | 1.30 | AC, cooling load |
| Monsoon | Jul-Sep | 1.00 | Moderate |
| Post-Monsoon | Oct-Nov | 1.10 | Festival season |
| Winter | Dec-Mar | 0.95 | Lower cooling |

### Regional Profile R(r)

| Region | Multiplier | Notes |
|--------|------------|-------|
| Delhi | 1.25 | High industrial + AC |
| Mumbai | 1.15 | Commercial hub |
| Bangalore | 1.10 | IT sector load |
| Chennai | 1.20 | Industrial + hot climate |
| Kolkata | 1.05 | Moderate |
| Pune | 1.10 | Growing demand |
| Hyderabad | 1.10 | IT + industrial |
| Ahmedabad | 1.05 | Industrial |

### V2G Opportunity Windows

**Peak shaving opportunities** occur when demand multiplier > 1.4:

```
Time        │ Multiplier │ V2G Action
────────────┼────────────┼──────────────────
06:00-09:00 │   1.2-1.5  │ Moderate discharge
17:00-21:00 │   1.4-1.8  │ Maximum discharge!
Night       │   0.5-0.6  │ Charge EVs
```

---

## Agent Decision Model

Each prosumer agent makes autonomous trading decisions based on battery state and market conditions.

### Agent State

```
Agent State = {
  type: "residential" | "commercial" | "fleet",
  battery_capacity: 50 kWh (default),
  SOC: [0, 1],  // State of Charge
  valuation: ₹/kWh  // True value for energy
}
```

### Decision Function

```python
def decide_role(agent, hour):
    if agent.SOC < 0.2:
        return "BUYER"  # Must charge
    elif agent.SOC > 0.8:
        return "SELLER"  # Can sell
    elif hour in PEAK_HOURS:  # 17-21
        return "SELLER"  # V2G opportunity
    else:
        return "BUYER"  # Default: charge
```

### Bid Generation

```
Buyer Bid:
  price = valuation × (1 + noise)
  noise ~ Uniform(-0.05, +0.05)
  quantity = min(needed_kWh, max_buy_rate)

Seller Bid:
  price = cost × (1 + noise)
  noise ~ Uniform(-0.05, +0.05)
  quantity = min(available_kWh, max_sell_rate)
```

### Utility Functions

**Buyer Utility**:
```
U_buyer = (valuation - clearing_price) × quantity
        = surplus × quantity
```

**Seller Utility**:
```
U_seller = (clearing_price - cost) × quantity
         = profit × quantity
```

### Battery Dynamics

```
After buying quantity q:
  SOC_new = SOC + q / battery_capacity

After selling quantity q:
  SOC_new = SOC - q / battery_capacity

Constraints:
  0 ≤ SOC ≤ 1
  q ≤ max_charge_rate × Δt
  q ≤ max_discharge_rate × Δt
```

---

## References

### Academic Papers

1. **McAfee, R.P. (1992)**. "A Dominant Strategy Double Auction." *Journal of Economic Theory*, 56(2), 434-450.
   - Original McAfee double auction mechanism

2. **Vickrey, W. (1961)**. "Counterspeculation, Auctions, and Competitive Sealed Tenders." *Journal of Finance*, 16(1), 8-37.
   - Foundation for auction theory

3. **Myerson, R.B. & Satterthwaite, M.A. (1983)**. "Efficient Mechanisms for Bilateral Trading." *Journal of Economic Theory*, 29(2), 265-281.
   - Impossibility results for efficient trading mechanisms

### V2G Literature

4. **Kempton, W. & Tomić, J. (2005)**. "Vehicle-to-Grid Power Fundamentals." *Journal of Power Sources*, 144(1), 268-279.
   - V2G concept introduction

5. **Sortomme, E. & El-Sharkawi, M.A. (2012)**. "Optimal Scheduling of Vehicle-to-Grid Energy and Ancillary Services." *IEEE Transactions on Smart Grid*, 3(1), 351-359.
   - V2G optimization

### Token Economics

6. **Buterin, V. (2017)**. "Notes on Blockchain Governance." https://vitalik.ca
   - Token governance principles

7. **Samani, K. (2017)**. "Understanding Token Velocity." https://multicoin.capital
   - Velocity-based token pricing

---

## Formal Proofs

For rigorous mathematical proofs of:
- McAfee mechanism incentive compatibility
- Nash equilibrium existence and uniqueness
- Token price stability conditions
- Convergence properties of agent learning

Please refer to the companion LaTeX document: `proofs/v2g_formal_proofs.tex` (coming soon).

---

## Implementation Notes

The mathematical models are implemented in:

| Model | File | Key Functions |
|-------|------|---------------|
| McAfee Auction | `backend/core/auction/mcafee.py` | `clear_market()`, `find_critical_index()` |
| SHAKTI Token | `backend/core/token/shakti.py` | `compute_price()`, `compute_velocity()` |
| India Demand | `backend/core/demand/india_load.py` | `get_multiplier()`, `get_peak_hours()` |
| Prosumer Agent | `backend/core/agents/prosumer.py` | `decide_role()`, `generate_bid()` |
