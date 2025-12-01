import { expect } from "chai";
import { ethers, upgrades } from "hardhat";
import { HardhatEthersSigner } from "@nomicfoundation/hardhat-ethers/signers";
import {
  ShaktiTokenV2,
  EnergyAuctionUpgradeable,
  EnergyEscrowUpgradeable,
  ReputationSystemUpgradeable,
} from "../../typechain-types";

describe("Upgradeable Contracts", function () {
  let admin: HardhatEthersSigner;
  let user1: HardhatEthersSigner;
  let user2: HardhatEthersSigner;
  let governance: HardhatEthersSigner;
  let treasury: HardhatEthersSigner;

  beforeEach(async function () {
    [admin, user1, user2, governance, treasury] = await ethers.getSigners();
  });

  describe("ShaktiTokenV2", function () {
    let token: ShaktiTokenV2;
    let tokenAddress: string;

    beforeEach(async function () {
      const ShaktiTokenV2 = await ethers.getContractFactory("ShaktiTokenV2");
      token = await upgrades.deployProxy(
        ShaktiTokenV2,
        [admin.address, admin.address],
        { initializer: "initialize", kind: "uups" }
      ) as unknown as ShaktiTokenV2;
      await token.waitForDeployment();
      tokenAddress = await token.getAddress();
    });

    describe("Initialization", function () {
      it("should initialize with correct name and symbol", async function () {
        expect(await token.name()).to.equal("SHAKTI Token");
        expect(await token.symbol()).to.equal("SHAKTI");
      });

      it("should mint initial supply to holder", async function () {
        const initialSupply = ethers.parseEther("1000000000");
        expect(await token.balanceOf(admin.address)).to.equal(initialSupply);
      });

      it("should grant all roles to admin", async function () {
        expect(await token.hasRole(await token.DEFAULT_ADMIN_ROLE(), admin.address)).to.be.true;
        expect(await token.hasRole(await token.MINTER_ROLE(), admin.address)).to.be.true;
        expect(await token.hasRole(await token.BURNER_ROLE(), admin.address)).to.be.true;
        expect(await token.hasRole(await token.PAUSER_ROLE(), admin.address)).to.be.true;
        expect(await token.hasRole(await token.UPGRADER_ROLE(), admin.address)).to.be.true;
      });

      it("should return correct version", async function () {
        expect(await token.version()).to.equal("2.0.0");
      });

      it("should prevent double initialization", async function () {
        await expect(
          token.initialize(user1.address, user1.address)
        ).to.be.revertedWithCustomError(token, "InvalidInitialization");
      });
    });

    describe("V2 Initialization", function () {
      it("should allow V2 initialization with governance timelock", async function () {
        await token.initializeV2(governance.address);
        expect(await token.hasRole(await token.UPGRADER_ROLE(), governance.address)).to.be.true;
      });

      it("should reject zero address for governance", async function () {
        await expect(
          token.initializeV2(ethers.ZeroAddress)
        ).to.be.revertedWithCustomError(token, "ZeroAddress");
      });
    });

    describe("ERC20 Functionality", function () {
      it("should transfer tokens", async function () {
        const amount = ethers.parseEther("1000");
        await token.transfer(user1.address, amount);
        expect(await token.balanceOf(user1.address)).to.equal(amount);
      });

      it("should approve and transferFrom", async function () {
        const amount = ethers.parseEther("1000");
        await token.approve(user1.address, amount);
        await token.connect(user1).transferFrom(admin.address, user2.address, amount);
        expect(await token.balanceOf(user2.address)).to.equal(amount);
      });
    });

    describe("Voting (ERC20Votes)", function () {
      it("should delegate votes", async function () {
        await token.delegate(admin.address);
        const votes = await token.getVotes(admin.address);
        expect(votes).to.equal(await token.balanceOf(admin.address));
      });

      it("should track voting power after transfer", async function () {
        await token.delegate(admin.address);
        const amount = ethers.parseEther("1000");
        await token.transfer(user1.address, amount);

        // Admin's votes decrease
        const adminVotes = await token.getVotes(admin.address);
        expect(adminVotes).to.equal((await token.balanceOf(admin.address)));
      });
    });

    describe("Pause Functionality", function () {
      it("should pause and unpause", async function () {
        await token.pause();
        expect(await token.paused()).to.be.true;

        await token.unpause();
        expect(await token.paused()).to.be.false;
      });

      it("should prevent transfers when paused", async function () {
        await token.pause();
        await expect(
          token.transfer(user1.address, ethers.parseEther("100"))
        ).to.be.revertedWithCustomError(token, "EnforcedPause");
      });
    });

    describe("Fee Burning", function () {
      it("should burn 30% of fees", async function () {
        const feeAmount = ethers.parseEther("1000");
        const expectedBurn = ethers.parseEther("300"); // 30%

        const balanceBefore = await token.balanceOf(admin.address);
        await token.burnFees(admin.address, feeAmount);
        const balanceAfter = await token.balanceOf(admin.address);

        expect(balanceBefore - balanceAfter).to.equal(expectedBurn);
        expect(await token.totalFeesBurned()).to.equal(expectedBurn);
      });
    });

    describe("Upgrade", function () {
      it("should only allow UPGRADER_ROLE to upgrade", async function () {
        const ShaktiTokenV2 = await ethers.getContractFactory("ShaktiTokenV2");

        // User without role cannot upgrade
        await expect(
          upgrades.upgradeProxy(tokenAddress, ShaktiTokenV2.connect(user1), { kind: "uups" })
        ).to.be.reverted;
      });

      it("should preserve state after upgrade", async function () {
        // Transfer some tokens
        await token.transfer(user1.address, ethers.parseEther("1000"));
        const user1BalanceBefore = await token.balanceOf(user1.address);
        const totalSupplyBefore = await token.totalSupply();

        // Upgrade
        const ShaktiTokenV2 = await ethers.getContractFactory("ShaktiTokenV2");
        const upgraded = await upgrades.upgradeProxy(tokenAddress, ShaktiTokenV2, { kind: "uups" });
        await upgraded.waitForDeployment();

        // Verify state preserved
        expect(await token.balanceOf(user1.address)).to.equal(user1BalanceBefore);
        expect(await token.totalSupply()).to.equal(totalSupplyBefore);
      });
    });
  });

  describe("EnergyAuctionUpgradeable", function () {
    let token: ShaktiTokenV2;
    let auction: EnergyAuctionUpgradeable;
    let auctionAddress: string;
    const minPrice = ethers.parseEther("0.002");
    const maxPrice = ethers.parseEther("0.015");

    beforeEach(async function () {
      // Deploy token
      const ShaktiTokenV2 = await ethers.getContractFactory("ShaktiTokenV2");
      token = await upgrades.deployProxy(
        ShaktiTokenV2,
        [admin.address, admin.address],
        { initializer: "initialize", kind: "uups" }
      ) as unknown as ShaktiTokenV2;
      await token.waitForDeployment();

      // Deploy auction
      const EnergyAuctionUpgradeable = await ethers.getContractFactory("EnergyAuctionUpgradeable");
      auction = await upgrades.deployProxy(
        EnergyAuctionUpgradeable,
        [await token.getAddress(), ethers.ZeroAddress, admin.address, minPrice, maxPrice],
        { initializer: "initialize", kind: "uups" }
      ) as unknown as EnergyAuctionUpgradeable;
      await auction.waitForDeployment();
      auctionAddress = await auction.getAddress();
    });

    describe("Initialization", function () {
      it("should initialize with correct parameters", async function () {
        expect(await auction.shaktiToken()).to.equal(await token.getAddress());
        expect(await auction.minPrice()).to.equal(minPrice);
        expect(await auction.maxPrice()).to.equal(maxPrice);
      });

      it("should return correct version", async function () {
        expect(await auction.version()).to.equal("1.0.0");
      });

      it("should grant all roles to admin", async function () {
        expect(await auction.hasRole(await auction.DEFAULT_ADMIN_ROLE(), admin.address)).to.be.true;
        expect(await auction.hasRole(await auction.AUCTIONEER_ROLE(), admin.address)).to.be.true;
        expect(await auction.hasRole(await auction.OPERATOR_ROLE(), admin.address)).to.be.true;
        expect(await auction.hasRole(await auction.UPGRADER_ROLE(), admin.address)).to.be.true;
      });
    });

    describe("Auction Rounds", function () {
      it("should create auction round", async function () {
        await auction.createAuctionRound(600); // 10 minutes
        const round = await auction.auctionRounds(1);
        expect(round.roundId).to.equal(1);
        expect(round.state).to.equal(0); // OPEN
      });

      it("should allow bid submission", async function () {
        await auction.createAuctionRound(600);

        // Approve and submit bid
        const bidAmount = ethers.parseEther("1000");
        await token.approve(auctionAddress, bidAmount);

        // submitBid takes (quantity, maxPricePerWh)
        // MIN_QUANTITY = 1000, price must be within bounds
        await auction.submitBid(
          1000n, // quantity (MIN_QUANTITY is 1000)
          ethers.parseEther("0.005") // price within bounds
        );

        const bidCount = (await auction.auctionRounds(1)).totalBids;
        expect(bidCount).to.equal(1);
      });
    });

    describe("Batch Operations", function () {
      it("should submit multiple bids via struct array", async function () {
        await auction.createAuctionRound(600);

        const totalAmount = ethers.parseEther("100000");
        await token.approve(auctionAddress, totalAmount);

        // BidOrder struct: { quantity: uint128, maxPricePerWh: uint128 }
        const bids = [
          { quantity: 1000n, maxPricePerWh: ethers.parseEther("0.003") },
          { quantity: 2000n, maxPricePerWh: ethers.parseEther("0.004") },
          { quantity: 1500n, maxPricePerWh: ethers.parseEther("0.005") },
        ];

        await auction.submitBids(bids);

        const round = await auction.auctionRounds(1);
        expect(round.totalBids).to.equal(3);
      });
    });

    describe("Upgrade", function () {
      it("should preserve state after upgrade", async function () {
        // Create round
        await auction.createAuctionRound(600);
        const roundIdBefore = await auction.currentRoundId();

        // Upgrade
        const EnergyAuctionUpgradeable = await ethers.getContractFactory("EnergyAuctionUpgradeable");
        await upgrades.upgradeProxy(auctionAddress, EnergyAuctionUpgradeable, { kind: "uups" });

        // Verify state
        expect(await auction.currentRoundId()).to.equal(roundIdBefore);
        expect(await auction.minPrice()).to.equal(minPrice);
        expect(await auction.maxPrice()).to.equal(maxPrice);
      });
    });
  });

  describe("EnergyEscrowUpgradeable", function () {
    let token: ShaktiTokenV2;
    let escrow: EnergyEscrowUpgradeable;
    let escrowAddress: string;
    const platformFee = 200n; // 2%
    const feeBurn = 3000n; // 30% of fees burned

    beforeEach(async function () {
      // Deploy token
      const ShaktiTokenV2 = await ethers.getContractFactory("ShaktiTokenV2");
      token = await upgrades.deployProxy(
        ShaktiTokenV2,
        [admin.address, admin.address],
        { initializer: "initialize", kind: "uups" }
      ) as unknown as ShaktiTokenV2;
      await token.waitForDeployment();

      // Deploy escrow with 5 parameters: token, treasury, admin, platformFee, feeBurn
      const EnergyEscrowUpgradeable = await ethers.getContractFactory("EnergyEscrowUpgradeable");
      escrow = await upgrades.deployProxy(
        EnergyEscrowUpgradeable,
        [await token.getAddress(), treasury.address, admin.address, platformFee, feeBurn],
        { initializer: "initialize", kind: "uups" }
      ) as unknown as EnergyEscrowUpgradeable;
      await escrow.waitForDeployment();
      escrowAddress = await escrow.getAddress();
    });

    describe("Initialization", function () {
      it("should initialize with correct parameters", async function () {
        expect(await escrow.shaktiToken()).to.equal(await token.getAddress());
        expect(await escrow.treasury()).to.equal(treasury.address);
        expect(await escrow.platformFeePercentage()).to.equal(platformFee);
        expect(await escrow.feeBurnPercentage()).to.equal(feeBurn);
      });

      it("should return correct version", async function () {
        expect(await escrow.version()).to.equal("1.0.0");
      });

      it("should not have circuit breaker active initially", async function () {
        expect(await escrow.circuitBreakerActive()).to.be.false;
      });
    });

    describe("Circuit Breaker", function () {
      it("should activate circuit breaker", async function () {
        await escrow.setCircuitBreaker(true);
        expect(await escrow.circuitBreakerActive()).to.be.true;
      });

      it("should deactivate circuit breaker", async function () {
        await escrow.setCircuitBreaker(true);
        await escrow.setCircuitBreaker(false);
        expect(await escrow.circuitBreakerActive()).to.be.false;
      });
    });

    describe("Fee Management", function () {
      it("should update platform fee", async function () {
        await escrow.setPlatformFee(300); // 3%
        expect(await escrow.platformFeePercentage()).to.equal(300);
      });

      it("should reject fee above max", async function () {
        // MAX_FEE_PERCENTAGE = 1000 (10%)
        await expect(
          escrow.setPlatformFee(1100) // 11% > max 10%
        ).to.be.revertedWithCustomError(escrow, "InvalidFeePercentage");
      });
    });

    describe("Upgrade", function () {
      it("should preserve state after upgrade", async function () {
        // Modify state
        await escrow.setPlatformFee(300);
        await escrow.setCircuitBreaker(true);

        // Upgrade
        const EnergyEscrowUpgradeable = await ethers.getContractFactory("EnergyEscrowUpgradeable");
        await upgrades.upgradeProxy(escrowAddress, EnergyEscrowUpgradeable, { kind: "uups" });

        // Verify state
        expect(await escrow.platformFeePercentage()).to.equal(300);
        expect(await escrow.circuitBreakerActive()).to.be.true;
      });
    });
  });

  describe("ReputationSystemUpgradeable", function () {
    let reputation: ReputationSystemUpgradeable;
    let reputationAddress: string;

    beforeEach(async function () {
      const ReputationSystemUpgradeable = await ethers.getContractFactory("ReputationSystemUpgradeable");
      reputation = await upgrades.deployProxy(
        ReputationSystemUpgradeable,
        [admin.address],
        { initializer: "initialize", kind: "uups" }
      ) as unknown as ReputationSystemUpgradeable;
      await reputation.waitForDeployment();
      reputationAddress = await reputation.getAddress();
    });

    describe("Initialization", function () {
      it("should initialize with correct constants", async function () {
        expect(await reputation.STARTING_REPUTATION()).to.equal(500);
        expect(await reputation.MAX_REPUTATION()).to.equal(1000);
      });

      it("should return correct version", async function () {
        expect(await reputation.version()).to.equal("1.0.0");
      });

      it("should have correct tier thresholds", async function () {
        expect(await reputation.BRONZE_MAX()).to.equal(300);
        expect(await reputation.SILVER_MAX()).to.equal(500);
        expect(await reputation.GOLD_MAX()).to.equal(700);
        expect(await reputation.PLATINUM_MAX()).to.equal(850);
      });

      it("should grant all roles to admin", async function () {
        expect(await reputation.hasRole(await reputation.DEFAULT_ADMIN_ROLE(), admin.address)).to.be.true;
        expect(await reputation.hasRole(await reputation.REPORTER_ROLE(), admin.address)).to.be.true;
        expect(await reputation.hasRole(await reputation.TRADE_REPORTER_ROLE(), admin.address)).to.be.true;
        expect(await reputation.hasRole(await reputation.KYC_VERIFIER_ROLE(), admin.address)).to.be.true;
        expect(await reputation.hasRole(await reputation.UPGRADER_ROLE(), admin.address)).to.be.true;
      });
    });

    describe("User Registration", function () {
      it("should register a new user", async function () {
        await reputation.registerUser(user1.address);
        const rep = await reputation.userReputations(user1.address);
        expect(rep.score).to.equal(500); // STARTING_REPUTATION
        expect(rep.tier).to.equal(1); // SILVER
      });

      it("should reject registering same user twice", async function () {
        await reputation.registerUser(user1.address);
        await expect(
          reputation.registerUser(user1.address)
        ).to.be.revertedWithCustomError(reputation, "UserAlreadyRegistered");
      });
    });

    describe("Reputation Recording", function () {
      beforeEach(async function () {
        await reputation.registerUser(user1.address);
        // Update stake to meet minimum requirement (100 SHAKTI)
        await reputation.updateStake(user1.address, ethers.parseEther("100"));
      });

      it("should record successful trade", async function () {
        const repBefore = await reputation.userReputations(user1.address);
        await reputation.recordSuccessfulTrade(user1.address, ethers.parseEther("100"));
        const repAfter = await reputation.userReputations(user1.address);

        expect(repAfter.score).to.be.gt(repBefore.score);
        expect(repAfter.successfulTrades).to.equal(1);
      });

      it("should record failed delivery", async function () {
        const repBefore = await reputation.userReputations(user1.address);
        await reputation.recordFailedDelivery(user1.address);
        const repAfter = await reputation.userReputations(user1.address);

        expect(repAfter.score).to.be.lt(repBefore.score);
        expect(repAfter.failedDeliveries).to.equal(1);
      });

      it("should record dispute outcomes", async function () {
        await reputation.recordDisputeWon(user1.address);
        let rep = await reputation.userReputations(user1.address);
        expect(rep.disputesWon).to.equal(1);

        await reputation.recordDisputeLost(user1.address);
        rep = await reputation.userReputations(user1.address);
        expect(rep.disputesLost).to.equal(1);
      });
    });

    describe("KYC Integration", function () {
      beforeEach(async function () {
        await reputation.registerUser(user1.address);
      });

      it("should verify KYC status", async function () {
        await reputation.setKYCStatus(user1.address, true);
        const rep = await reputation.userReputations(user1.address);
        expect(rep.isKYCVerified).to.be.true;
      });

      it("should revoke KYC status", async function () {
        await reputation.setKYCStatus(user1.address, true);
        await reputation.setKYCStatus(user1.address, false);
        const rep = await reputation.userReputations(user1.address);
        expect(rep.isKYCVerified).to.be.false;
      });
    });

    describe("Tier Calculation", function () {
      beforeEach(async function () {
        await reputation.registerUser(user1.address);
        // Update stake to meet minimum requirement (100 SHAKTI)
        await reputation.updateStake(user1.address, ethers.parseEther("100"));
      });

      it("should start at Silver tier", async function () {
        const rep = await reputation.userReputations(user1.address);
        expect(rep.tier).to.equal(1); // SILVER (score 500 is exactly at SILVER_MAX)
      });

      it("should upgrade tier after many successful trades", async function () {
        // Record many successful large trades to increase score
        for (let i = 0; i < 50; i++) {
          await reputation.recordSuccessfulTrade(user1.address, ethers.parseEther("20000"));
        }

        const rep = await reputation.userReputations(user1.address);
        expect(rep.tier).to.be.gte(2); // At least GOLD
      });

      it("should downgrade tier after failed deliveries", async function () {
        // Record failed deliveries to decrease score
        for (let i = 0; i < 5; i++) {
          await reputation.recordFailedDelivery(user1.address);
        }

        const rep = await reputation.userReputations(user1.address);
        expect(rep.tier).to.equal(0); // BRONZE
      });
    });

    describe("Upgrade", function () {
      beforeEach(async function () {
        await reputation.registerUser(user1.address);
        // Update stake to meet minimum requirement (100 SHAKTI)
        await reputation.updateStake(user1.address, ethers.parseEther("100"));
      });

      it("should preserve reputation after upgrade", async function () {
        // Record some reputation changes
        await reputation.recordSuccessfulTrade(user1.address, ethers.parseEther("100"));
        const repBefore = await reputation.userReputations(user1.address);

        // Upgrade
        const ReputationSystemUpgradeable = await ethers.getContractFactory("ReputationSystemUpgradeable");
        await upgrades.upgradeProxy(reputationAddress, ReputationSystemUpgradeable, { kind: "uups" });

        // Verify state
        const repAfter = await reputation.userReputations(user1.address);
        expect(repAfter.score).to.equal(repBefore.score);
        expect(repAfter.successfulTrades).to.equal(repBefore.successfulTrades);
      });
    });
  });

  describe("Cross-Contract Integration", function () {
    let token: ShaktiTokenV2;
    let auction: EnergyAuctionUpgradeable;
    let escrow: EnergyEscrowUpgradeable;
    let reputation: ReputationSystemUpgradeable;

    beforeEach(async function () {
      // Deploy all contracts
      const ShaktiTokenV2 = await ethers.getContractFactory("ShaktiTokenV2");
      token = await upgrades.deployProxy(
        ShaktiTokenV2,
        [admin.address, admin.address],
        { initializer: "initialize", kind: "uups" }
      ) as unknown as ShaktiTokenV2;
      await token.waitForDeployment();

      const EnergyAuctionUpgradeable = await ethers.getContractFactory("EnergyAuctionUpgradeable");
      auction = await upgrades.deployProxy(
        EnergyAuctionUpgradeable,
        [await token.getAddress(), ethers.ZeroAddress, admin.address, ethers.parseEther("0.002"), ethers.parseEther("0.015")],
        { initializer: "initialize", kind: "uups" }
      ) as unknown as EnergyAuctionUpgradeable;
      await auction.waitForDeployment();

      const EnergyEscrowUpgradeable = await ethers.getContractFactory("EnergyEscrowUpgradeable");
      escrow = await upgrades.deployProxy(
        EnergyEscrowUpgradeable,
        [await token.getAddress(), treasury.address, admin.address, 200n, 3000n],
        { initializer: "initialize", kind: "uups" }
      ) as unknown as EnergyEscrowUpgradeable;
      await escrow.waitForDeployment();

      const ReputationSystemUpgradeable = await ethers.getContractFactory("ReputationSystemUpgradeable");
      reputation = await upgrades.deployProxy(
        ReputationSystemUpgradeable,
        [admin.address],
        { initializer: "initialize", kind: "uups" }
      ) as unknown as ReputationSystemUpgradeable;
      await reputation.waitForDeployment();
    });

    it("should maintain references after upgrade", async function () {
      const tokenAddress = await token.getAddress();

      // Upgrade escrow
      const EnergyEscrowUpgradeable = await ethers.getContractFactory("EnergyEscrowUpgradeable");
      await upgrades.upgradeProxy(await escrow.getAddress(), EnergyEscrowUpgradeable, { kind: "uups" });

      // Verify references still valid
      expect(await escrow.shaktiToken()).to.equal(tokenAddress);
    });

    it("should allow full workflow after upgrades", async function () {
      // Upgrade all contracts
      const ShaktiTokenV2 = await ethers.getContractFactory("ShaktiTokenV2");
      const EnergyAuctionUpgradeable = await ethers.getContractFactory("EnergyAuctionUpgradeable");
      const EnergyEscrowUpgradeable = await ethers.getContractFactory("EnergyEscrowUpgradeable");
      const ReputationSystemUpgradeable = await ethers.getContractFactory("ReputationSystemUpgradeable");

      await upgrades.upgradeProxy(await token.getAddress(), ShaktiTokenV2, { kind: "uups" });
      await upgrades.upgradeProxy(await auction.getAddress(), EnergyAuctionUpgradeable, { kind: "uups" });
      await upgrades.upgradeProxy(await escrow.getAddress(), EnergyEscrowUpgradeable, { kind: "uups" });
      await upgrades.upgradeProxy(await reputation.getAddress(), ReputationSystemUpgradeable, { kind: "uups" });

      // Verify all contracts still work
      expect(await token.version()).to.equal("2.0.0");
      expect(await auction.version()).to.equal("1.0.0");
      expect(await escrow.version()).to.equal("1.0.0");
      expect(await reputation.version()).to.equal("1.0.0");

      // Create auction round
      await auction.createAuctionRound(600);
      expect(await auction.currentRoundId()).to.equal(1);

      // Transfer tokens
      await token.transfer(user1.address, ethers.parseEther("1000"));
      expect(await token.balanceOf(user1.address)).to.equal(ethers.parseEther("1000"));

      // Register user in reputation system
      await reputation.registerUser(user1.address);
      const rep = await reputation.userReputations(user1.address);
      expect(rep.score).to.equal(500);
    });
  });
});
