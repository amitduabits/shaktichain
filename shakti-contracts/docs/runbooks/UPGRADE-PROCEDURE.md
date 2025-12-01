# Contract Upgrade Procedure

## Overview

This runbook describes the procedure for upgrading SHAKTI-CHAIN smart contracts. All contracts are immutable by design, requiring redeployment for upgrades.

**Note:** SHAKTI-CHAIN uses non-upgradeable contracts. "Upgrades" involve deploying new contracts and migrating state/permissions.

---

## Upgrade Types

### Type 1: Parameter Changes
- Changes to configurable parameters
- No new contract deployment needed
- Executed via governance or multisig

### Type 2: Bug Fixes
- Deploy new contract version
- Migrate users/state to new contract
- Deprecate old contract

### Type 3: Feature Additions
- Deploy new contracts
- Integrate with existing system
- Update references in dependent contracts

### Type 4: Full Migration
- Major version change
- Complete system redeploy
- Coordinated user migration

---

## Pre-Upgrade Checklist

### Code Review
- [ ] Changes reviewed by 2+ engineers
- [ ] Security review completed
- [ ] All tests passing
- [ ] Coverage requirements met (>90%)
- [ ] Gas optimization verified

### Testing
- [ ] Unit tests for new code
- [ ] Integration tests updated
- [ ] Mainnet fork testing completed
- [ ] Upgrade procedure tested on fork

### Documentation
- [ ] Code changes documented
- [ ] Migration guide prepared
- [ ] User communication drafted

### Approvals
- [ ] Engineering lead approval
- [ ] Security team approval
- [ ] Governance approval (if required)

---

## Type 1: Parameter Changes

### Via Governance (Standard)

For changes requiring governance vote:

1. **Create Proposal**
```typescript
// Example: Update auction min/max price
const targets = [energyAuction.address];
const values = [0];
const calldatas = [
  energyAuction.interface.encodeFunctionData("updatePriceBounds", [
    newMinPrice,
    newMaxPrice
  ])
];
const description = "Update EnergyAuction price bounds";

await governor.propose(targets, values, calldatas, description);
```

2. **Voting Period**
- Wait for voting delay (1 block)
- Community votes during voting period (50,400 blocks / ~7 days)
- Requires quorum (4% of total supply)

3. **Execute (after passed)**
```typescript
const descriptionHash = ethers.keccak256(ethers.toUtf8Bytes(description));
await governor.queue(targets, values, calldatas, descriptionHash);

// Wait for timelock delay (48 hours)
await governor.execute(targets, values, calldatas, descriptionHash);
```

### Via Multisig (Emergency)

For urgent parameter changes:

1. **Create Gnosis Safe Transaction**
   - Go to https://app.safe.global/
   - Select Owner Multisig
   - New Transaction > Contract Interaction
   - Enter contract and function details

2. **Collect Signatures (3/5)**
   - Contact multisig signers
   - Each signer reviews and signs

3. **Execute**
   - Once 3/5 signatures collected
   - Execute transaction

---

## Type 2: Bug Fix Deployment

### Phase 1: Preparation

1. **Deploy Fixed Contract to Testnet**
```bash
npx hardhat run scripts/deploy/[CONTRACT].ts --network amoy
```

2. **Verify on Testnet**
- [ ] Bug is fixed
- [ ] No new issues introduced
- [ ] All integrations work

3. **Mainnet Fork Testing**
```bash
# Start fork
npx hardhat node --fork https://polygon-mainnet.g.alchemy.com/v2/KEY

# Deploy and test
npx hardhat run scripts/upgrade/test-upgrade.ts --network localhost
```

### Phase 2: Mainnet Deployment

1. **Pause Affected Contracts**
```bash
npx hardhat run scripts/emergency/pause-affected.ts --network polygon
```

2. **Deploy New Contract**
```bash
npx hardhat run scripts/deploy/[CONTRACT].ts --network polygon
```

3. **Verify on Polygonscan**
```bash
npx hardhat verify --network polygon <NEW_ADDRESS> [CONSTRUCTOR_ARGS]
```

### Phase 3: Migration

1. **Update References**
   - Update all contracts that reference the old contract
   - Use multisig for role transfers

2. **Role Migration**
```typescript
// Grant roles to new contract
await oldContract.grantRole(ROLE, newContractAddress);

// After verification, revoke from old
await oldContract.revokeRole(ROLE, oldContractAddress);
```

3. **State Migration (if applicable)**
```typescript
// Example: Migrate user data
for (const user of affectedUsers) {
  await newContract.migrateUser(user.address, user.data);
}
```

### Phase 4: Verification

1. **Functional Testing**
- [ ] Core functionality works
- [ ] Integrations verified
- [ ] No stuck funds

2. **Unpause**
```bash
npx hardhat run scripts/emergency/unpause-all.ts --network polygon
```

3. **Monitor**
- Watch for 24 hours minimum
- Alert on any anomalies

---

## Type 3: Feature Addition

### Phase 1: Development

1. **Develop New Contract**
- Follow coding standards
- Include comprehensive tests
- Security-first design

2. **Integration Design**
- Define interfaces with existing contracts
- Plan role requirements
- Document dependencies

### Phase 2: Testnet Deployment

