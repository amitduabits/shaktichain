# SHAKTI-CHAIN Upgradeable Contracts Guide

This guide documents the upgrade process for SHAKTI-CHAIN smart contracts using the UUPS (Universal Upgradeable Proxy Standard) pattern.

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Upgradeable Contracts](#upgradeable-contracts)
3. [Deployment](#deployment)
4. [Upgrade Process](#upgrade-process)
5. [Governance-Controlled Upgrades](#governance-controlled-upgrades)
6. [Safety Checks](#safety-checks)
7. [Rollback Procedure](#rollback-procedure)
8. [Best Practices](#best-practices)

---

## Architecture Overview

### UUPS Pattern

SHAKTI-CHAIN uses the UUPS (Universal Upgradeable Proxy Standard) upgrade pattern:

```
┌─────────────────┐     ┌─────────────────┐
│   Proxy (ERC1967)│────▶│  Implementation │
│                 │     │                 │
│  - Storage      │     │  - Logic        │
│  - Fallback     │     │  - Version      │
│  - delegatecall │     │  - _authorizeUpgrade │
└─────────────────┘     └─────────────────┘
```

**Key Features:**
- Upgrade logic lives in the implementation (not the proxy)
- Smaller proxy contracts = lower gas costs
- `_authorizeUpgrade` provides access control
- Storage layout must remain compatible across versions

### Storage Layout

Each upgradeable contract includes a storage gap for future variables:

```solidity
// Reserved for future state variables
uint256[40] private __gap;
```

**Important:** Never:
- Remove existing state variables
- Change the order of state variables
- Change the type of state variables
- Add variables before the gap

---

## Upgradeable Contracts

| Contract | Description | Storage Gap |
|----------|-------------|-------------|
| `ShaktiTokenV2` | ERC20 + Votes + Burnable | 49 slots |
| `EnergyAuctionUpgradeable` | McAfee double auction | 40 slots |
| `EnergyEscrowUpgradeable` | Settlement & disputes | 40 slots |
| `ReputationSystemUpgradeable` | Tiered reputation system | 40 slots |

### Key Roles

Each contract defines an `UPGRADER_ROLE`:

```solidity
bytes32 public constant UPGRADER_ROLE = keccak256("UPGRADER_ROLE");

function _authorizeUpgrade(
    address newImplementation
) internal override onlyRole(UPGRADER_ROLE) {}
```

---

## Deployment

### Initial Deployment

Deploy all upgradeable contracts using the provided script:

```bash
# Localhost/Hardhat
npx hardhat run scripts/deploy-upgradeable.ts --network localhost

# Polygon Mumbai Testnet
npx hardhat run scripts/deploy-upgradeable.ts --network polygonMumbai

# Polygon Mainnet
npx hardhat run scripts/deploy-upgradeable.ts --network polygonMainnet
```

The script will:
1. Deploy each contract as a UUPS proxy
2. Initialize with proper configuration
3. Grant roles to the deployer
4. Save deployment info to `deployments/<network>-upgradeable-deployment.json`

### Deployment Output

```json
{
  "network": "polygonMumbai",
  "chainId": 80001,
  "contracts": {
    "ShaktiTokenV2": {
      "proxy": "0x...",
      "implementation": "0x...",
      "admin": "0x..."
    },
    ...
  },
  "deployer": "0x...",
  "timestamp": "2024-..."
}
```

---

## Upgrade Process

### Step 1: Prepare New Implementation

Create a new version of the contract (e.g., `EnergyAuctionUpgradeableV2.sol`):

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "./EnergyAuctionUpgradeable.sol";

contract EnergyAuctionUpgradeableV2 is EnergyAuctionUpgradeable {
    // New state variable (use from the gap!)
    uint256 public newFeature;

    // Reinitializer for V2-specific setup
    function initializeV2(uint256 _newFeature) public reinitializer(2) {
        newFeature = _newFeature;
    }

    // Override version
    function version() external pure override returns (string memory) {
        return "2.0.0";
    }

    // New functionality
    function newFunction() external view returns (uint256) {
        return newFeature;
    }
}
```

### Step 2: Validate Storage Compatibility

```bash
npx hardhat run scripts/verify-upgrade.ts --network <network>
```

This validates:
- Storage layout compatibility
- No breaking changes
- Roles are intact
- Contract state is accessible

### Step 3: Execute Upgrade

For non-governance upgrades (testnet):

```bash
npx hardhat run scripts/upgrade-auction.ts --network polygonMumbai
```

For governance-controlled upgrades (mainnet), see [Governance-Controlled Upgrades](#governance-controlled-upgrades).

### Step 4: Post-Upgrade Verification

```bash
npx hardhat run scripts/verify-upgrade.ts --network <network>
```

Verify:
- New implementation is active
- State is preserved
- New functionality works
- No unexpected behavior

---

## Governance-Controlled Upgrades

On mainnet, upgrades should go through governance:

### Flow

```
1. Proposal Created    ──▶ Governor Contract
2. Voting Period       ──▶ 5 days
3. Timelock Queue      ──▶ 2 days delay
4. Execution           ──▶ Upgrade performed
5. Verification        ──▶ Post-upgrade checks
```

### Transfer UPGRADER_ROLE to Governance

After initial deployment:

```solidity
// Grant to timelock
contract.grantRole(UPGRADER_ROLE, timelockAddress);

// Revoke from deployer (optional, for full decentralization)
contract.revokeRole(UPGRADER_ROLE, deployerAddress);
```

### Create Upgrade Proposal

```javascript
const targets = [auctionProxyAddress];
const values = [0];
const calldatas = [
  auctionProxy.interface.encodeFunctionData("upgradeToAndCall", [
    newImplementation,
    initData // or "0x" if no re-initialization
  ])
];
const description = "Upgrade EnergyAuction to V2 - adds batch settlement feature";

await governor.propose(targets, values, calldatas, description);
```

### Execute After Timelock

```javascript
await governor.queue(targets, values, calldatas, descriptionHash);
// Wait for timelock delay...
await governor.execute(targets, values, calldatas, descriptionHash);
```

---

## Safety Checks

### Pre-Upgrade Checklist

- [ ] New implementation compiles without errors
- [ ] Storage layout validated with OpenZeppelin plugin
- [ ] Unit tests pass for new functionality
- [ ] Integration tests pass
- [ ] Testnet deployment successful
- [ ] Security review completed (for significant changes)
- [ ] Snapshot of current state taken
- [ ] Rollback plan documented

### Storage Layout Validation

The OpenZeppelin Upgrades plugin automatically validates:

```typescript
await upgrades.validateUpgrade(proxyAddress, NewImplementation, {
  kind: "uups",
});
```

If validation fails, you'll see errors like:
- "Storage layout incompatible"
- "New variable inserted before existing"
- "Variable type changed"

### State Snapshot

Before upgrade, record critical state:

```javascript
const snapshot = {
  roundId: await auction.currentRoundId(),
  minPrice: await auction.minPrice(),
  maxPrice: await auction.maxPrice(),
  // ... other critical values
};
```

After upgrade, verify state matches.

---

## Rollback Procedure

### When to Rollback

- Critical bug discovered in new implementation
- Unexpected behavior affecting users
- Security vulnerability identified
- State corruption detected

### Emergency Rollback Script

```bash
# Interactive mode
npx hardhat run scripts/rollback.ts --network <network>

# Non-interactive mode
npx hardhat run scripts/rollback.ts --network <network> \
  --contract EnergyAuctionUpgradeable \
  --implementation 0x<previous-impl> \
  --reason "Critical bug in V2" \
  --force
```

### Rollback Process

1. **Identify** the previous working implementation address
2. **Verify** the caller has `UPGRADER_ROLE`
3. **Confirm** the action (type "ROLLBACK")
4. **Execute** the rollback
5. **Verify** contract functionality is restored
6. **Document** the incident

### Post-Rollback

1. Investigate root cause
2. Fix the issue
3. Add regression tests
4. Re-deploy after proper testing

---

## Best Practices

### Development

1. **Always use initializers** - Never use constructors in upgradeable contracts
2. **Reserve storage gaps** - Include `uint256[N] private __gap;`
3. **Version your contracts** - Include a `version()` function
4. **Use reinitializers** - For upgrade-specific initialization

### Testing

1. **Test upgrade path** - Include upgrade tests in test suite
2. **Test state preservation** - Verify state survives upgrades
3. **Test new functionality** - Ensure new features work
4. **Test rollback** - Verify rollback works correctly

### Security

1. **Limit UPGRADER_ROLE** - Only governance should have this role on mainnet
2. **Use timelock** - Add delay before upgrades execute
3. **Audit significant changes** - Security review for major upgrades
4. **Monitor events** - Watch for `Upgraded(implementation)` events

### Operations

1. **Testnet first** - Always test upgrades on testnet
2. **Document changes** - Keep upgrade history
3. **Have rollback plan** - Know how to revert if needed
4. **Monitor post-upgrade** - Watch for issues after deployment

---

## Scripts Reference

| Script | Purpose |
|--------|---------|
| `deploy-upgradeable.ts` | Initial deployment of all upgradeable contracts |
| `upgrade-auction.ts` | Upgrade EnergyAuctionUpgradeable |
| `verify-upgrade.ts` | Verify all upgradeable contracts |
| `rollback.ts` | Emergency rollback to previous implementation |

---

## Troubleshooting

### "Storage layout incompatible"

You've changed the storage layout in an incompatible way. Options:
- Use a new slot from the storage gap
- Ensure variable order matches V1
- Consider a migration strategy

### "Caller doesn't have UPGRADER_ROLE"

The account trying to upgrade lacks permissions. Either:
- Use an account with UPGRADER_ROLE
- Grant UPGRADER_ROLE to the account
- Use governance to execute the upgrade

### "Implementation not found"

The target implementation address has no code. Ensure:
- Implementation is deployed first
- Using correct network
- Address is correct

### "Transaction reverted"

Check:
- Gas limit is sufficient
- Caller has required roles
- Contract is not paused
- Initialize/reinitialize called correctly

---

## Further Reading

- [OpenZeppelin Upgrades Documentation](https://docs.openzeppelin.com/upgrades-plugins)
- [EIP-1822: UUPS Standard](https://eips.ethereum.org/EIPS/eip-1822)
- [EIP-1967: Proxy Storage Slots](https://eips.ethereum.org/EIPS/eip-1967)
- [SHAKTI-CHAIN Technical Documentation](./technical-architecture.md)
