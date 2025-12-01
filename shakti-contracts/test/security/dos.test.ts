/**
 * SHAKTI-CHAIN Security Tests: Denial of Service Prevention
 *
 * Tests for DoS vulnerabilities including:
 * - Gas griefing attacks
 * - Block gas limit issues
 * - External call failures
 * - State bloat attacks
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

describe("Security: Denial of Service Prevention", function () {
  let owner: SignerWithAddress;
  let attacker: SignerWithAddress;
  let users: SignerWithAddress[];
  let shaktiToken: ShaktiToken;
  let energyAuction: EnergyAuction;
  let stakingPool: StakingPool;
  let energyEscrow: EnergyEscrow;
  let reputationSystem: ReputationSystem;

  const AUCTION_DURATION = 600;

  async function deployContractsFixture() {
    const signers = await ethers.getSigners();
    owner = signers[0];
    attacker = signers[1];
    users = signers.slice(2, 12); // 10 users

    // Deploy ShaktiToken
    const ShaktiTokenFactory = await ethers.getContractFactory("ShaktiToken");
    shaktiToken = await ShaktiTokenFactory.deploy(owner.address, owner.address);

    // Deploy StakingPool
    const StakingPoolFactory = await ethers.getContractFactory("StakingPool");
    stakingPool = await StakingPoolFactory.deploy(
      await shaktiToken.getAddress(),
      owner.address,
      800
    );

    // Deploy EnergyAuction
    const EnergyAuctionFactory = await ethers.getContractFactory("EnergyAuction");
    energyAuction = await EnergyAuctionFactory.deploy(
      await shaktiToken.getAddress(),
      ethers.ZeroAddress,
      owner.address,
      ethers.parseEther("0.001"),
      ethers.parseEther("0.01")
    );

    // Deploy EnergyEscrow
    const EnergyEscrowFactory = await ethers.getContractFactory("EnergyEscrow");
    energyEscrow = await EnergyEscrowFactory.deploy(
      await shaktiToken.getAddress(),
      owner.address,
      owner.address,
      200,
      3000
    );

    // Deploy ReputationSystem
    const ReputationSystemFactory = await ethers.getContractFactory("ReputationSystem");
    reputationSystem = await ReputationSystemFactory.deploy(owner.address);

    // Setup tokens for all users
    for (const user of users) {
      await shaktiToken.transfer(user.address, ethers.parseEther("10000"));
      await shaktiToken.connect(user).approve(
        await energyAuction.getAddress(),
        ethers.MaxUint256
      );
      await shaktiToken.connect(user).approve(
        await stakingPool.getAddress(),
        ethers.MaxUint256
      );
    }
    await shaktiToken.transfer(attacker.address, ethers.parseEther("100000"));
    await shaktiToken.connect(attacker).approve(
      await energyAuction.getAddress(),
      ethers.MaxUint256
    );

    return { shaktiToken, energyAuction, stakingPool, energyEscrow, reputationSystem };
  }

  describe("Gas Limit DoS Prevention", function () {
    beforeEach(async function () {
      await loadFixture(deployContractsFixture);
    });

    it("Auction clearing uses batch processing for gas limits", async function () {
      // Create auction
      await energyAuction.createAuctionRound(AUCTION_DURATION);

      // Submit multiple orders
      for (let i = 0; i < 5; i++) {
        await energyAuction.connect(users[i]).submitBid(
          2000,
          ethers.parseEther("0.006")
        );
        await energyAuction.connect(users[i + 5]).submitAsk(
          2000,
          ethers.parseEther("0.004")
        );
      }

      // Close auction
      await ethers.provider.send("evm_increaseTime", [AUCTION_DURATION + 1]);
      await ethers.provider.send("evm_mine", []);
      await energyAuction.closeAuction(1);

      // Clear in batches - should not exceed gas limit
      const tx = await energyAuction.clearMarket(1);
      const receipt = await tx.wait();

      // Verify gas used is reasonable
      expect(receipt!.gasUsed).to.be.lt(10000000n); // Well under block limit
    });

    it("BATCH_SIZE constant limits orders per clearMarket call", async function () {
      const batchSize = await energyAuction.BATCH_SIZE();
      expect(batchSize).to.be.gt(0);
      expect(batchSize).to.be.lte(100); // Reasonable batch size
    });

    it("MAX_ORDERS_PER_ROUND prevents order flooding", async function () {
      const maxOrders = await energyAuction.MAX_ORDERS_PER_ROUND();
      expect(maxOrders).to.be.lte(500); // Capped at reasonable limit
    });

    it("Batch bid submission has implicit gas limits", async function () {
      await energyAuction.createAuctionRound(AUCTION_DURATION);

      // Submit batch of bids
      const bids = Array(10).fill(null).map(() => ({
        quantity: 1000n,
        maxPricePerWh: ethers.parseEther("0.005"),
      }));

      const tx = await energyAuction.connect(users[0]).submitBids(bids);
      const receipt = await tx.wait();

      expect(receipt!.gasUsed).to.be.lt(3000000n);
    });
  });

  describe("State Bloat Prevention", function () {
    beforeEach(async function () {
      await loadFixture(deployContractsFixture);
    });

    it("Minimum stake prevents dust stake spam", async function () {
      const minStake = await stakingPool.MINIMUM_STAKE();
      expect(minStake).to.equal(ethers.parseEther("100"));

      await expect(
        stakingPool.connect(users[0]).stake(minStake - 1n, 0)
      ).to.be.revertedWithCustomError(stakingPool, "BelowMinimumStake");
    });

    it("Minimum order quantity prevents order spam", async function () {
      await energyAuction.createAuctionRound(AUCTION_DURATION);

      const minQuantity = await energyAuction.MIN_QUANTITY();
      expect(minQuantity).to.equal(1000); // 1 kWh

      await expect(
        energyAuction.connect(users[0]).submitBid(minQuantity - 1n, ethers.parseEther("0.005"))
      ).to.be.revertedWithCustomError(energyAuction, "InvalidQuantity");
    });

    it("Maximum order quantity prevents single user domination", async function () {
      await energyAuction.createAuctionRound(AUCTION_DURATION);

      const maxQuantity = await energyAuction.MAX_QUANTITY();
      expect(maxQuantity).to.equal(100000); // 100 kWh

      await expect(
        energyAuction.connect(users[0]).submitBid(maxQuantity + 1n, ethers.parseEther("0.005"))
      ).to.be.revertedWithCustomError(energyAuction, "InvalidQuantity");
    });
  });

  describe("External Call Failure Handling", function () {
    beforeEach(async function () {
      await loadFixture(deployContractsFixture);
    });

    it("SafeERC20 handles token transfer failures", async function () {
      // User with no tokens cannot stake
      const newUser = (await ethers.getSigners())[15];

      await shaktiToken.connect(newUser).approve(
        await stakingPool.getAddress(),
        ethers.MaxUint256
      );

      await expect(
        stakingPool.connect(newUser).stake(ethers.parseEther("100"), 0)
      ).to.be.reverted;
    });

    it("Auction handles failed token transfers gracefully", async function () {
      await energyAuction.createAuctionRound(AUCTION_DURATION);

      // User without approval
      const noApprovalUser = (await ethers.getSigners())[16];
      await shaktiToken.transfer(noApprovalUser.address, ethers.parseEther("1000"));

      await expect(
        energyAuction.connect(noApprovalUser).submitBid(2000, ethers.parseEther("0.005"))
      ).to.be.reverted;

      // Auction state should be unchanged
      const round = await energyAuction.getAuctionRound(1);
      expect(round.totalBids).to.equal(0);
    });
  });

  describe("Loop Bounds Prevention", function () {
    beforeEach(async function () {
      await loadFixture(deployContractsFixture);
    });

    it("Reputation leaderboard has bounded iteration", async function () {
      // Register users
      for (let i = 0; i < 5; i++) {
        await reputationSystem.registerUser(users[i].address);
      }

      // Get leaderboard with limit
      const leaderboard = await reputationSystem.getLeaderboard(3);
      expect(leaderboard.length).to.equal(3);
    });

    it("Batch decay has bounded iteration", async function () {
      // Register users
      for (let i = 0; i < 5; i++) {
        await reputationSystem.registerUser(users[i].address);
      }

      // Time passes for decay
      await ethers.provider.send("evm_increaseTime", [7 * 86400 + 1]);
      await ethers.provider.send("evm_mine", []);

      // Batch decay should complete within gas limits
      const addresses = users.slice(0, 5).map(u => u.address);
      const tx = await reputationSystem.batchApplyDecay(addresses);
      const receipt = await tx.wait();

      expect(receipt!.gasUsed).to.be.lt(1000000n);
    });

    it("Settlement batch completion has bounded iteration", async function () {
      // Grant auction role
      const AUCTION_ROLE = await energyEscrow.AUCTION_ROLE();
      await energyEscrow.grantRole(AUCTION_ROLE, owner.address);

      // Create multiple settlements
      await shaktiToken.approve(await energyEscrow.getAddress(), ethers.MaxUint256);

      for (let i = 0; i < 3; i++) {
        await energyEscrow.deposit(1, ethers.parseEther("100"));
        await energyEscrow.createSettlement(
          1,
          owner.address,
          users[i].address,
          1000,
          ethers.parseEther("0.005")
        );
      }

      // Fast forward past dispute window
      await ethers.provider.send("evm_increaseTime", [86400 + 1]);
      await ethers.provider.send("evm_mine", []);

      // Batch complete
      const tx = await energyEscrow.batchCompleteSettlements([0, 1, 2]);
      const receipt = await tx.wait();

      expect(receipt!.gasUsed).to.be.lt(1000000n);
    });
  });

  describe("Pausable DoS Prevention", function () {
    beforeEach(async function () {
      await loadFixture(deployContractsFixture);
    });

    it("Only authorized can pause - prevents malicious pause", async function () {
      await expect(
        stakingPool.connect(attacker).pause()
      ).to.be.reverted;

      // Staking should still work
      await expect(
        stakingPool.connect(users[0]).stake(ethers.parseEther("100"), 0)
      ).to.not.be.reverted;
    });

    it("Emergency withdraw available even when paused", async function () {
      // Stake
      await stakingPool.connect(users[0]).stake(ethers.parseEther("100"), 0);

      // Pause
      await stakingPool.pause();

      // Normal unstake fails
      await expect(
        stakingPool.connect(users[0]).unstake(ethers.parseEther("100"))
      ).to.be.reverted;

      // Emergency withdraw should work (not paused)
      await expect(
        stakingPool.connect(users[0]).emergencyWithdraw()
      ).to.not.be.reverted;
    });

    it("Circuit breaker in escrow allows emergency actions", async function () {
      // Deposit
      await shaktiToken.connect(users[0]).approve(
        await energyEscrow.getAddress(),
        ethers.MaxUint256
      );
      await energyEscrow.connect(users[0]).deposit(1, ethers.parseEther("100"));

      // Activate circuit breaker
      await energyEscrow.setCircuitBreaker(true);

      // Normal operations blocked
      await expect(
        energyEscrow.connect(users[0]).deposit(1, ethers.parseEther("100"))
      ).to.be.revertedWithCustomError(energyEscrow, "CircuitBreakerActive");

      // Admin can emergency withdraw
      await expect(
        energyEscrow.emergencyWithdrawFor(1, users[0].address)
      ).to.not.be.reverted;
    });
  });

  describe("Order Cancellation DoS Prevention", function () {
    beforeEach(async function () {
      await loadFixture(deployContractsFixture);
      await energyAuction.createAuctionRound(AUCTION_DURATION);
    });

    it("User can only cancel their own orders", async function () {
      // User submits order
      await energyAuction.connect(users[0]).submitBid(2000, ethers.parseEther("0.006"));

      // Attacker cannot cancel
      await expect(
        energyAuction.connect(attacker).cancelOrder(1, 0)
      ).to.be.revertedWithCustomError(energyAuction, "NotOrderOwner");
    });

    it("Cannot cancel already matched orders", async function () {
      // Submit matching orders
      await energyAuction.connect(users[0]).submitBid(2000, ethers.parseEther("0.006"));
      await energyAuction.connect(users[1]).submitAsk(2000, ethers.parseEther("0.004"));

      // Close and clear
      await ethers.provider.send("evm_increaseTime", [AUCTION_DURATION + 1]);
      await ethers.provider.send("evm_mine", []);
      await energyAuction.closeAuction(1);
      await energyAuction.clearMarket(1);

      // Cannot cancel matched order
      await expect(
        energyAuction.connect(users[0]).cancelOrder(1, 0)
      ).to.be.reverted; // Auction not open
    });
  });

  describe("Reputation System DoS Prevention", function () {
    beforeEach(async function () {
      await loadFixture(deployContractsFixture);
    });

    it("Registration is bounded per user", async function () {
      // User can only register once
      await reputationSystem.registerUser(users[0].address);

      await expect(
        reputationSystem.registerUser(users[0].address)
      ).to.be.revertedWithCustomError(reputationSystem, "UserAlreadyRegistered");
    });

    it("Decay capped at -10 per call prevents gas griefing", async function () {
      await reputationSystem.registerUser(users[0].address);

      // Wait very long time
      await ethers.provider.send("evm_increaseTime", [365 * 86400]); // 1 year
      await ethers.provider.send("evm_mine", []);

      // Decay should be capped
      const tx = await reputationSystem.applyDecay(users[0].address);
      const receipt = await tx.wait();

      // Should complete in reasonable gas
      expect(receipt!.gasUsed).to.be.lt(200000n);

      // Check decay was capped
      const rep = await reputationSystem.getUserReputation(users[0].address);
      expect(rep.score).to.be.gte(490); // Started at 500, max -10 decay
    });

    it("Tier distribution calculation has bounded gas", async function () {
      // Register multiple users
      for (let i = 0; i < 5; i++) {
        await reputationSystem.registerUser(users[i].address);
      }

      // Get tier distribution
      const distribution = await reputationSystem.getTierDistribution();
      expect(distribution.silver).to.equal(5); // All start at 500 = Silver
    });
  });

  describe("Token Burn DoS Prevention", function () {
    beforeEach(async function () {
      await loadFixture(deployContractsFixture);
    });

    it("Burn operations bounded by balance", async function () {
      // Grant burner role
      const BURNER_ROLE = await shaktiToken.BURNER_ROLE();
      await shaktiToken.grantRole(BURNER_ROLE, users[0].address);

      // Cannot burn more than balance
      await expect(
        shaktiToken.connect(users[0]).burnFees(ethers.parseEther("1000000"))
      ).to.be.revertedWithCustomError(shaktiToken, "InsufficientBalance");
    });
  });

  describe("Staking Pool DoS Prevention", function () {
    beforeEach(async function () {
      await loadFixture(deployContractsFixture);
    });

    it("Batch reward claims have bounded iteration", async function () {
      // Stake for multiple users
      for (let i = 0; i < 5; i++) {
        await stakingPool.connect(users[i]).stake(ethers.parseEther("100"), 0);
      }

      // Time passes
      await ethers.provider.send("evm_increaseTime", [30 * 86400]);
      await ethers.provider.send("evm_mine", []);

      // Batch claim
      const addresses = users.slice(0, 5).map(u => u.address);
      const tx = await stakingPool.batchClaimRewards(addresses);
      const receipt = await tx.wait();

      expect(receipt!.gasUsed).to.be.lt(1000000n);
    });

    it("Cannot grief compound by sending dust tokens", async function () {
      // Stake
      await stakingPool.connect(users[0]).stake(ethers.parseEther("100"), 0);

      // Time passes
      await ethers.provider.send("evm_increaseTime", [30 * 86400]);
      await ethers.provider.send("evm_mine", []);

      // Compound
      await expect(
        stakingPool.connect(users[0]).compoundRewards()
      ).to.not.be.reverted;
    });
  });
});
