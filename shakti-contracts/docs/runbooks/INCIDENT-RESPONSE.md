# Incident Response Runbook

## Overview

This runbook provides structured procedures for responding to security incidents, system outages, and operational issues affecting SHAKTI-CHAIN.

---

## Incident Severity Levels

| Level | Name | Description | Response Time | Examples |
|-------|------|-------------|---------------|----------|
| SEV-1 | Critical | Active exploit, funds at risk | < 15 min | Reentrancy attack, oracle manipulation |
| SEV-2 | High | Service degraded, potential vulnerability | < 1 hour | Failed settlements, suspicious patterns |
| SEV-3 | Medium | Limited impact, workaround available | < 4 hours | Single contract issue, UI problems |
| SEV-4 | Low | Minor issue, no user impact | < 24 hours | Logging issues, minor bugs |

---

## Incident Response Team

### Primary Responders

| Role | Primary | Backup | Contact |
|------|---------|--------|---------|
| Incident Commander | _______ | _______ | _______ |
| Technical Lead | _______ | _______ | _______ |
| Security Lead | _______ | _______ | _______ |
| Communications Lead | _______ | _______ | _______ |

### Escalation Matrix

```
SEV-4 → On-call Engineer
SEV-3 → On-call Engineer → Team Lead
SEV-2 → On-call Engineer → Team Lead → Engineering Manager
SEV-1 → On-call Engineer → Team Lead → Engineering Manager → Executive Team
```

---

## Incident Response Phases

### Phase 1: Detection & Triage (0-15 minutes)

#### 1.1 Incident Detected

**Automated Detection Sources:**
- Tenderly alerts
- PagerDuty notifications
- Monitoring dashboards
- User reports

**Initial Assessment Checklist:**
- [ ] What is the nature of the incident?
- [ ] Which contracts/systems are affected?
- [ ] Is there active fund loss?
- [ ] What is the estimated impact?

#### 1.2 Assign Severity

```
┌─────────────────────────────────────────┐
│ Is there active fund loss or exploit?   │
│                                         │
│    YES → SEV-1 (Immediate pause)        │
│    NO  ↓                                │
├─────────────────────────────────────────┤
│ Is service completely unavailable?      │
│                                         │
│    YES → SEV-2                          │
│    NO  ↓                                │
├─────────────────────────────────────────┤
│ Are users significantly impacted?       │
│                                         │
│    YES → SEV-3                          │
│    NO  → SEV-4                          │
└─────────────────────────────────────────┘
```

#### 1.3 Create Incident Channel

```
# Discord/Slack channel naming
#incident-YYYYMMDD-brief-description

# Example
#incident-20241201-auction-settlement-failure
```

**Initial Message Template:**
```
INCIDENT DECLARED

Severity: SEV-[X]
Time Detected: [TIMESTAMP UTC]
Description: [BRIEF DESCRIPTION]
Affected Systems: [LIST]
Incident Commander: @[NAME]

Status: INVESTIGATING
```

### Phase 2: Containment (15-60 minutes)

#### 2.1 SEV-1 Containment

**Immediate Actions:**
1. [ ] Activate emergency pause (see EMERGENCY-PAUSE.md)
2. [ ] Notify all team members
3. [ ] Begin transaction analysis
4. [ ] Document all actions taken

**Transaction Analysis:**
```bash
# Get recent transactions for affected contract
cast logs --address <CONTRACT_ADDRESS> --from-block <BLOCK-100> --rpc-url $POLYGON_RPC

# Check specific transaction
cast tx <TX_HASH> --rpc-url $POLYGON_RPC

# Decode transaction data
cast decode-tx <TX_HASH> --rpc-url $POLYGON_RPC
```

#### 2.2 SEV-2/3 Containment

**Actions:**
1. [ ] Assess if pause is necessary
2. [ ] Identify affected functionality
3. [ ] Implement temporary workaround if possible
4. [ ] Document scope of impact

#### 2.3 Evidence Preservation

**Collect and Document:**
- [ ] Relevant transaction hashes
- [ ] Block numbers
- [ ] Contract states before/after
- [ ] Logs and alerts
- [ ] Screenshots of dashboards

**Evidence Template:**
```markdown
## Evidence Log

### Transaction Evidence
| Tx Hash | Block | From | To | Value | Notes |
|---------|-------|------|----|----|-------|
| 0x... | 12345 | 0x... | 0x... | X ETH | Description |

### State Evidence
| Contract | Function | Before | After |
|----------|----------|--------|-------|
| ... | ... | ... | ... |

### Timeline
| Time (UTC) | Event |
|------------|-------|
| HH:MM | ... |
```

### Phase 3: Investigation (1-24 hours)

#### 3.1 Root Cause Analysis

**Investigation Checklist:**
- [ ] Identify attack vector or failure point
- [ ] Trace all affected transactions
- [ ] Determine scope of impact
- [ ] Calculate losses (if any)
- [ ] Identify vulnerability source

**Analysis Tools:**
```bash
# Mainnet fork for investigation
npx hardhat node --fork https://polygon-mainnet.g.alchemy.com/v2/YOUR_KEY --fork-block-number <BLOCK>

# Simulate attack/failure
npx hardhat test test/incident/reproduce-incident.ts --network localhost
```

#### 3.2 Impact Assessment

