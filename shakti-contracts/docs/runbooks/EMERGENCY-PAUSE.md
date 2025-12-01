# Emergency Pause Runbook

## Overview

This runbook describes the procedure for emergency pausing SHAKTI-CHAIN contracts when a critical security incident is detected.

**Severity:** Critical
**Response Time:** < 15 minutes
**Authorization:** Emergency Multisig (2/3)

---

## Quick Reference

### Pausable Contracts

| Contract | Pause Function | Required Role |
|----------|---------------|---------------|
| ShaktiToken | `pause()` | PAUSER_ROLE |
| StakingPool | `pause()` | PAUSER_ROLE |
| EnergyAuction | `pause()` | PAUSER_ROLE |
| EnergyEscrow | `pause()` | PAUSER_ROLE |
| EnergyVerification | `pause()` | PAUSER_ROLE |
| DynamicPricing | `pause()` | PAUSER_ROLE |

### Emergency Contacts

| Role | Primary | Phone | Telegram |
|------|---------|-------|----------|
| Security Lead | _______ | _______ | @_______ |
| Engineering Lead | _______ | _______ | @_______ |
| Emergency Signer 1 | _______ | _______ | @_______ |
| Emergency Signer 2 | _______ | _______ | @_______ |
| Emergency Signer 3 | _______ | _______ | @_______ |

---

## When to Pause

### Immediate Pause Required (No Approval Needed)
- Active exploit in progress
- Funds being drained
- Oracle manipulation detected
- Reentrancy attack observed

### Pause After Assessment (2/3 Multisig Required)
- Suspicious transaction patterns
- Potential vulnerability discovered
- Third-party dependency compromise
- Network-wide issues (Polygon outage)

---

## Pause Procedure

### Step 1: Assess the Situation (0-2 minutes)

```bash
# Check recent transactions
# Tenderly Dashboard: https://dashboard.tenderly.co/project/shakti-chain

# Check contract state
cast call <CONTRACT_ADDRESS> "paused()(bool)" --rpc-url $POLYGON_RPC
```

**Decision Point:**
- If active exploit: Proceed immediately to Step 2
- If suspected issue: Alert team, gather 2/3 signers

### Step 2: Initiate Emergency Pause (2-5 minutes)

#### Option A: Direct Pause (If you have PAUSER_ROLE)

```bash
# Set environment
export POLYGON_RPC="https://polygon-mainnet.g.alchemy.com/v2/YOUR_KEY"
export PRIVATE_KEY="your_private_key"

# Pause each contract
cd shakti-contracts

# Pause all contracts using the emergency script
npx hardhat run scripts/emergency/pause-all.ts --network polygon
```

#### Option B: Multisig Pause (Standard Procedure)

1. **Go to Gnosis Safe UI**
   - URL: https://app.safe.global/
   - Select Emergency Multisig

2. **Create New Transaction**
   - Click "New Transaction" > "Contract Interaction"
   - Enter contract address
   - Select `pause()` function
   - Submit transaction

3. **Collect Signatures**
   - Contact Signer 2 and Signer 3
   - Each signer confirms in Safe UI
   - Execute when 2/3 signatures collected

### Step 3: Verify Pause Status (5-10 minutes)

```bash
# Verify each contract is paused
npx hardhat run scripts/emergency/verify-pause.ts --network polygon
```

Expected output:
```
Checking pause status...
ShaktiToken: PAUSED
StakingPool: PAUSED
EnergyAuction: PAUSED
EnergyEscrow: PAUSED
EnergyVerification: PAUSED
DynamicPricing: PAUSED

All contracts paused successfully.
```

### Step 4: Communicate (10-15 minutes)

1. **Internal Communication**
   ```
   @channel EMERGENCY PAUSE ACTIVATED

   Time: [TIMESTAMP]
   Reason: [BRIEF DESCRIPTION]
   Contracts Paused: [LIST]
   Next Steps: Incident response in progress

   DO NOT UNPAUSE without team approval
   ```

