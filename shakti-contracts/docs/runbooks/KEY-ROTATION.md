# Key Rotation Procedure

## Overview

This runbook describes the procedures for rotating cryptographic keys, admin addresses, and multisig signers for SHAKTI-CHAIN.

**Security Classification:** Confidential
**Review Frequency:** Quarterly

---

## Key Types and Rotation Schedules

| Key Type | Rotation Schedule | Trigger Events |
|----------|------------------|----------------|
| Deployer Key | Post-launch only | Compromise suspected |
| Multisig Signers | As needed | Personnel change, compromise |
| API Keys (Alchemy, etc.) | Every 90 days | Scheduled, exposure |
| Oracle Keys | Per Chainlink | Chainlink managed |
| Backend Service Keys | Every 30 days | Scheduled |

---

## 1. Multisig Signer Rotation

### 1.1 When to Rotate

**Mandatory Rotation:**
- Team member leaves organization
- Security incident involving signer
- Hardware wallet lost or stolen
- Signer becomes unresponsive (>30 days)

**Recommended Rotation:**
- Annual key refresh
- After major security incident (even if signer not compromised)

### 1.2 Prerequisites

- [ ] New signer identified and vetted
- [ ] New signer has hardware wallet (Ledger/Trezor)
- [ ] New signer address verified
- [ ] 3/5 current signers available (Owner) or 2/3 (Emergency)
- [ ] Backup communication channel established

### 1.3 Procedure: Add New Signer

**Step 1: Verify New Signer**
```
New Signer Address: 0x________________________________
Verification Method: [Video call / In-person / Signed message]
Verified By: ________________________________
Date: ________________________________
```

**Step 2: Add to Gnosis Safe**

1. Go to https://app.safe.global/
2. Connect with existing signer wallet
3. Navigate to Settings > Owners
4. Click "Add new owner"
5. Enter new signer address
6. **Do not change threshold yet**
7. Submit transaction
8. Collect required signatures
9. Execute

**Step 3: Verify Addition**
```bash
# Verify signer count
cast call <SAFE_ADDRESS> "getOwners()(address[])" --rpc-url $POLYGON_RPC
```

### 1.4 Procedure: Remove Old Signer

**Step 1: Confirm Removal Authorization**
- [ ] Documented reason for removal
- [ ] Approval from team lead
- [ ] New signer already added

**Step 2: Remove from Gnosis Safe**

1. Go to https://app.safe.global/
2. Connect with existing signer wallet
3. Navigate to Settings > Owners
4. Click on owner to remove
5. Select "Remove owner"
6. Verify threshold remains valid (3/5 or 2/3)
7. Submit transaction
8. Collect required signatures
9. Execute

**Step 3: Verify Removal**
```bash
# Verify signer count
cast call <SAFE_ADDRESS> "getOwners()(address[])" --rpc-url $POLYGON_RPC
```

**Step 4: Revoke Any Direct Roles**

If the removed signer had direct roles on contracts:
```typescript
// Example: Remove PAUSER_ROLE
await contract.revokeRole(PAUSER_ROLE, oldSignerAddress);
```

### 1.5 Emergency Signer Replacement

If a signer is compromised and immediate action needed:

1. **Immediately pause all contracts** (if 2/3 Emergency signers available)
2. **Do NOT process any pending Safe transactions**
3. **Remove compromised signer as first priority**
4. **Add replacement signer**
5. **Review all pending transactions for malicious activity**
6. **Resume operations**

---

## 2. Admin Role Rotation

### 2.1 Role Inventory

| Contract | Role | Current Holder | Backup |
|----------|------|----------------|--------|
| ShaktiToken | DEFAULT_ADMIN_ROLE | Owner Multisig | - |
| ShaktiToken | MINTER_ROLE | StakingPool | - |
| ShaktiToken | PAUSER_ROLE | Emergency Multisig | - |
| StakingPool | DEFAULT_ADMIN_ROLE | Owner Multisig | - |
| EnergyAuction | OPERATOR_ROLE | Deployer | Owner Multisig |
| EnergyEscrow | AUCTION_ROLE | EnergyAuction | - |
| ReputationSystem | REPORTER_ROLE | EnergyAuction | - |
| EnergyVerification | ARBITER_ROLE | Owner Multisig | - |
| Treasury | Signer | 5 Signers | - |

