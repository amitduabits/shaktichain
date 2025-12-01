/**
 * SHAKTI-CHAIN Security Tests: Edge Cases
 *
 * Tests boundary conditions, overflow/underflow, and edge cases.
 * Solidity 0.8+ provides built-in overflow protection, but we verify behavior.
 */

import { expect } from "chai";
import { ethers } from "hardhat";
import { loadFixture } from "@nomicfoundation/hardhat-network-helpers";
import { SignerWithAddress } from "@nomicfoundation/hardhat-ethers/signers";
import {
  ShaktiToken,
  EnergyAuction,
  StakingPool,
  EnergyEscrow,
  ReputationSystem,
} from "../../typechain-types";

describe("Security: Edge Cases", function () {
  let owner: SignerWithAddress;
  let user1: SignerWithAddress;
  let user2: SignerWithAddress;
  let shaktiToken: ShaktiToken;
  let stakingPool: StakingPool;
  let energyAuction: EnergyAuction;
  let energyEscrow: EnergyEscrow;
  let reputationSystem: ReputationSystem;

  async function deployContractsFixture() {
    [owner, user1, user2] = await ethers.getSigners();

    const ShaktiTokenFactory = await ethers.getContractFactory("ShaktiToken");
    shaktiToken = await ShaktiTokenFactory.deploy(owner.address, owner.address);

    const StakingPoolFactory = await ethers.getContractFactory("StakingPool");
    stakingPool = await StakingPoolFactory.deploy(
      await shaktiToken.getAddress(),
      owner.address,
      800
    );

    const EnergyAuctionFactory = await ethers.getContractFactory("EnergyAuction");
    energyAuction = await EnergyAuctionFactory.deploy(
      await shaktiToken.getAddress(),
      ethers.ZeroAddress,
      owner.address,
      ethers.parseEther("0.001"),
      ethers.parseEther("0.01")
    );

    const EnergyEscrowFactory = await ethers.getContractFactory("EnergyEscrow");
    energyEscrow = await EnergyEscrowFactory.deploy(
      await shaktiToken.getAddress(),
      owner.address,
      owner.address,
      200,
      3000
    );

    const ReputationSystemFactory = await ethers.getContractFactory("ReputationSystem");
    reputationSystem = await ReputationSystemFactory.deploy(owner.address);

    // Setup
    await shaktiToken.transfer(user1.address, ethers.parseEther("100000"));
    await shaktiToken.transfer(user2.address, ethers.parseEther("100000"));

    // Fund staking pool with reward tokens
    await shaktiToken.transfer(await stakingPool.getAddress(), ethers.parseEther("1000000"));

    return { shaktiToken, stakingPool, energyAuction, energyEscrow, reputationSystem };
  }

  describe("Integer Overflow/Underflow Protection", function () {
    beforeEach(async function () {
      await loadFixture(deployContractsFixture);
    });

    it("Token mint cannot exceed MAX_SUPPLY", async function () {
      const maxSupply = await shaktiToken.MAX_SUPPLY();
      const currentSupply = await shaktiToken.totalSupply();
      const remaining = maxSupply - currentSupply;

      // Try to mint more than remaining
      await expect(
        shaktiToken.mint(owner.address, remaining + 1n)
      ).to.be.revertedWithCustomError(shaktiToken, "ExceedsMaxSupply");
    });

    it("StakingPool reward calculation handles large time spans", async function () {
      await shaktiToken.connect(user1).approve(
        await stakingPool.getAddress(),
        ethers.MaxUint256
      );
      await stakingPool.connect(user1).stake(ethers.parseEther("1000"), 0);

      // Fast forward 10 years
      await ethers.provider.send("evm_increaseTime", [10 * 365 * 86400]);
      await ethers.provider.send("evm_mine", []);

      // Should not overflow
      const rewards = await stakingPool.getRewards(user1.address);
      expect(rewards).to.be.gt(0);
    });

    it("Reputation score capped at MAX_REPUTATION", async function () {
      await reputationSystem.registerUser(user1.address);

      // Grant reporter role
      const REPORTER_ROLE = await reputationSystem.REPORTER_ROLE();
      await reputationSystem.grantRole(REPORTER_ROLE, owner.address);

      // Try to add excessive reputation
      await reputationSystem.updateReputation(user1.address, 10000, 6); // AdminAdjustment

      const rep = await reputationSystem.getUserReputation(user1.address);
      expect(rep.score).to.lte(1000); // MAX_REPUTATION
    });

    it("Reputation score floored at 0", async function () {
      await reputationSystem.registerUser(user1.address);

      const REPORTER_ROLE = await reputationSystem.REPORTER_ROLE();
      await reputationSystem.grantRole(REPORTER_ROLE, owner.address);

      // Try to subtract more than current score
      await reputationSystem.updateReputation(user1.address, -10000, 6);

      const rep = await reputationSystem.getUserReputation(user1.address);
      expect(rep.score).to.equal(0);
    });

    it("Fee calculation handles small amounts", async function () {
      const fees = await energyEscrow.calculateFees(1);

      // Should handle 1 wei without issues
      expect(fees.platformFee).to.be.gte(0);
    });

    it("Fee calculation handles large amounts", async function () {
      const largeAmount = ethers.parseEther("1000000000"); // 1 billion
      const fees = await energyEscrow.calculateFees(largeAmount);

      // Should calculate correctly
      expect(fees.platformFee).to.be.gt(0);
      expect(fees.sellerAmount).to.be.gt(0);
      expect(fees.platformFee + fees.sellerAmount).to.equal(largeAmount);
    });
  });

  describe("Zero Value Handling", function () {
    beforeEach(async function () {
      await loadFixture(deployContractsFixture);
    });

    it("Cannot stake zero tokens", async function () {
      await expect(
        stakingPool.connect(user1).stake(0, 0)
      ).to.be.revertedWithCustomError(stakingPool, "ZeroAmount");
    });

    it("Cannot unstake zero tokens", async function () {
      await shaktiToken.connect(user1).approve(
        await stakingPool.getAddress(),
        ethers.MaxUint256
      );
      await stakingPool.connect(user1).stake(ethers.parseEther("100"), 0);

      await expect(
        stakingPool.connect(user1).unstake(0)
      ).to.be.revertedWithCustomError(stakingPool, "ZeroAmount");
    });

    it("Cannot submit bid with zero quantity", async function () {
      await energyAuction.createAuctionRound(600);
      await shaktiToken.connect(user1).approve(
        await energyAuction.getAddress(),
        ethers.MaxUint256
      );

      await expect(
        energyAuction.connect(user1).submitBid(0, ethers.parseEther("0.005"))
      ).to.be.revertedWithCustomError(energyAuction, "InvalidQuantity");
    });

    it("Cannot deposit zero to escrow", async function () {
      await expect(
        energyEscrow.connect(user1).deposit(1, 0)
      ).to.be.revertedWithCustomError(energyEscrow, "ZeroAmount");
    });

    it("Cannot withdraw zero from escrow", async function () {
      await shaktiToken.connect(user1).approve(
        await energyEscrow.getAddress(),
        ethers.MaxUint256
      );
      await energyEscrow.connect(user1).deposit(1, ethers.parseEther("100"));

      await expect(
        energyEscrow.connect(user1).withdraw(1, 0)
      ).to.be.revertedWithCustomError(energyEscrow, "ZeroAmount");
    });

    it("Token mint rejects zero amount", async function () {
      await expect(
        shaktiToken.mint(user1.address, 0)
      ).to.be.revertedWithCustomError(shaktiToken, "ZeroAmount");
    });

    it("Token burnFees rejects zero amount", async function () {
      await expect(
        shaktiToken.burnFees(0)
      ).to.be.revertedWithCustomError(shaktiToken, "ZeroAmount");
    });
  });

  describe("Boundary Conditions", function () {
    beforeEach(async function () {
      await loadFixture(deployContractsFixture);
    });

    it("Staking at exact minimum amount", async function () {
      const minStake = await stakingPool.MINIMUM_STAKE();
      await shaktiToken.connect(user1).approve(
        await stakingPool.getAddress(),
        ethers.MaxUint256
      );

      await expect(
        stakingPool.connect(user1).stake(minStake, 0)
      ).to.not.be.reverted;
    });

    it("Staking just below minimum amount", async function () {
      const minStake = await stakingPool.MINIMUM_STAKE();
      await shaktiToken.connect(user1).approve(
        await stakingPool.getAddress(),
        ethers.MaxUint256
      );

      await expect(
        stakingPool.connect(user1).stake(minStake - 1n, 0)
      ).to.be.revertedWithCustomError(stakingPool, "BelowMinimumStake");
    });

    it("Auction order at exact minimum quantity", async function () {
      await energyAuction.createAuctionRound(600);
      await shaktiToken.connect(user1).approve(
        await energyAuction.getAddress(),
        ethers.MaxUint256
      );

      const minQty = await energyAuction.MIN_QUANTITY();

      await expect(
        energyAuction.connect(user1).submitBid(minQty, ethers.parseEther("0.005"))
      ).to.not.be.reverted;
    });

    it("Auction order at exact maximum quantity", async function () {
      await energyAuction.createAuctionRound(600);
      await shaktiToken.connect(user1).approve(
        await energyAuction.getAddress(),
        ethers.MaxUint256
      );

      const maxQty = await energyAuction.MAX_QUANTITY();

      await expect(
        energyAuction.connect(user1).submitBid(maxQty, ethers.parseEther("0.005"))
      ).to.not.be.reverted;
    });

    it("Auction order at exact minimum price", async function () {
      await energyAuction.createAuctionRound(600);
      await shaktiToken.connect(user1).approve(
        await energyAuction.getAddress(),
        ethers.MaxUint256
      );

      const minPrice = await energyAuction.minPrice();

      await expect(
        energyAuction.connect(user1).submitBid(2000, minPrice)
      ).to.not.be.reverted;
    });

    it("Auction order at exact maximum price", async function () {
      await energyAuction.createAuctionRound(600);
      await shaktiToken.connect(user1).approve(
        await energyAuction.getAddress(),
        ethers.MaxUint256
      );

      const maxPrice = await energyAuction.maxPrice();

      await expect(
        energyAuction.connect(user1).submitBid(2000, maxPrice)
      ).to.not.be.reverted;
    });

    it("Auction duration at exact minimum", async function () {
      const minDuration = await energyAuction.MIN_DURATION();

      await expect(
        energyAuction.createAuctionRound(minDuration)
      ).to.not.be.reverted;
    });

    it("Auction duration at exact maximum", async function () {
      const maxDuration = await energyAuction.MAX_DURATION();

      await expect(
        energyAuction.createAuctionRound(maxDuration)
      ).to.not.be.reverted;
    });

    it("Lock period exactly 30 days", async function () {
      await shaktiToken.connect(user1).approve(
        await stakingPool.getAddress(),
        ethers.MaxUint256
      );

      const lock30 = await stakingPool.LOCK_30_DAYS();

      await expect(
        stakingPool.connect(user1).stake(ethers.parseEther("100"), lock30)
      ).to.not.be.reverted;

      const stakeInfo = await stakingPool.getStakeInfo(user1.address);
      expect(stakeInfo.lockPeriod).to.equal(lock30);
    });

    it("Lock period exactly 90 days", async function () {
      await shaktiToken.connect(user1).approve(
        await stakingPool.getAddress(),
        ethers.MaxUint256
      );

      const lock90 = await stakingPool.LOCK_90_DAYS();

      await expect(
        stakingPool.connect(user1).stake(ethers.parseEther("100"), lock90)
      ).to.not.be.reverted;
    });

    it("Invalid lock period rejected", async function () {
      await shaktiToken.connect(user1).approve(
        await stakingPool.getAddress(),
        ethers.MaxUint256
      );

      // 15 days is not a valid lock period
      await expect(
        stakingPool.connect(user1).stake(ethers.parseEther("100"), 15 * 86400)
      ).to.be.revertedWithCustomError(stakingPool, "InvalidLockPeriod");
    });
  });

  describe("Timestamp Edge Cases", function () {
    beforeEach(async function () {
      await loadFixture(deployContractsFixture);
    });

    it("Auction ends exactly at endTime", async function () {
      await energyAuction.createAuctionRound(600);

      const round = await energyAuction.getAuctionRound(1);
      const endTime = round.endTime;

      // Move to exact end time
      const currentBlock = await ethers.provider.getBlock("latest");
      const timeToEnd = Number(endTime) - currentBlock!.timestamp;

      await ethers.provider.send("evm_increaseTime", [timeToEnd]);
      await ethers.provider.send("evm_mine", []);

      // Cannot submit bid at or after endTime
      await shaktiToken.connect(user1).approve(
        await energyAuction.getAddress(),
        ethers.MaxUint256
      );

      await expect(
        energyAuction.connect(user1).submitBid(2000, ethers.parseEther("0.005"))
      ).to.be.revertedWithCustomError(energyAuction, "AuctionAlreadyEnded");
    });

    it("Lock period expires exactly on time", async function () {
      await shaktiToken.connect(user1).approve(
        await stakingPool.getAddress(),
        ethers.MaxUint256
      );

      const lock30 = await stakingPool.LOCK_30_DAYS();
      await stakingPool.connect(user1).stake(ethers.parseEther("100"), lock30);

      // Move to exact unlock time
      await ethers.provider.send("evm_increaseTime", [Number(lock30)]);
      await ethers.provider.send("evm_mine", []);

      // Should be able to unstake
      await expect(
        stakingPool.connect(user1).unstake(ethers.parseEther("100"))
      ).to.not.be.reverted;
    });

    it("Dispute window expires exactly at deadline", async function () {
      const AUCTION_ROLE = await energyEscrow.AUCTION_ROLE();
      await energyEscrow.grantRole(AUCTION_ROLE, owner.address);

      await shaktiToken.approve(await energyEscrow.getAddress(), ethers.MaxUint256);
      await energyEscrow.deposit(1, ethers.parseEther("1000"));
      await energyEscrow.createSettlement(1, owner.address, user1.address, 1000, ethers.parseEther("0.005"));

      const settlement = await energyEscrow.getSettlement(0);
      const deadline = settlement.disputeDeadline;

      // Move to just before deadline
      const currentBlock = await ethers.provider.getBlock("latest");
      const timeToDeadline = Number(deadline) - currentBlock!.timestamp - 1;

      await ethers.provider.send("evm_increaseTime", [timeToDeadline]);
      await ethers.provider.send("evm_mine", []);

      // Can still raise dispute
      await expect(
        energyEscrow.connect(user1).raiseDispute(0, "test")
      ).to.not.be.reverted;
    });
  });

  describe("Empty State Handling", function () {
    beforeEach(async function () {
      await loadFixture(deployContractsFixture);
    });

    it("Unstake when no stake exists", async function () {
      await expect(
        stakingPool.connect(user1).unstake(ethers.parseEther("100"))
      ).to.be.revertedWithCustomError(stakingPool, "NoStakeFound");
    });

    it("Claim rewards when no stake exists", async function () {
      await expect(
        stakingPool.connect(user1).claimRewards()
      ).to.be.revertedWithCustomError(stakingPool, "NoRewardsToClaim");
    });

    it("Emergency withdraw when no stake exists", async function () {
      await expect(
        stakingPool.connect(user1).emergencyWithdraw()
      ).to.be.revertedWithCustomError(stakingPool, "NoStakeFound");
    });

    it("Get rewards for non-staker returns 0", async function () {
      const rewards = await stakingPool.getRewards(user1.address);
      expect(rewards).to.equal(0);
    });

    it("Get reputation for non-registered user", async function () {
      const rep = await reputationSystem.getReputation(user1.address);
      expect(rep.score).to.equal(0);
      expect(rep.tier).to.equal(0); // Bronze
    });

    it("Clear market with no orders", async function () {
      await energyAuction.createAuctionRound(600);

      await ethers.provider.send("evm_increaseTime", [601]);
      await ethers.provider.send("evm_mine", []);

      await energyAuction.closeAuction(1);

      // Should handle gracefully
      await expect(
        energyAuction.clearMarket(1)
      ).to.not.be.reverted;
    });

    it("Get current auction when none exists", async function () {
      const auction = await energyAuction.getCurrentAuction();
      expect(auction.roundId).to.equal(0);
    });
  });

  describe("Rounding and Precision", function () {
    beforeEach(async function () {
      await loadFixture(deployContractsFixture);
    });

    it("Fee calculation rounds correctly", async function () {
      // Test with odd amount that doesn't divide evenly
      const amount = ethers.parseEther("333.333333");
      const fees = await energyEscrow.calculateFees(amount);

      // Verify no precision loss (total = seller + fee)
      expect(fees.sellerAmount + fees.platformFee).to.equal(amount);
    });

    it("Reward calculation precision maintained", async function () {
      await shaktiToken.connect(user1).approve(
        await stakingPool.getAddress(),
        ethers.MaxUint256
      );
      // Use minimum stake (100 tokens) to test precision at boundary
      const minStake = await stakingPool.MINIMUM_STAKE();
      await stakingPool.connect(user1).stake(minStake, 0);

      // Even minimum stakes should earn some rewards over time
      await ethers.provider.send("evm_increaseTime", [365 * 86400]);
      await ethers.provider.send("evm_mine", []);

      const rewards = await stakingPool.getRewards(user1.address);
      expect(rewards).to.be.gt(0);
    });

    it("Price precision in auction", async function () {
      await energyAuction.createAuctionRound(600);
      await shaktiToken.connect(user1).approve(
        await energyAuction.getAddress(),
        ethers.MaxUint256
      );
      await shaktiToken.connect(user2).approve(
        await energyAuction.getAddress(),
        ethers.MaxUint256
      );

      // Submit with precise prices
      await energyAuction.connect(user1).submitBid(2000, ethers.parseEther("0.005123456789"));
      await energyAuction.connect(user2).submitAsk(2000, ethers.parseEther("0.004987654321"));

      await ethers.provider.send("evm_increaseTime", [601]);
      await ethers.provider.send("evm_mine", []);

      await energyAuction.closeAuction(1);
      await energyAuction.clearMarket(1);

      const round = await energyAuction.getAuctionRound(1);
      expect(round.clearingPrice).to.be.gt(0);
    });
  });

  describe("Storage Collision Prevention", function () {
    beforeEach(async function () {
      await loadFixture(deployContractsFixture);
    });

    it("Different users have separate stake storage", async function () {
      await shaktiToken.connect(user1).approve(
        await stakingPool.getAddress(),
        ethers.MaxUint256
      );
      await shaktiToken.connect(user2).approve(
        await stakingPool.getAddress(),
        ethers.MaxUint256
      );

      await stakingPool.connect(user1).stake(ethers.parseEther("1000"), 0);
      await stakingPool.connect(user2).stake(ethers.parseEther("500"), 0);

      const stake1 = await stakingPool.getStakeInfo(user1.address);
      const stake2 = await stakingPool.getStakeInfo(user2.address);

      expect(stake1.amount).to.equal(ethers.parseEther("1000"));
      expect(stake2.amount).to.equal(ethers.parseEther("500"));
    });

    it("Different auction rounds have separate storage", async function () {
      await energyAuction.createAuctionRound(300);

      await ethers.provider.send("evm_increaseTime", [301]);
      await ethers.provider.send("evm_mine", []);

      await energyAuction.closeAuction(1);
      await energyAuction.clearMarket(1);

      // Create second round
      await energyAuction.createAuctionRound(300);

      const round1 = await energyAuction.getAuctionRound(1);
      const round2 = await energyAuction.getAuctionRound(2);

      expect(round1.roundId).to.equal(1);
      expect(round2.roundId).to.equal(2);
    });
  });

  describe("Reentrancy via Callback Prevention", function () {
    it("Token callbacks cannot reenter staking", async function () {
      // ShaktiToken is standard ERC20, no callback mechanism
      // This is a documentation test that callbacks are not used
      await shaktiToken.connect(user1).approve(
        await stakingPool.getAddress(),
        ethers.MaxUint256
      );

      await expect(
        stakingPool.connect(user1).stake(ethers.parseEther("100"), 0)
      ).to.not.be.reverted;
    });
  });
});
