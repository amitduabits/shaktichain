import { BigInt, BigDecimal, Address } from "@graphprotocol/graph-ts";
import {
  UserRegistered as UserRegisteredEvent,
  ReputationUpdated as ReputationUpdatedEvent,
  TierChanged as TierChangedEvent,
  DecayApplied as DecayAppliedEvent,
  UserFlaggedEvent as UserFlaggedEventEvent,
  UserUnflagged as UserUnflaggedEvent,
  StakeUpdated as StakeUpdatedEvent,
  KYCStatusUpdated as KYCStatusUpdatedEvent,
} from "../generated/ReputationSystem/ReputationSystem";
import {
  Prosumer,
  ReputationChange,
  DailyStats,
  Protocol,
} from "../generated/schema";
import {
  ZERO_BD,
  ZERO_BI,
  ONE_BI,
  toDecimal,
  getOrCreateProtocol,
  getOrCreateProsumer,
  getOrCreateDailyStats,
  generateReputationChangeId,
  getTierFromEnum,
  getTierFromScore,
} from "./helpers";

// ============ User Registration ============

export function handleUserRegistered(event: UserRegisteredEvent): void {
  let user = event.params.user;
  let initialReputation = event.params.initialReputation.toI32();
  let tier = event.params.tier;
  let timestamp = event.block.timestamp;

  // Create prosumer with initial values
  let prosumer = getOrCreateProsumer(user, timestamp);
  prosumer.reputation = initialReputation;
  prosumer.tier = getTierFromEnum(tier);
  prosumer.registeredAt = timestamp;
  prosumer.lastActivityAt = timestamp;
  prosumer.save();

  // Create initial reputation change record
  let changeId = generateReputationChangeId(event.transaction.hash, event.logIndex);
  let change = new ReputationChange(changeId);
  change.prosumer = prosumer.id;
  change.oldScore = 0;
  change.newScore = initialReputation;
  change.change = initialReputation;
  change.reason = "Initial registration";
  change.oldTier = null;
  change.newTier = getTierFromEnum(tier);
  change.tierChanged = true;
  change.timestamp = timestamp;
  change.transactionHash = event.transaction.hash;
  change.save();

  // Update daily stats
  let dailyStats = getOrCreateDailyStats(timestamp);
  dailyStats.newProsumers = dailyStats.newProsumers + 1;
  dailyStats.save();
}

// ============ Reputation Updates ============

export function handleReputationUpdated(event: ReputationUpdatedEvent): void {
  let user = event.params.user;
  let oldScore = event.params.oldScore.toI32();
  let newScore = event.params.newScore.toI32();
  let reason = event.params.reason;
  let timestamp = event.block.timestamp;

  // Update prosumer
  let prosumer = getOrCreateProsumer(user, timestamp);
  let oldTier = prosumer.tier;
  prosumer.reputation = newScore;
  prosumer.tier = getTierFromScore(newScore);
  prosumer.lastActivityAt = timestamp;
  prosumer.save();

  // Create reputation change record
  let changeId = generateReputationChangeId(event.transaction.hash, event.logIndex);
  let change = new ReputationChange(changeId);
  change.prosumer = prosumer.id;
  change.oldScore = oldScore;
  change.newScore = newScore;
  change.change = newScore - oldScore;
  change.reason = reason;
  change.oldTier = oldTier;
  change.newTier = prosumer.tier;
  change.tierChanged = oldTier != prosumer.tier;
  change.timestamp = timestamp;
  change.transactionHash = event.transaction.hash;
  change.save();
}

// ============ Tier Changes ============

export function handleTierChanged(event: TierChangedEvent): void {
  let user = event.params.user;
  let oldTier = event.params.oldTier;
  let newTier = event.params.newTier;
  let timestamp = event.block.timestamp;

  // Update prosumer tier
  let prosumer = getOrCreateProsumer(user, timestamp);
  prosumer.tier = getTierFromEnum(newTier);
  prosumer.lastActivityAt = timestamp;
  prosumer.save();

  // Note: ReputationChange is typically created by handleReputationUpdated
  // This handler is for explicit tier changes if any
}

// ============ Decay ============