2. **External Communication** (if public-facing)
   - Update status page
   - Post on Discord/Twitter
   - Template:
   ```
   SHAKTI-CHAIN is temporarily paused for security maintenance.
   Your funds are safe. We are investigating and will provide updates.
   ETA for resolution: [TIME]
   ```

---

## Post-Pause Actions

### Immediate (0-1 hour)
- [ ] Document timeline of events
- [ ] Identify affected transactions
- [ ] Assess scope of impact
- [ ] Begin root cause analysis

### Short-term (1-24 hours)
- [ ] Complete incident investigation
- [ ] Develop remediation plan
- [ ] Test fix on fork/testnet
- [ ] Prepare for unpause

### Before Unpause
- [ ] Root cause identified and fixed
- [ ] Fix tested on mainnet fork
- [ ] Security review of fix completed
- [ ] Team approval (3/5 Owner Multisig)
- [ ] Communication plan ready

---

## Unpause Procedure

### Prerequisites
- [ ] Incident resolved
- [ ] Fix deployed (if code change needed)
- [ ] Owner Multisig approval (3/5)
- [ ] Monitoring alerts verified

### Execute Unpause

```bash
# Via Gnosis Safe (recommended)
# 1. Create unpause transaction
# 2. Collect 3/5 signatures
# 3. Execute

# Or via script (if direct access)
npx hardhat run scripts/emergency/unpause-all.ts --network polygon
```

### Verify Unpause

```bash
npx hardhat run scripts/emergency/verify-pause.ts --network polygon
```

Expected output:
```
Checking pause status...
ShaktiToken: ACTIVE
StakingPool: ACTIVE
EnergyAuction: ACTIVE
EnergyEscrow: ACTIVE
EnergyVerification: ACTIVE
DynamicPricing: ACTIVE

All contracts active.
```

---

## Emergency Scripts

### scripts/emergency/pause-all.ts

```typescript
import { ethers, network } from "hardhat";
import { loadDeployment } from "../utils/deployment-helpers";

const PAUSABLE_CONTRACTS = [
  "ShaktiToken",
  "StakingPool",
  "EnergyAuction",
  "EnergyEscrow",
  "EnergyVerification",
  "DynamicPricing"
];

async function main() {
  console.log("EMERGENCY PAUSE - All Contracts");
  console.log("Network:", network.name);
  console.log("Time:", new Date().toISOString());
  console.log("");

  const [signer] = await ethers.getSigners();
  console.log("Executing as:", signer.address);

  for (const name of PAUSABLE_CONTRACTS) {
    const deployment = await loadDeployment(name);
    if (!deployment) {
      console.log(`${name}: NOT DEPLOYED`);
      continue;
    }

    const contract = await ethers.getContractAt(name, deployment.address);

    const isPaused = await contract.paused();
    if (isPaused) {
      console.log(`${name}: Already paused`);
      continue;
    }

    console.log(`Pausing ${name}...`);
    const tx = await contract.pause();
    await tx.wait();
    console.log(`${name}: PAUSED (tx: ${tx.hash})`);
  }

  console.log("\nEmergency pause complete.");
}

main().catch(console.error);
```

---

## Appendix: Pause Impact

### What Stops When Paused

| Contract | Blocked Functions |
|----------|------------------|
| ShaktiToken | transfer, transferFrom, approve |
| StakingPool | stake, unstake, claimRewards |
| EnergyAuction | placeBid, placeAsk, matchOrders |
| EnergyEscrow | createEscrow, releaseEscrow, dispute |
| EnergyVerification | registerTrade, reportDelivery |
| DynamicPricing | updatePrice |

### What Continues When Paused

- View functions (balances, states)
- Governor voting (if not paused)
- Timelock execution queue

---

## Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | _____ | _____ | Initial version |

---

*Last Updated: _______________*
*Next Review: _______________*
