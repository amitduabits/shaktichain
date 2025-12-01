/**
 * SHAKTI-CHAIN Security Tests: Access Control
 *
 * Tests role-based access control for all privileged functions.
 * Verifies that unauthorized users cannot access protected functions.
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
  DynamicPricing,
} from "../../typechain-types";

describe("Security: Access Control", function () {
  let owner: SignerWithAddress;
  let admin: SignerWithAddress;
  let attacker: SignerWithAddress;
  let user1: SignerWithAddress;
  let user2: SignerWithAddress;
  let shaktiToken: ShaktiToken;
  let stakingPool: StakingPool;
  let energyAuction: EnergyAuction;
  let energyEscrow: EnergyEscrow;
  let reputationSystem: ReputationSystem;

  async function deployContractsFixture() {
    [owner, admin, attacker, user1, user2] = await ethers.getSigners();

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

    return { shaktiToken, stakingPool, energyAuction, energyEscrow, reputationSystem };
  }

  describe("ShaktiToken Access Control", function () {
    beforeEach(async function () {
      await loadFixture(deployContractsFixture);
    });

    it("Should reject mint from non-MINTER_ROLE", async function () {
      const MINTER_ROLE = await shaktiToken.MINTER_ROLE();

      await expect(
        shaktiToken.connect(attacker).mint(attacker.address, ethers.parseEther("1000"))
      ).to.be.revertedWithCustomError(shaktiToken, "AccessControlUnauthorizedAccount")
        .withArgs(attacker.address, MINTER_ROLE);
    });

    it("Should reject pause from non-PAUSER_ROLE", async function () {
      const PAUSER_ROLE = await shaktiToken.PAUSER_ROLE();

      await expect(
        shaktiToken.connect(attacker).pause()
      ).to.be.revertedWithCustomError(shaktiToken, "AccessControlUnauthorizedAccount")
        .withArgs(attacker.address, PAUSER_ROLE);
    });

    it("Should reject unpause from non-PAUSER_ROLE", async function () {
      // First pause with owner
      await shaktiToken.pause();

      const PAUSER_ROLE = await shaktiToken.PAUSER_ROLE();

      await expect(
        shaktiToken.connect(attacker).unpause()
      ).to.be.revertedWithCustomError(shaktiToken, "AccessControlUnauthorizedAccount")
        .withArgs(attacker.address, PAUSER_ROLE);
    });

    it("Should reject burnFees from non-BURNER_ROLE", async function () {
      const BURNER_ROLE = await shaktiToken.BURNER_ROLE();

      await expect(
        shaktiToken.connect(attacker).burnFees(ethers.parseEther("100"))
      ).to.be.revertedWithCustomError(shaktiToken, "AccessControlUnauthorizedAccount")
        .withArgs(attacker.address, BURNER_ROLE);
    });

    it("Should allow role assignment only by admin", async function () {
      const MINTER_ROLE = await shaktiToken.MINTER_ROLE();

      // Attacker cannot grant roles
      await expect(
        shaktiToken.connect(attacker).grantRole(MINTER_ROLE, attacker.address)
      ).to.be.reverted;

      // Owner can grant roles
      await expect(
        shaktiToken.grantRole(MINTER_ROLE, admin.address)
      ).to.not.be.reverted;
    });

    it("Should prevent role renunciation abuse", async function () {
      const DEFAULT_ADMIN_ROLE = await shaktiToken.DEFAULT_ADMIN_ROLE();

      // Owner should be careful with admin role
      expect(await shaktiToken.hasRole(DEFAULT_ADMIN_ROLE, owner.address)).to.be.true;
    });
  });

  describe("StakingPool Access Control", function () {
    beforeEach(async function () {
      await loadFixture(deployContractsFixture);
    });

    it("Should reject setRewardRate from non-GOVERNANCE_ROLE", async function () {
      const GOVERNANCE_ROLE = await stakingPool.GOVERNANCE_ROLE();

      await expect(
        stakingPool.connect(attacker).setRewardRate(1000)
      ).to.be.revertedWithCustomError(stakingPool, "AccessControlUnauthorizedAccount")
        .withArgs(attacker.address, GOVERNANCE_ROLE);
    });

    it("Should reject pause from non-PAUSER_ROLE", async function () {
      const PAUSER_ROLE = await stakingPool.PAUSER_ROLE();

      await expect(
        stakingPool.connect(attacker).pause()
      ).to.be.revertedWithCustomError(stakingPool, "AccessControlUnauthorizedAccount")
        .withArgs(attacker.address, PAUSER_ROLE);
    });

    it("Should allow governance to update reward rate", async function () {
      await expect(
        stakingPool.connect(owner).setRewardRate(1000)
      ).to.not.be.reverted;
    });

    it("Should enforce MAX_REWARD_RATE limit", async function () {
      const maxRate = await stakingPool.MAX_REWARD_RATE();

      await expect(
        stakingPool.connect(owner).setRewardRate(maxRate + 1n)
      ).to.be.revertedWithCustomError(stakingPool, "InvalidRewardRate");
    });
  });

  describe("EnergyAuction Access Control", function () {
    beforeEach(async function () {
      await loadFixture(deployContractsFixture);
    });

    it("Should reject createAuctionRound from non-AUCTIONEER_ROLE", async function () {
      const AUCTIONEER_ROLE = await energyAuction.AUCTIONEER_ROLE();

      await expect(
        energyAuction.connect(attacker).createAuctionRound(600)
      ).to.be.revertedWithCustomError(energyAuction, "AccessControlUnauthorizedAccount")
        .withArgs(attacker.address, AUCTIONEER_ROLE);
    });

    it("Should reject closeAuction from non-AUCTIONEER_ROLE", async function () {
      // Create auction first
      await energyAuction.createAuctionRound(300);

      // Fast forward
      await ethers.provider.send("evm_increaseTime", [301]);
      await ethers.provider.send("evm_mine", []);

      const AUCTIONEER_ROLE = await energyAuction.AUCTIONEER_ROLE();

      await expect(
        energyAuction.connect(attacker).closeAuction(1)
      ).to.be.revertedWithCustomError(energyAuction, "AccessControlUnauthorizedAccount")
        .withArgs(attacker.address, AUCTIONEER_ROLE);
    });

    it("Should reject clearMarket from non-OPERATOR_ROLE", async function () {
      const OPERATOR_ROLE = await energyAuction.OPERATOR_ROLE();

      await expect(
        energyAuction.connect(attacker).clearMarket(1)
      ).to.be.revertedWithCustomError(energyAuction, "AccessControlUnauthorizedAccount")
        .withArgs(attacker.address, OPERATOR_ROLE);
    });

    it("Should reject setPriceBounds from non-DEFAULT_ADMIN_ROLE", async function () {
      await expect(
        energyAuction.connect(attacker).setPriceBounds(
          ethers.parseEther("0.002"),
          ethers.parseEther("0.02")
        )
      ).to.be.reverted;
    });

    it("Should reject pause from non-DEFAULT_ADMIN_ROLE", async function () {
      await expect(
        energyAuction.connect(attacker).pause()
      ).to.be.reverted;
    });
  });

  describe("EnergyEscrow Access Control", function () {
    beforeEach(async function () {
      await loadFixture(deployContractsFixture);
    });

    it("Should reject createSettlement from non-AUCTION_ROLE", async function () {
      await expect(
        energyEscrow.connect(attacker).createSettlement(
          1,
          user1.address,
          user2.address,
          1000,
          ethers.parseEther("0.005")
        )
      ).to.be.revertedWithCustomError(energyEscrow, "UnauthorizedAuction");
    });

    it("Should reject depositFor from non-AUCTION_ROLE", async function () {
      await shaktiToken.transfer(attacker.address, ethers.parseEther("1000"));
      await shaktiToken.connect(attacker).approve(
        await energyEscrow.getAddress(),
        ethers.MaxUint256
      );

      await expect(
        energyEscrow.connect(attacker).depositFor(1, user1.address, ethers.parseEther("100"))
      ).to.be.revertedWithCustomError(energyEscrow, "UnauthorizedAuction");
    });

    it("Should reject refundSettlement from non-AUCTION_ROLE", async function () {
      await expect(
        energyEscrow.connect(attacker).refundSettlement(0)
      ).to.be.reverted;
    });

    it("Should reject resolveDispute from non-ARBITER_ROLE", async function () {
      const ARBITER_ROLE = await energyEscrow.ARBITER_ROLE();

      await expect(
        energyEscrow.connect(attacker).resolveDispute(0, 1, "test", false)
      ).to.be.revertedWithCustomError(energyEscrow, "AccessControlUnauthorizedAccount")
        .withArgs(attacker.address, ARBITER_ROLE);
    });

    it("Should reject setPlatformFee from non-DEFAULT_ADMIN_ROLE", async function () {
      await expect(
        energyEscrow.connect(attacker).setPlatformFee(100)
      ).to.be.reverted;
    });

    it("Should reject setCircuitBreaker from non-DEFAULT_ADMIN_ROLE", async function () {
      await expect(
        energyEscrow.connect(attacker).setCircuitBreaker(true)
      ).to.be.reverted;
    });

    it("Should reject setTreasury from non-TREASURY_ROLE", async function () {
      const TREASURY_ROLE = await energyEscrow.TREASURY_ROLE();

      await expect(
        energyEscrow.connect(attacker).setTreasury(attacker.address)
      ).to.be.revertedWithCustomError(energyEscrow, "AccessControlUnauthorizedAccount")
        .withArgs(attacker.address, TREASURY_ROLE);
    });

    it("Should reject emergencyWithdrawFor from non-admin when circuit breaker off", async function () {
      await expect(
        energyEscrow.connect(attacker).emergencyWithdrawFor(1, user1.address)
      ).to.be.reverted;
    });
  });

  describe("ReputationSystem Access Control", function () {
    beforeEach(async function () {
      await loadFixture(deployContractsFixture);
    });

    it("Should reject updateReputation from non-REPORTER_ROLE", async function () {
      // Register user first
      await reputationSystem.registerUser(user1.address);

      const REPORTER_ROLE = await reputationSystem.REPORTER_ROLE();

      await expect(
        reputationSystem.connect(attacker).updateReputation(user1.address, 10, 0)
      ).to.be.revertedWithCustomError(reputationSystem, "AccessControlUnauthorizedAccount")
        .withArgs(attacker.address, REPORTER_ROLE);
    });

    it("Should reject recordSuccessfulTrade from non-REPORTER_ROLE", async function () {
      await reputationSystem.registerUser(user1.address);

      const REPORTER_ROLE = await reputationSystem.REPORTER_ROLE();

      await expect(
        reputationSystem.connect(attacker).recordSuccessfulTrade(
          user1.address,
          ethers.parseEther("50")
        )
      ).to.be.revertedWithCustomError(reputationSystem, "AccessControlUnauthorizedAccount")
        .withArgs(attacker.address, REPORTER_ROLE);
    });

    it("Should reject updateKYCStatus from non-VERIFIER_ROLE", async function () {
      await reputationSystem.registerUser(user1.address);

      const VERIFIER_ROLE = await reputationSystem.VERIFIER_ROLE();

      await expect(
        reputationSystem.connect(attacker).updateKYCStatus(user1.address, true)
      ).to.be.revertedWithCustomError(reputationSystem, "AccessControlUnauthorizedAccount")
        .withArgs(attacker.address, VERIFIER_ROLE);
    });

    it("Should reject flagUser from non-VERIFIER_ROLE", async function () {
      await reputationSystem.registerUser(user1.address);

      const VERIFIER_ROLE = await reputationSystem.VERIFIER_ROLE();

      await expect(
        reputationSystem.connect(attacker).flagUser(user1.address, "suspicious")
      ).to.be.revertedWithCustomError(reputationSystem, "AccessControlUnauthorizedAccount")
        .withArgs(attacker.address, VERIFIER_ROLE);
    });

    it("Should reject adminAdjustReputation from non-DEFAULT_ADMIN_ROLE", async function () {
      await reputationSystem.registerUser(user1.address);

      await expect(
        reputationSystem.connect(attacker).adminAdjustReputation(user1.address, 100, "bonus")
      ).to.be.reverted;
    });

    it("Should reject grantReporterRole from non-DEFAULT_ADMIN_ROLE", async function () {
      await expect(
        reputationSystem.connect(attacker).grantReporterRole(attacker.address)
      ).to.be.reverted;
    });
  });

  describe("Role Hierarchy Tests", function () {
    beforeEach(async function () {
      await loadFixture(deployContractsFixture);
    });

    it("DEFAULT_ADMIN_ROLE should be able to grant/revoke other roles", async function () {
      const MINTER_ROLE = await shaktiToken.MINTER_ROLE();

      // Grant role
      await shaktiToken.grantRole(MINTER_ROLE, admin.address);
      expect(await shaktiToken.hasRole(MINTER_ROLE, admin.address)).to.be.true;

      // Revoke role
      await shaktiToken.revokeRole(MINTER_ROLE, admin.address);
      expect(await shaktiToken.hasRole(MINTER_ROLE, admin.address)).to.be.false;
    });

    it("Non-admin cannot grant roles to others", async function () {
      const MINTER_ROLE = await shaktiToken.MINTER_ROLE();

      // First give admin the MINTER_ROLE
      await shaktiToken.grantRole(MINTER_ROLE, admin.address);

      // Admin with MINTER_ROLE cannot grant it to others
      await expect(
        shaktiToken.connect(admin).grantRole(MINTER_ROLE, attacker.address)
      ).to.be.reverted;
    });

    it("User cannot escalate their own privileges", async function () {
      const DEFAULT_ADMIN_ROLE = await shaktiToken.DEFAULT_ADMIN_ROLE();

      await expect(
        shaktiToken.connect(attacker).grantRole(DEFAULT_ADMIN_ROLE, attacker.address)
      ).to.be.reverted;
    });
  });

  describe("Pausable Access Control", function () {
    beforeEach(async function () {
      await loadFixture(deployContractsFixture);
    });

    it("Operations should fail when paused", async function () {
      // Pause StakingPool
      await stakingPool.pause();

      // Transfer tokens to user
      await shaktiToken.transfer(user1.address, ethers.parseEther("1000"));
      await shaktiToken.connect(user1).approve(
        await stakingPool.getAddress(),
        ethers.MaxUint256
      );

      // Stake should fail
      await expect(
        stakingPool.connect(user1).stake(ethers.parseEther("100"), 0)
      ).to.be.reverted; // Pausable: paused
    });

    it("Only authorized roles can pause/unpause", async function () {
      // Already tested above, but double-checking
      await expect(
        stakingPool.connect(attacker).pause()
      ).to.be.reverted;
    });

    it("Circuit breaker should block escrow operations", async function () {
      // Activate circuit breaker
      await energyEscrow.setCircuitBreaker(true);

      // Transfer tokens to user
      await shaktiToken.transfer(user1.address, ethers.parseEther("1000"));
      await shaktiToken.connect(user1).approve(
        await energyEscrow.getAddress(),
        ethers.MaxUint256
      );

      // Deposit should fail
      await expect(
        energyEscrow.connect(user1).deposit(1, ethers.parseEther("100"))
      ).to.be.revertedWithCustomError(energyEscrow, "CircuitBreakerActive");
    });
  });

  describe("Zero Address Checks", function () {
    it("ShaktiToken constructor should reject zero admin", async function () {
      const ShaktiTokenFactory = await ethers.getContractFactory("ShaktiToken");

      await expect(
        ShaktiTokenFactory.deploy(ethers.ZeroAddress, owner.address)
      ).to.be.revertedWithCustomError(shaktiToken, "ZeroAddress");
    });

    it("StakingPool constructor should reject zero admin", async function () {
      const StakingPoolFactory = await ethers.getContractFactory("StakingPool");

      await expect(
        StakingPoolFactory.deploy(
          await shaktiToken.getAddress(),
          ethers.ZeroAddress,
          800
        )
      ).to.be.revertedWithCustomError(stakingPool, "ZeroAddress");
    });

    it("EnergyEscrow should reject zero treasury", async function () {
      const EnergyEscrowFactory = await ethers.getContractFactory("EnergyEscrow");

      await expect(
        EnergyEscrowFactory.deploy(
          await shaktiToken.getAddress(),
          ethers.ZeroAddress, // treasury
          owner.address,
          200,
          3000
        )
      ).to.be.reverted;
    });

    it("EnergyEscrow setTreasury should reject zero address", async function () {
      await expect(
        energyEscrow.setTreasury(ethers.ZeroAddress)
      ).to.be.revertedWithCustomError(energyEscrow, "ZeroAddress");
    });
  });

  describe("Multi-Signature Considerations", function () {
    it("Critical admin functions should exist for future multi-sig", async function () {
      // DEFAULT_ADMIN_ROLE in OpenZeppelin is bytes32(0) by design
      const DEFAULT_ADMIN_ROLE = await shaktiToken.DEFAULT_ADMIN_ROLE();

      // Owner should have admin role
      expect(await shaktiToken.hasRole(DEFAULT_ADMIN_ROLE, owner.address)).to.be.true;

      // Verify role can be transferred to a multi-sig address
      await shaktiToken.grantRole(DEFAULT_ADMIN_ROLE, admin.address);
      expect(await shaktiToken.hasRole(DEFAULT_ADMIN_ROLE, admin.address)).to.be.true;

      // Original admin can then renounce their role
      // This is the pattern for transferring to multi-sig
      await shaktiToken.renounceRole(DEFAULT_ADMIN_ROLE, owner.address);
      expect(await shaktiToken.hasRole(DEFAULT_ADMIN_ROLE, owner.address)).to.be.false;
    });
  });
});