### 2.2 Rotating Admin Roles

**From Individual to Multisig:**

```typescript
// 1. Grant role to multisig
await contract.grantRole(DEFAULT_ADMIN_ROLE, multisigAddress);

// 2. Verify multisig has role
const hasRole = await contract.hasRole(DEFAULT_ADMIN_ROLE, multisigAddress);
console.log("Multisig has admin:", hasRole); // true

// 3. Revoke from individual (via multisig)
await contract.revokeRole(DEFAULT_ADMIN_ROLE, individualAddress);
```

**Between Multisigs:**

Must be done via governance or current admin multisig:
1. Create Safe transaction granting role to new multisig
2. Collect signatures
3. Execute
4. Create Safe transaction revoking role from old multisig
5. Collect signatures
6. Execute

### 2.3 Script: Rotate Admin Role

```typescript
// scripts/admin/rotate-role.ts
import { ethers } from "hardhat";

async function main() {
  const CONTRACT_ADDRESS = process.env.CONTRACT_ADDRESS!;
  const ROLE = process.env.ROLE!;
  const OLD_ADDRESS = process.env.OLD_ADDRESS!;
  const NEW_ADDRESS = process.env.NEW_ADDRESS!;

  const contract = await ethers.getContractAt("AccessControl", CONTRACT_ADDRESS);

  console.log("Rotating role:", ROLE);
  console.log("From:", OLD_ADDRESS);
  console.log("To:", NEW_ADDRESS);

  // Grant to new
  console.log("\nGranting role to new address...");
  const grantTx = await contract.grantRole(ROLE, NEW_ADDRESS);
  await grantTx.wait();
  console.log("Granted. Tx:", grantTx.hash);

  // Verify
  const newHasRole = await contract.hasRole(ROLE, NEW_ADDRESS);
  if (!newHasRole) throw new Error("Grant failed!");

  // Revoke from old
  console.log("\nRevoking role from old address...");
  const revokeTx = await contract.revokeRole(ROLE, OLD_ADDRESS);
  await revokeTx.wait();
  console.log("Revoked. Tx:", revokeTx.hash);

  // Verify
  const oldHasRole = await contract.hasRole(ROLE, OLD_ADDRESS);
  if (oldHasRole) throw new Error("Revoke failed!");

  console.log("\nRole rotation complete!");
}

main().catch(console.error);
```

---

## 3. API Key Rotation

### 3.1 Alchemy API Key

**Rotation Schedule:** Every 90 days or on suspected exposure

**Procedure:**

1. **Generate New Key**
   - Log into Alchemy Dashboard
   - Go to Apps > Your App
   - Click "View Key"
   - Click "Rotate Key" (keeps old key valid for 24h)

2. **Update Configuration**
   ```bash
   # Update .env
   ALCHEMY_API_KEY=new_key_here

   # Update any deployed services
   # Kubernetes secret, AWS Parameter Store, etc.
   ```

3. **Verify New Key Works**
   ```bash
   curl https://polygon-mainnet.g.alchemy.com/v2/NEW_KEY \
     -X POST \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}'
   ```

4. **Update Deployed Services**
   - Restart affected services
   - Verify connectivity

5. **Confirm Old Key Deactivated** (after 24h)
   - Attempt connection with old key
   - Should fail

### 3.2 Tenderly API Key

**Procedure:**

1. Go to Tenderly Dashboard > Settings > API Keys
2. Create new key
3. Update webhook configurations
4. Verify alerts still work
5. Delete old key

### 3.3 PagerDuty Integration Key

**Procedure:**

1. Go to PagerDuty > Services > SHAKTI-CHAIN
2. Integrations > Add Integration
3. Create new Events API v2 key
4. Update webhook URLs
5. Test alert
6. Remove old integration

---

## 4. Backend Service Keys

### 4.1 Database Credentials

**Schedule:** Every 30 days

1. Generate new password
2. Update database user
3. Update application configuration
4. Rolling restart of services
5. Verify connectivity
6. Invalidate old password

### 4.2 JWT Signing Keys

**Schedule:** Every 90 days

