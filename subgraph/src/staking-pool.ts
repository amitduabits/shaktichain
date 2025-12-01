import { BigInt, BigDecimal, Address } from "@graphprotocol/graph-ts";
import {
  Staked as StakedEvent,
  Unstaked as UnstakedEvent,
  RewardsClaimed as RewardsClaimedEvent,
  RewardsDistributed as RewardsDistributedEvent,
  EmergencyWithdraw as EmergencyWithdrawEvent,
} from "../generated/StakingPool/StakingPool";
import {
  Stake,
  Prosumer,
  StakingPoolSnapshot,
  Protocol,
  DailyStats,
} from "../generated/schema";
import {
  ZERO_BD,
  ZERO_BI,
  ONE_BI,
  toDecimal,
  getOrCreateProtocol,
  getOrCreateProsumer,
  getOrCreateDailyStats,
  generateStakeId,
} from "./helpers";

// ============ Staking Handlers ============

export function handleStaked(event: StakedEvent): void {
  let staker = event.params.staker;
  let amount = toDecimal(event.params.amount);
  let shares = toDecimal(event.params.shares);
  let timestamp = event.block.timestamp;

  // Get or create stake entity
  let stakeId = generateStakeId(staker);
  let stake = Stake.load(stakeId);

  if (stake == null) {
    stake = new Stake(stakeId);
    stake.staker = staker.toHexString();
    stake.amount = ZERO_BD;
    stake.shares = ZERO_BD;
    stake.pendingRewards = ZERO_BD;
    stake.totalRewardsClaimed = ZERO_BD;
    stake.stakedAt = timestamp;
    stake.lastClaimAt = null;
    stake.lockEndTime = null;
    stake.isLocked = false;

    // Update protocol staker count
    let protocol = getOrCreateProtocol();
    protocol.totalStakers = protocol.totalStakers + 1;
    protocol.save();
  }

  stake.amount = stake.amount.plus(amount);
  stake.shares = stake.shares.plus(shares);
  stake.save();

  // Update prosumer
  let prosumer = getOrCreateProsumer(staker, timestamp);
  prosumer.stakedAmount = prosumer.stakedAmount.plus(amount);
  prosumer.lastActivityAt = timestamp;
  prosumer.save();

  // Update protocol
  let protocol = getOrCreateProtocol();
  protocol.totalStaked = protocol.totalStaked.plus(amount);
  protocol.lastUpdatedAt = timestamp;
  protocol.save();

  // Update daily stats
  let dailyStats = getOrCreateDailyStats(timestamp);
  dailyStats.totalStaked = dailyStats.totalStaked.plus(amount);
  dailyStats.save();

  // Create snapshot
  createStakingSnapshot(event.block.timestamp, event.block.number);
}

export function handleUnstaked(event: UnstakedEvent): void {
  let staker = event.params.staker;
  let amount = toDecimal(event.params.amount);
  let shares = toDecimal(event.params.shares);
  let timestamp = event.block.timestamp;

  let stakeId = generateStakeId(staker);
  let stake = Stake.load(stakeId);

  if (stake != null) {
    stake.amount = stake.amount.minus(amount);
    stake.shares = stake.shares.minus(shares);

    // Check if fully unstaked
    if (stake.amount.equals(ZERO_BD)) {
      // Update protocol staker count
      let protocol = getOrCreateProtocol();
      protocol.totalStakers = protocol.totalStakers - 1;
      protocol.save();
    }

    stake.save();
  }

  // Update prosumer
  let prosumer = getOrCreateProsumer(staker, timestamp);
  prosumer.stakedAmount = prosumer.stakedAmount.minus(amount);
  prosumer.lastActivityAt = timestamp;
  prosumer.save();

  // Update protocol
  let protocol = getOrCreateProtocol();
  protocol.totalStaked = protocol.totalStaked.minus(amount);
  protocol.lastUpdatedAt = timestamp;
  protocol.save();

  // Create snapshot
  createStakingSnapshot(timestamp, event.block.number);
}

export function handleRewardsClaimed(event: RewardsClaimedEvent): void {
  let staker = event.params.staker;
  let amount = toDecimal(event.params.amount);
  let timestamp = event.block.timestamp;

  let stakeId = generateStakeId(staker);
  let stake = Stake.load(stakeId);

  if (stake != null) {
    stake.totalRewardsClaimed = stake.totalRewardsClaimed.plus(amount);
    stake.pendingRewards = ZERO_BD;
    stake.lastClaimAt = timestamp;
    stake.save();
  }

  // Update prosumer
  let prosumer = getOrCreateProsumer(staker, timestamp);
  prosumer.lastActivityAt = timestamp;
  prosumer.save();

  // Update daily stats
  let dailyStats = getOrCreateDailyStats(timestamp);
  dailyStats.stakingRewards = dailyStats.stakingRewards.plus(amount);
  dailyStats.save();
}

export function handleRewardsDistributed(event: RewardsDistributedEvent): void {
  let totalRewards = toDecimal(event.params.totalRewards);
  let rewardPerShare = toDecimal(event.params.rewardPerShare);
  let timestamp = event.block.timestamp;

  // Update daily stats
  let dailyStats = getOrCreateDailyStats(timestamp);
  dailyStats.stakingRewards = dailyStats.stakingRewards.plus(totalRewards);
  dailyStats.save();

  // Create snapshot with reward rate
  let snapshot = createStakingSnapshot(timestamp, event.block.number);
  snapshot.rewardRate = rewardPerShare;
  snapshot.totalRewardsDistributed = snapshot.totalRewardsDistributed.plus(totalRewards);
  snapshot.save();
}

export function handleEmergencyWithdraw(event: EmergencyWithdrawEvent): void {
  let staker = event.params.staker;
  let amount = toDecimal(event.params.amount);
  let timestamp = event.block.timestamp;

  let stakeId = generateStakeId(staker);
  let stake = Stake.load(stakeId);

  if (stake != null) {
    let previousAmount = stake.amount;
    stake.amount = ZERO_BD;
    stake.shares = ZERO_BD;
    stake.pendingRewards = ZERO_BD;
    stake.save();

    // Update prosumer
    let prosumer = getOrCreateProsumer(staker, timestamp);
    prosumer.stakedAmount = ZERO_BD;
    prosumer.lastActivityAt = timestamp;
    prosumer.save();

    // Update protocol
    let protocol = getOrCreateProtocol();
    protocol.totalStaked = protocol.totalStaked.minus(previousAmount);
    protocol.totalStakers = protocol.totalStakers - 1;
    protocol.lastUpdatedAt = timestamp;
    protocol.save();
  }
}

// ============ Snapshot Helper ============

function createStakingSnapshot(timestamp: BigInt, blockNumber: BigInt): StakingPoolSnapshot {
  let id = "snapshot-" + timestamp.toString();
  let snapshot = new StakingPoolSnapshot(id);

  let protocol = getOrCreateProtocol();

  snapshot.timestamp = timestamp;
  snapshot.blockNumber = blockNumber;
  snapshot.totalStaked = protocol.totalStaked;
  snapshot.totalShares = ZERO_BD; // Would need to query contract for this
  snapshot.rewardRate = ZERO_BD;
  snapshot.totalRewardsDistributed = ZERO_BD;
  snapshot.stakerCount = protocol.totalStakers;
  snapshot.apr = ZERO_BD; // Calculated externally

  snapshot.save();

  return snapshot;
}
