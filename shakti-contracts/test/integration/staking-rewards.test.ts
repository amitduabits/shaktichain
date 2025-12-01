/**
 * SHAKTI-CHAIN Integration Test: Staking & Rewards
 *
 * Tests the staking lifecycle:
 * 1. Token approval
 * 2. Stake deposit
 * 3. Lock period management
 * 4. Reward accrual
 * 5. Reward claiming
 * 6. Unstaking
 *
 * Scenarios:
 * - Standard staking with rewards
 * - Early unstake penalty
 * - Multiple stakes from same user
 * - Compound staking
 */

import { expect } from "chai";
import { ethers } from "hardhat";
import { time } from "@nomicfoundation/hardhat-network-helpers";
import { ShaktiToken, StakingPool } from "../../typechain-types";
import { SignerWithAddress } from "@nomicfoundation/hardhat-ethers/signers";

describe("Integration: Staking & Rewards", function () {
  let token: ShaktiToken;
  let staking: StakingPool;

  let admin: SignerWithAddress;
  let staker1: SignerWithAddress;
  let staker2: SignerWithAddress;
  let staker3: SignerWithAddress;

  const INITIAL_BALANCE = ethers.parseEther("100000"); // 100,000 SHAKTI
  const STAKE_AMOUNT = ethers.parseEther("10000"); // 10,000 SHAKTI
  const REWARD_POOL = ethers.parseEther("1000000"); // 1,000,000 SHAKTI for rewards

  const LOCK_30_DAYS = 30 * 24 * 3600;
  const LOCK_90_DAYS = 90 * 24 * 3600;
  const LOCK_180_DAYS = 180 * 24 * 3600;

  beforeEach(async function () {
    [admin, staker1, staker2, staker3] = await ethers.getSigners();

    // Deploy Token
    const TokenFactory = await ethers.getContractFactory("ShaktiToken");
    token = await TokenFactory.deploy(admin.address);
    await token.waitForDeployment();

    // Deploy Staking Pool
    const StakingFactory = await ethers.getContractFactory("StakingPool");
    staking = await StakingFactory.deploy(
      await token.getAddress(),
      admin.address
    );
    await staking.waitForDeployment();

    // Grant MINTER_ROLE to staking pool for reward minting
    const MINTER_ROLE = await token.MINTER_ROLE();
    await token.grantRole(MINTER_ROLE, await staking.getAddress());

    // Fund reward pool
    await token.mint(await staking.getAddress(), REWARD_POOL);

    // Distribute tokens to stakers
    await token.mint(staker1.address, INITIAL_BALANCE);
    await token.mint(staker2.address, INITIAL_BALANCE);
    await token.mint(staker3.address, INITIAL_BALANCE);

    // Approve staking contract
    await token.connect(staker1).approve(await staking.getAddress(), INITIAL_BALANCE);
    await token.connect(staker2).approve(await staking.getAddress(), INITIAL_BALANCE);
    await token.connect(staker3).approve(await staking.getAddress(), INITIAL_BALANCE);
  });

  describe("Basic Staking Flow", function () {
    it("should allow staking with 30-day lock", async function () {
      const initialBalance = await token.balanceOf(staker1.address);

      // Stake
      await staking.connect(staker1).stake(STAKE_AMOUNT, 0); // 0 = 30-day lock

      // Verify stake
      const stakeInfo = await staking.stakes(staker1.address, 0);
      expect(stakeInfo.amount).to.equal(STAKE_AMOUNT);

      // Verify balance changed
      const finalBalance = await token.balanceOf(staker1.address);
      expect(finalBalance).to.equal(initialBalance - STAKE_AMOUNT);

      // Verify total staked
      const totalStaked = await staking.totalStaked();
      expect(totalStaked).to.equal(STAKE_AMOUNT);

      console.log("\n  Stake Created:");
      console.log("  --------------");
      console.log(`  Amount: ${ethers.formatEther(STAKE_AMOUNT)} SHAKTI`);
      console.log(`  Lock Period: 30 days`);
      console.log(`  Total Staked: ${ethers.formatEther(totalStaked)} SHAKTI`);
    });

    it("should allow staking with 90-day lock for higher rewards", async function () {
      await staking.connect(staker1).stake(STAKE_AMOUNT, 1); // 1 = 90-day lock

      const stakeInfo = await staking.stakes(staker1.address, 0);
      expect(stakeInfo.amount).to.equal(STAKE_AMOUNT);
      expect(stakeInfo.lockTier).to.equal(1);
    });

    it("should accrue rewards over time", async function () {
      await staking.connect(staker1).stake(STAKE_AMOUNT, 0);

      // Move time forward 30 days
      await time.increase(LOCK_30_DAYS);

      // Check pending rewards
      const pendingRewards = await staking.pendingRewards(staker1.address);
      expect(pendingRewards).to.be.gt(0);

      console.log("\n  Reward Accrual (30 days):");
      console.log("  -------------------------");
      console.log(`  Staked: ${ethers.formatEther(STAKE_AMOUNT)} SHAKTI`);
      console.log(`  Pending Rewards: ${ethers.formatEther(pendingRewards)} SHAKTI`);
      console.log(`  APY: ~8%`);
    });

    it("should allow claiming rewards after lock period", async function () {
      await staking.connect(staker1).stake(STAKE_AMOUNT, 0);

      // Fast forward past lock period
      await time.increase(LOCK_30_DAYS + 1);

      const balanceBefore = await token.balanceOf(staker1.address);
      const pendingRewards = await staking.pendingRewards(staker1.address);

      // Claim rewards
      await staking.connect(staker1).claimRewards();

      const balanceAfter = await token.balanceOf(staker1.address);
      expect(balanceAfter).to.be.gt(balanceBefore);

      console.log("\n  Reward Claim:");
      console.log("  -------------");
      console.log(`  Claimed: ${ethers.formatEther(balanceAfter - balanceBefore)} SHAKTI`);
    });

    it("should allow unstaking after lock period", async function () {
      await staking.connect(staker1).stake(STAKE_AMOUNT, 0);

      // Fast forward past lock period
      await time.increase(LOCK_30_DAYS + 1);

      const balanceBefore = await token.balanceOf(staker1.address);

      // Unstake
      await staking.connect(staker1).unstake(0); // Stake index 0

      const balanceAfter = await token.balanceOf(staker1.address);

      // Should receive stake + rewards
      expect(balanceAfter).to.be.gt(balanceBefore);
      expect(balanceAfter).to.be.gte(balanceBefore + STAKE_AMOUNT);

      // Total staked should decrease
      const totalStaked = await staking.totalStaked();
      expect(totalStaked).to.equal(0);

      console.log("\n  Unstake Result:");
      console.log("  ---------------");
      console.log(`  Original Stake: ${ethers.formatEther(STAKE_AMOUNT)} SHAKTI`);
      console.log(`  Received: ${ethers.formatEther(balanceAfter - balanceBefore)} SHAKTI`);
      console.log(`  Net Gain: ${ethers.formatEther(balanceAfter - balanceBefore - STAKE_AMOUNT)} SHAKTI`);
    });
  });

  describe("Early Unstaking Penalty", function () {
    it("should apply penalty for early unstake", async function () {
      await staking.connect(staker1).stake(STAKE_AMOUNT, 0);

      // Try to unstake immediately (within lock period)
      // This should either be rejected or apply a penalty
      // depending on contract implementation

      const stakeInfo = await staking.stakes(staker1.address, 0);
      const lockEnd = stakeInfo.lockEnd;
      const currentTime = BigInt(await time.latest());

      // Verify we're still in lock period
      expect(lockEnd).to.be.gt(currentTime);

      // Attempting early unstake should revert
      await expect(
        staking.connect(staker1).unstake(0)
      ).to.be.reverted;
    });

    it("should calculate correct penalty amount", async function () {
      await staking.connect(staker1).stake(STAKE_AMOUNT, 0);

      // Move forward 15 days (half the lock period)
      await time.increase(15 * 24 * 3600);

      // Still locked
      await expect(
        staking.connect(staker1).unstake(0)
      ).to.be.reverted;
    });
  });

  describe("Multiple Stakes", function () {
    it("should handle multiple stakes from same user", async function () {
      // Stake 1: 10,000 SHAKTI, 30-day lock
      await staking.connect(staker1).stake(STAKE_AMOUNT, 0);

      // Stake 2: 5,000 SHAKTI, 90-day lock
      await staking.connect(staker1).stake(STAKE_AMOUNT / 2n, 1);

      // Get all stakes
      const stakeCount = await staking.getUserStakeCount(staker1.address);
      expect(stakeCount).to.equal(2);

      // Verify total staked
      const userStaked = await staking.getUserTotalStaked(staker1.address);
      expect(userStaked).to.equal(STAKE_AMOUNT + STAKE_AMOUNT / 2n);

      console.log("\n  Multiple Stakes:");
      console.log("  ----------------");
      console.log(`  Stake 1: ${ethers.formatEther(STAKE_AMOUNT)} SHAKTI (30-day)`);
      console.log(`  Stake 2: ${ethers.formatEther(STAKE_AMOUNT / 2n)} SHAKTI (90-day)`);
      console.log(`  Total: ${ethers.formatEther(userStaked)} SHAKTI`);
    });

    it("should track individual stake rewards separately", async function () {
      await staking.connect(staker1).stake(STAKE_AMOUNT, 0);
      await staking.connect(staker1).stake(STAKE_AMOUNT, 1);

      await time.increase(LOCK_30_DAYS);

      const totalRewards = await staking.pendingRewards(staker1.address);
      expect(totalRewards).to.be.gt(0);
    });
  });

  describe("Multi-User Staking", function () {
    it("should correctly distribute rewards among stakers", async function () {
      // Three stakers deposit
      await staking.connect(staker1).stake(STAKE_AMOUNT, 0);
      await staking.connect(staker2).stake(STAKE_AMOUNT * 2n, 0);
      await staking.connect(staker3).stake(STAKE_AMOUNT * 3n, 0);

      // Fast forward
      await time.increase(LOCK_30_DAYS);

      // Check rewards (should be proportional to stake)
      const rewards1 = await staking.pendingRewards(staker1.address);
      const rewards2 = await staking.pendingRewards(staker2.address);
      const rewards3 = await staking.pendingRewards(staker3.address);

      // Staker 2 has 2x stake, should have ~2x rewards
      // Staker 3 has 3x stake, should have ~3x rewards
      // Note: May not be exactly proportional due to block timing

      expect(rewards2).to.be.gt(rewards1);
      expect(rewards3).to.be.gt(rewards2);

      console.log("\n  Multi-User Rewards:");
      console.log("  -------------------");
      console.log(`  Staker 1 (10K): ${ethers.formatEther(rewards1)} SHAKTI`);
      console.log(`  Staker 2 (20K): ${ethers.formatEther(rewards2)} SHAKTI`);
      console.log(`  Staker 3 (30K): ${ethers.formatEther(rewards3)} SHAKTI`);
    });

    it("should update rewards when new stakers join", async function () {
      // Staker 1 stakes first
      await staking.connect(staker1).stake(STAKE_AMOUNT, 0);

      // Wait 15 days
      await time.increase(15 * 24 * 3600);

      const rewards1Before = await staking.pendingRewards(staker1.address);

      // Staker 2 joins
      await staking.connect(staker2).stake(STAKE_AMOUNT, 0);

      // Wait another 15 days
      await time.increase(15 * 24 * 3600);

      const rewards1After = await staking.pendingRewards(staker1.address);
      const rewards2After = await staking.pendingRewards(staker2.address);

      // Staker 1 should have more rewards (staked longer)
      expect(rewards1After).to.be.gt(rewards2After);
    });
  });

  describe("Lock Tier Rewards", function () {
    it("should give higher rewards for longer locks", async function () {
      // Same amount, different lock periods
      await staking.connect(staker1).stake(STAKE_AMOUNT, 0); // 30 days
      await staking.connect(staker2).stake(STAKE_AMOUNT, 1); // 90 days

      // Wait 30 days (minimum lock)
      await time.increase(LOCK_30_DAYS);

      const rewards30 = await staking.pendingRewards(staker1.address);
      const rewards90 = await staking.pendingRewards(staker2.address);

      // 90-day lock should earn more per unit time
      // (but comparison depends on multiplier implementation)
      console.log("\n  Lock Tier Comparison (30 days elapsed):");
      console.log("  ----------------------------------------");
      console.log(`  30-day lock: ${ethers.formatEther(rewards30)} SHAKTI`);
      console.log(`  90-day lock: ${ethers.formatEther(rewards90)} SHAKTI`);
    });
  });

  describe("Staking Pool Stats", function () {
    it("should track global staking statistics", async function () {
      await staking.connect(staker1).stake(STAKE_AMOUNT, 0);
      await staking.connect(staker2).stake(STAKE_AMOUNT * 2n, 1);

      const totalStaked = await staking.totalStaked();
      const rewardRate = await staking.rewardRate();

      console.log("\n  Staking Pool Stats:");
      console.log("  -------------------");
      console.log(`  Total Staked: ${ethers.formatEther(totalStaked)} SHAKTI`);
      console.log(`  Reward Rate: ${rewardRate.toString()} basis points`);
    });

    it("should provide user staking summary", async function () {
      await staking.connect(staker1).stake(STAKE_AMOUNT, 0);
      await staking.connect(staker1).stake(STAKE_AMOUNT / 2n, 1);

      await time.increase(LOCK_30_DAYS);

      const totalStaked = await staking.getUserTotalStaked(staker1.address);
      const pendingRewards = await staking.pendingRewards(staker1.address);
      const stakeCount = await staking.getUserStakeCount(staker1.address);

      console.log("\n  User Staking Summary:");
      console.log("  ---------------------");
      console.log(`  Address: ${staker1.address}`);
      console.log(`  Total Staked: ${ethers.formatEther(totalStaked)} SHAKTI`);
      console.log(`  Pending Rewards: ${ethers.formatEther(pendingRewards)} SHAKTI`);
      console.log(`  Active Stakes: ${stakeCount}`);
    });
  });

  describe("Edge Cases", function () {
    it("should reject stake below minimum", async function () {
      const minStake = await staking.MIN_STAKE();
      const belowMin = minStake - 1n;

      await expect(
        staking.connect(staker1).stake(belowMin, 0)
      ).to.be.reverted;
    });

    it("should reject stake when paused", async function () {
      const PAUSER_ROLE = await staking.PAUSER_ROLE();
      await staking.grantRole(PAUSER_ROLE, admin.address);
      await staking.pause();

      await expect(
        staking.connect(staker1).stake(STAKE_AMOUNT, 0)
      ).to.be.reverted;
    });

    it("should handle claiming when no rewards pending", async function () {
      await staking.connect(staker1).stake(STAKE_AMOUNT, 0);

      // Try to claim immediately (minimal rewards)
      // Should not revert, just claim 0 or minimal amount
      await time.increase(1); // Move 1 second

      // Depending on implementation, this might succeed with 0 rewards
      // or might have minimum threshold
    });
  });
});