1. Generate new key pair
2. Add new public key to validators
3. Keep old key for validation (grace period)
4. Switch signing to new key
5. After grace period, remove old key

---

## 5. Hardware Wallet Best Practices

### 5.1 Setup Requirements

- [ ] Hardware wallet purchased from official source
- [ ] Firmware updated to latest version
- [ ] New seed phrase generated (never reused)
- [ ] Seed phrase backed up on steel/titanium
- [ ] Backup stored in secure location (safe, bank vault)
- [ ] PIN set (not default)
- [ ] Passphrase enabled (optional, recommended for high-value)

### 5.2 Seed Phrase Backup

**DO:**
- Write on metal (fire/water resistant)
- Store in secure location (bank safe deposit box)
- Consider splitting across locations (2-of-3 Shamir)
- Keep backup location documented (secured)

**DON'T:**
- Store digitally (no photos, no cloud)
- Use easily guessed passphrases
- Store seed and passphrase together
- Share seed phrase with anyone

### 5.3 Regular Verification

**Monthly:**
- [ ] Hardware wallet accessible
- [ ] PIN remembered
- [ ] Can sign test message

**Quarterly:**
- [ ] Backup location verified
- [ ] Seed phrase backup intact
- [ ] Recovery procedure tested (on separate device)

---

## 6. Compromise Response

### 6.1 Suspected Key Compromise

**Immediate Actions:**

1. **Do not panic** - act methodically
2. **Assess scope** - which keys potentially affected?
3. **Pause contracts** if user funds at risk
4. **Notify team** via secure channel
5. **Begin rotation** for affected keys

### 6.2 Confirmed Compromise

1. **Emergency pause** all contracts
2. **Remove compromised signer** from all multisigs
3. **Revoke all roles** from compromised address
4. **Audit recent transactions** for unauthorized activity
5. **Assess damage** and document
6. **Add replacement** signer/key
7. **Resume operations** once secure
8. **Post-mortem** and improve procedures

### 6.3 Compromise Checklist

```markdown
## Compromise Response Log

Date/Time Detected: ________________________________
Detected By: ________________________________
Affected Key/Address: ________________________________
Potential Scope: ________________________________

### Immediate Response
- [ ] Team notified
- [ ] Contracts paused (if needed)
- [ ] Compromised access revoked

### Investigation
- [ ] Recent transactions reviewed
- [ ] Unauthorized activity identified: Y/N
- [ ] Funds affected: Amount: ___________

### Recovery
- [ ] New keys generated
- [ ] Access restored to team
- [ ] Operations resumed

### Post-Mortem
- [ ] Root cause identified
- [ ] Preventive measures implemented
- [ ] Documentation updated
```

---

## 7. Rotation Log

Maintain a secure log of all key rotations:

| Date | Key Type | Old Identifier | New Identifier | Rotated By | Reason |
|------|----------|----------------|----------------|------------|--------|
| YYYY-MM-DD | Multisig Signer | 0x...1234 | 0x...5678 | [Name] | Personnel change |
| YYYY-MM-DD | Alchemy API | key_...abc | key_...xyz | [Name] | Scheduled |

**Log Location:** [Secure documentation system]
**Access:** [Authorized personnel only]

---

## Appendix A: Quick Reference

### Gnosis Safe Management

```bash
# Check owners
cast call <SAFE> "getOwners()(address[])" --rpc-url $RPC

# Check threshold
cast call <SAFE> "getThreshold()(uint256)" --rpc-url $RPC
```

### Role Verification

```bash
# Check if address has role
cast call <CONTRACT> "hasRole(bytes32,address)(bool)" <ROLE_HASH> <ADDRESS> --rpc-url $RPC

# Common role hashes
DEFAULT_ADMIN_ROLE = 0x0000000000000000000000000000000000000000000000000000000000000000
MINTER_ROLE = 0x9f2df0fed2c77648de5860a4cc508cd0818c85b8b8a1ab4ceeef8d981c8956a6
PAUSER_ROLE = 0x65d7a28e3265b37a6474929f336521b332c1681b933f6cb9f3376673440d862a
```

---

*Last Updated: _______________*
*Next Review: _______________*
*Classification: CONFIDENTIAL*