export function handleDecayApplied(event: DecayAppliedEvent): void {
  let user = event.params.user;
  let decayAmount = event.params.decayAmount.toI32();
  let weeksInactive = event.params.weeksInactive.toI32();
  let timestamp = event.block.timestamp;

  // Update prosumer
  let prosumer = getOrCreateProsumer(user, timestamp);
  let oldScore = prosumer.reputation;
  let newScore = oldScore - decayAmount;
  if (newScore < 0) newScore = 0;

  let oldTier = prosumer.tier;
  prosumer.reputation = newScore;
  prosumer.tier = getTierFromScore(newScore);
  prosumer.lastActivityAt = timestamp;
  prosumer.save();

  // Create reputation change record
  let changeId = generateReputationChangeId(event.transaction.hash, event.logIndex);
  let change = new ReputationChange(changeId);
  change.prosumer = prosumer.id;
  change.oldScore = oldScore;
  change.newScore = newScore;
  change.change = -decayAmount;
  change.reason = "Inactivity decay (" + weeksInactive.toString() + " weeks)";
  change.oldTier = oldTier;
  change.newTier = prosumer.tier;
  change.tierChanged = oldTier != prosumer.tier;
  change.timestamp = timestamp;
  change.transactionHash = event.transaction.hash;
  change.save();
}

// ============ Flag/Unflag ============

export function handleUserFlagged(event: UserFlaggedEventEvent): void {
  let user = event.params.user;
  let reporter = event.params.reporter;
  let reason = event.params.reason;
  let timestamp = event.block.timestamp;

  // Update prosumer
  let prosumer = getOrCreateProsumer(user, timestamp);
  prosumer.isFlagged = true;
  prosumer.lastActivityAt = timestamp;
  prosumer.save();

  // Create reputation change record
  let changeId = generateReputationChangeId(event.transaction.hash, event.logIndex);
  let change = new ReputationChange(changeId);
  change.prosumer = prosumer.id;
  change.oldScore = prosumer.reputation;
  change.newScore = prosumer.reputation;
  change.change = 0;
  change.reason = "User flagged: " + reason;
  change.oldTier = prosumer.tier;
  change.newTier = prosumer.tier;
  change.tierChanged = false;
  change.timestamp = timestamp;
  change.transactionHash = event.transaction.hash;
  change.save();
}

export function handleUserUnflagged(event: UserUnflaggedEvent): void {
  let user = event.params.user;
  let admin = event.params.admin;
  let timestamp = event.block.timestamp;

  // Update prosumer
  let prosumer = getOrCreateProsumer(user, timestamp);
  prosumer.isFlagged = false;
  prosumer.lastActivityAt = timestamp;
  prosumer.save();

  // Create reputation change record
  let changeId = generateReputationChangeId(event.transaction.hash, event.logIndex);
  let change = new ReputationChange(changeId);
  change.prosumer = prosumer.id;
  change.oldScore = prosumer.reputation;
  change.newScore = prosumer.reputation;
  change.change = 0;
  change.reason = "User unflagged";
  change.oldTier = prosumer.tier;
  change.newTier = prosumer.tier;
  change.tierChanged = false;
  change.timestamp = timestamp;
  change.transactionHash = event.transaction.hash;
  change.save();
}

// ============ Stake Updates ============

export function handleStakeUpdated(event: StakeUpdatedEvent): void {
  let user = event.params.user;
  let oldStake = toDecimal(event.params.oldStake);
  let newStake = toDecimal(event.params.newStake);
  let timestamp = event.block.timestamp;

  // Update prosumer
  let prosumer = getOrCreateProsumer(user, timestamp);
  prosumer.stakedAmount = newStake;
  prosumer.lastActivityAt = timestamp;
  prosumer.save();
}

// ============ KYC Updates ============

export function handleKYCStatusUpdated(event: KYCStatusUpdatedEvent): void {
  let user = event.params.user;
  let verified = event.params.verified;
  let timestamp = event.block.timestamp;

  // Update prosumer
  let prosumer = getOrCreateProsumer(user, timestamp);
  prosumer.isKYCVerified = verified;
  prosumer.lastActivityAt = timestamp;
  prosumer.save();

  // Create reputation change record
  let changeId = generateReputationChangeId(event.transaction.hash, event.logIndex);
  let change = new ReputationChange(changeId);
  change.prosumer = prosumer.id;
  change.oldScore = prosumer.reputation;
  change.newScore = prosumer.reputation;
  change.change = 0;
  change.reason = verified ? "KYC verified" : "KYC revoked";
  change.oldTier = prosumer.tier;
  change.newTier = prosumer.tier;
  change.tierChanged = false;
  change.timestamp = timestamp;
  change.transactionHash = event.transaction.hash;
  change.save();
}