| Metric | Value |
|--------|-------|
| Funds Lost | $ _____ |
| Users Affected | _____ |
| Transactions Affected | _____ |
| Duration | _____ hours |

### Phase 4: Remediation (24-72 hours)

#### 4.1 Develop Fix

**Requirements:**
- [ ] Fix addresses root cause
- [ ] Fix tested on mainnet fork
- [ ] Security review completed
- [ ] No regressions introduced

#### 4.2 Deploy Fix

**For Code Changes:**
1. Follow UPGRADE-PROCEDURE.md
2. Emergency governance if needed
3. Thorough testing before mainnet

**For Configuration Changes:**
1. Prepare multisig transaction
2. Review by security team
3. Execute via Gnosis Safe

#### 4.3 Restore Service

1. [ ] Verify fix deployed correctly
2. [ ] Execute unpause (see EMERGENCY-PAUSE.md)
3. [ ] Monitor closely for 24 hours
4. [ ] Confirm normal operation

### Phase 5: Communication

#### 5.1 Internal Communication

**Update Frequency by Severity:**
- SEV-1: Every 15 minutes
- SEV-2: Every 30 minutes
- SEV-3: Every 2 hours
- SEV-4: Daily

**Status Update Template:**
```
INCIDENT UPDATE

Severity: SEV-[X]
Status: [INVESTIGATING/CONTAINED/RESOLVED]
Time: [TIMESTAMP UTC]

Current State:
- [BULLET POINTS]

Actions Taken:
- [BULLET POINTS]

Next Steps:
- [BULLET POINTS]

ETA for Resolution: [TIME]
```

#### 5.2 External Communication

**Public Status Page Updates:**
```
[TIMESTAMP] - Investigating
We are investigating reports of [ISSUE DESCRIPTION].

[TIMESTAMP] - Identified
The issue has been identified. We are working on a fix.

[TIMESTAMP] - Resolved
The issue has been resolved. All services are operating normally.
```

**Discord/Twitter Template:**
```
Update on SHAKTI-CHAIN Service Interruption

We experienced [BRIEF DESCRIPTION] starting at [TIME].

Impact: [DESCRIPTION]
Status: [CURRENT STATUS]
Next Update: [TIME]

Your funds are safe. We appreciate your patience.
```

### Phase 6: Post-Incident (24-168 hours)

#### 6.1 Post-Mortem

**Required for:** All SEV-1 and SEV-2 incidents

**Post-Mortem Template:**
```markdown
# Incident Post-Mortem: [TITLE]

## Summary
- **Date:** [DATE]
- **Duration:** [X hours]
- **Severity:** SEV-[X]
- **Impact:** [DESCRIPTION]

## Timeline
| Time (UTC) | Event |
|------------|-------|
| HH:MM | Incident detected |
| HH:MM | ... |
| HH:MM | Resolution |

## Root Cause
[DETAILED DESCRIPTION]

## Resolution
[HOW THE INCIDENT WAS RESOLVED]

## Lessons Learned
### What Went Well
- [BULLET POINTS]

### What Didn't Go Well
- [BULLET POINTS]

## Action Items
| Item | Owner | Due Date | Status |
|------|-------|----------|--------|
| ... | ... | ... | ... |

## Prevention Measures
[DESCRIPTION OF CHANGES TO PREVENT RECURRENCE]
```

#### 6.2 Follow-up Actions

- [ ] Post-mortem document completed
- [ ] Action items assigned and tracked
- [ ] Runbooks updated if needed
- [ ] Monitoring/alerting improved
- [ ] Team debrief conducted

---

## Incident Playbooks

### Playbook: Oracle Manipulation

**Symptoms:**
- Unusual price movements
- Large trades at suspicious prices
- Alert on price deviation

**Response:**
1. Pause DynamicPricing contract
2. Check Chainlink feed status
3. Compare on-chain vs off-chain prices
4. If manipulation confirmed:
   - Pause EnergyAuction
   - Identify affected trades
   - Prepare compensation plan

### Playbook: Failed Settlements

**Symptoms:**
- Escrow release failures
- User complaints about stuck funds
- Settlement timeout alerts

**Response:**
1. Identify failing transactions
2. Check escrow contract state
3. Verify AUCTION_ROLE assignments
4. Check token balances
5. Manual intervention if needed

### Playbook: Suspicious Activity

**Symptoms:**
- Unusual trading patterns
- Multiple failed transactions
- Wash trading indicators

**Response:**
1. Document suspicious addresses
2. Analyze transaction patterns
3. Check if exploit or legitimate
4. If malicious: consider blacklist
5. Update reputation scores

### Playbook: Network Issues (Polygon)

**Symptoms:**
- Transaction timeouts
- RPC errors
- Block production issues

**Response:**
1. Switch to backup RPC
2. Check Polygon status page
3. Pause if necessary for safety
4. Communicate delay to users
5. Resume when network stable

---

## Contact Information

### Internal
| Team | Channel | Email |
|------|---------|-------|
| Engineering | #engineering | eng@shakti.energy |
| Security | #security | security@shakti.energy |
| Operations | #ops | ops@shakti.energy |

### External
| Service | Contact | Phone |
|---------|---------|-------|
| Alchemy (RPC) | support@alchemy.com | _______ |
| Chainlink | _______ | _______ |
| Polygon | _______ | _______ |

---

*Last Updated: _______________*
*Next Review: _______________*
