import { BigInt, Address, Bytes } from "@graphprotocol/graph-ts";
import {
  Transfer as TransferEvent,
  Approval as ApprovalEvent,
  FeesBurned as FeesBurnedEvent,
  DelegateChanged as DelegateChangedEvent,
  DelegateVotesChanged as DelegateVotesChangedEvent,
} from "../generated/ShaktiToken/ShaktiToken";
import { TokenHolder, Transfer, Protocol, DailyStats } from "../generated/schema";
import {
  ZERO_BD,
  ZERO_BI,
  toDecimal,
  getOrCreateProtocol,
  getOrCreateTokenHolder,
  getOrCreateDailyStats,
  generateTransferId,
} from "./helpers";

// ============ Transfer Handler ============

export function handleTransfer(event: TransferEvent): void {
  let from = event.params.from;
  let to = event.params.to;
  let amount = toDecimal(event.params.value);
  let timestamp = event.block.timestamp;

  // Skip zero transfers
  if (amount.equals(ZERO_BD)) {
    return;
  }

  // Handle mint (from zero address)
  let isMint = from.equals(Address.zero());
  // Handle burn (to zero address)
  let isBurn = to.equals(Address.zero());

  // Update sender (if not mint)
  if (!isMint) {
    let fromHolder = getOrCreateTokenHolder(from, timestamp);
    fromHolder.balance = fromHolder.balance.minus(amount);
    fromHolder.totalTransferred = fromHolder.totalTransferred.plus(amount);
    fromHolder.lastActivityAt = timestamp;

    if (isBurn) {
      fromHolder.totalBurned = fromHolder.totalBurned.plus(amount);
    }

    fromHolder.save();
  }

  // Update receiver (if not burn)
  if (!isBurn) {
    let toHolder = getOrCreateTokenHolder(to, timestamp);
    toHolder.balance = toHolder.balance.plus(amount);
    toHolder.totalReceived = toHolder.totalReceived.plus(amount);
    toHolder.lastActivityAt = timestamp;
    toHolder.save();
  }

  // Create transfer entity
  let transferId = generateTransferId(event.transaction.hash, event.logIndex);
  let transfer = new Transfer(transferId);
  transfer.from = from.toHexString();
  transfer.to = to.toHexString();
  transfer.amount = amount;
  transfer.timestamp = timestamp;
  transfer.blockNumber = event.block.number;
  transfer.transactionHash = event.transaction.hash;
  transfer.save();

  // Update protocol stats
  let protocol = getOrCreateProtocol();

  if (isMint) {
    protocol.totalSupply = protocol.totalSupply.plus(amount);
    protocol.circulatingSupply = protocol.circulatingSupply.plus(amount);
  } else if (isBurn) {
    protocol.totalSupply = protocol.totalSupply.minus(amount);
    protocol.circulatingSupply = protocol.circulatingSupply.minus(amount);
    protocol.totalBurned = protocol.totalBurned.plus(amount);
  }

  protocol.lastUpdatedAt = timestamp;
  protocol.save();
}

// ============ Approval Handler ============

export function handleApproval(event: ApprovalEvent): void {
  // Approvals are tracked implicitly through transfers
  // Can be extended to track allowances if needed
}

// ============ Fees Burned Handler ============

export function handleFeesBurned(event: FeesBurnedEvent): void {
  let from = event.params.from;
  let feeAmount = toDecimal(event.params.feeAmount);
  let burnedAmount = toDecimal(event.params.burnedAmount);
  let timestamp = event.block.timestamp;

  // Update protocol stats
  let protocol = getOrCreateProtocol();
  protocol.totalBurned = protocol.totalBurned.plus(burnedAmount);
  protocol.totalFees = protocol.totalFees.plus(feeAmount);
  protocol.lastUpdatedAt = timestamp;
  protocol.save();

  // Update daily stats
  let dailyStats = getOrCreateDailyStats(timestamp);
  dailyStats.totalBurned = dailyStats.totalBurned.plus(burnedAmount);
  dailyStats.totalFees = dailyStats.totalFees.plus(feeAmount);
  dailyStats.save();

  // Update holder stats
  let holder = getOrCreateTokenHolder(from, timestamp);
  holder.totalBurned = holder.totalBurned.plus(burnedAmount);
  holder.lastActivityAt = timestamp;
  holder.save();
}

// ============ Delegation Handlers ============

export function handleDelegateChanged(event: DelegateChangedEvent): void {
  let delegator = event.params.delegator;
  let newDelegate = event.params.toDelegate;
  let timestamp = event.block.timestamp;

  let holder = getOrCreateTokenHolder(delegator, timestamp);

  if (newDelegate.equals(Address.zero())) {
    holder.delegatedTo = null;
  } else {
    holder.delegatedTo = newDelegate;
  }

  holder.lastActivityAt = timestamp;
  holder.save();
}

export function handleDelegateVotesChanged(event: DelegateVotesChangedEvent): void {
  let delegate = event.params.delegate;
  let newVotes = toDecimal(event.params.newBalance);
  let timestamp = event.block.timestamp;

  let holder = getOrCreateTokenHolder(delegate, timestamp);
  holder.votingPower = newVotes;
  holder.lastActivityAt = timestamp;
  holder.save();
}