```bash
# Deploy new contract
npx hardhat run scripts/deploy/new-feature.ts --network amoy

# Run integration tests
npx hardhat test test/integration/new-feature.test.ts --network amoy
```

### Phase 3: Governance Proposal

```typescript
// Propose adding new contract to system
const targets = [
  existingContract.address,
  newContract.address
];
const values = [0, 0];
const calldatas = [
  existingContract.interface.encodeFunctionData("setNewFeature", [newContract.address]),
  newContract.interface.encodeFunctionData("initialize", [params])
];

await governor.propose(targets, values, calldatas, description);
```

### Phase 4: Mainnet Integration

1. **Deploy New Contract**
2. **Execute Governance Proposal**
3. **Verify Integration**
4. **Announce Feature**

---

## Type 4: Full Migration

### Pre-Migration (T-30 days)

1. **Announcement**
   - Public announcement of migration
   - Clear timeline communicated
   - Documentation prepared

2. **Migration Tools**
   - Develop migration scripts
   - Build state export/import tools
   - Create verification tools

3. **Testing**
   - Full migration test on fork
   - Dry run with team
   - Fix any issues found

### Migration Week (T-7 days)

1. **Final Preparations**
   - All tools tested and ready
   - Team availability confirmed
   - Communication plan finalized

2. **State Snapshot**
```typescript
// Export current state
const snapshot = await exportState(oldContracts);
fs.writeFileSync('migration-snapshot.json', JSON.stringify(snapshot));
```

### Migration Day (T-0)

1. **Pause Old System**
```bash
npx hardhat run scripts/emergency/pause-all.ts --network polygon
```

2. **Final State Export**
```bash
npx hardhat run scripts/migration/export-state.ts --network polygon
```

3. **Deploy New System**
```bash
npx hardhat run scripts/deploy/deploy-all.ts --network polygon
```

4. **Import State**
```bash
npx hardhat run scripts/migration/import-state.ts --network polygon
```

5. **Verify Migration**
```bash
npx hardhat run scripts/migration/verify-migration.ts --network polygon
```

6. **Enable New System**
```bash
npx hardhat run scripts/setup/initialize-contracts.ts --network polygon
```

### Post-Migration

1. **Monitor closely for 7 days**
2. **Address any issues immediately**
3. **Deprecate old contracts** (after grace period)

---

## Rollback Procedures

### Type 1/2: Quick Rollback

If issues discovered within 24 hours:

1. Pause new contract
2. Restore roles to old contract
3. Unpause old contract
4. Communicate rollback

### Type 3/4: Complex Rollback

1. Pause entire system
2. Assess data consistency
3. Restore from snapshot
4. Redeploy if necessary
5. Full verification before resume

---

## Upgrade Scripts

### scripts/upgrade/deploy-upgrade.ts

```typescript
import { ethers, network } from "hardhat";
import { loadDeployment, saveDeployment } from "../utils/deployment-helpers";

async function main() {
  const contractName = process.env.CONTRACT_NAME;
  if (!contractName) throw new Error("CONTRACT_NAME required");

  console.log(`Deploying upgrade for ${contractName}`);
  console.log("Network:", network.name);

  // Load old deployment
  const oldDeployment = await loadDeployment(contractName);
  console.log("Old address:", oldDeployment?.address);

  // Deploy new version
  const Contract = await ethers.getContractFactory(contractName);
  const newContract = await Contract.deploy(...constructorArgs);
  await newContract.waitForDeployment();

  const newAddress = await newContract.getAddress();
  console.log("New address:", newAddress);

  // Save with version suffix
  await saveDeployment(`${contractName}_v2`, {
    address: newAddress,
    previousVersion: oldDeployment?.address,
    // ... other details
  });

  console.log("Upgrade deployed. Run migration script next.");
}

main().catch(console.error);
```

### scripts/upgrade/migrate-roles.ts

```typescript
import { ethers } from "hardhat";
import { loadDeployment } from "../utils/deployment-helpers";

async function main() {
  const oldAddress = process.env.OLD_ADDRESS;
  const newAddress = process.env.NEW_ADDRESS;
  const role = process.env.ROLE;

  const oldContract = await ethers.getContractAt("AccessControl", oldAddress);
  const newContract = await ethers.getContractAt("AccessControl", newAddress);

  // Grant role to new contract
  console.log(`Granting ${role} to ${newAddress}`);
  await oldContract.grantRole(role, newAddress);

  // Verify
  const hasRole = await oldContract.hasRole(role, newAddress);
  console.log("Role granted:", hasRole);
}

main().catch(console.error);
```

---

## Governance Parameters

| Parameter | Value | Notes |
|-----------|-------|-------|
| Voting Delay | 1 block | Time before voting starts |
| Voting Period | 50,400 blocks | ~7 days |
| Proposal Threshold | 100,000 SHAKTI | Tokens needed to propose |
| Quorum | 4% | Minimum participation |
| Timelock Delay | 48 hours | Delay before execution |

---

## Verification Checklist

### Post-Upgrade Verification

- [ ] Contract deployed to correct network
- [ ] Contract verified on Polygonscan
- [ ] Constructor arguments correct
- [ ] Roles properly assigned
- [ ] Integrations functional
- [ ] No stuck funds
- [ ] Monitoring active
- [ ] Old contract deprecated (if applicable)

---

*Last Updated: _______________*
*Next Review: _______________*
