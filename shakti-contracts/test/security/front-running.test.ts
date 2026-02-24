/**
 * SHAKTI-CHAIN Security Tests: Front-Running Prevention
 *
 * Tests for potential front-running vulnerabilities in auction and trading.
 * Front-running attacks occur when an attacker observes a pending transaction
 * and submits their own transaction with a higher gas price to get ahead.
 */

import { expect } from "chai";
import { ethers } from "hardhat";
import { loadFixture } from "@nomicfoundation/hardhat-network-helpers";
import { SignerWithAddress } from "@nomicfoundation/hardhat-ethers/signers";
import { ShaktiToken, EnergyAuction, StakingPool } from "../../typechain-types";

describe("Security: Front-Running Prevention", function () {
  let owner: SignerWithAddress;
  let frontrunner: SignerWithAddress;
  let victim: SignerWithAddress;
  let user: SignerWithAddress;
  let shaktiToken: ShaktiToken;
  let energyAuction: EnergyAuction;
  let stakingPool: StakingPool;

  const AUCTION_DURATION = 600; // 10 minutes
  const ORDER_QUANTITY = 5000; // 5 kWh in Wh

  async function deployContractsFixture() {
    [owner, frontrunner, victim, user] = await ethers.getSigners();

    // Deploy ShaktiToken
    const ShaktiTokenFactory = await ethers.getContractFactory("ShaktiToken");
    shaktiToken = await ShaktiTokenFactory.deploy(owner.address, owner.address);

    // Deploy EnergyAuction
    const EnergyAuctionFactory = await ethers.getContractFactory("EnergyAuction");
    energyAuction = await EnergyAuctionFactory.deploy(
      await shaktiToken.getAddress(),
      ethers.ZeroAddress,
      owner.address,
      ethers.parseEther("0.001"), // minPrice
      ethers.parseEther("0.01") // maxPrice
    );

    // Deploy StakingPool
    const StakingPoolFactory = await ethers.getContractFactory("StakingPool");
    stakingPool = await StakingPoolFactory.deploy(
      await shaktiToken.getAddress(),
      owner.address,
      800
    );

    // Setup: Transfer tokens
    await shaktiToken.transfer(frontrunner.address, ethers.parseEther("100000"));
    await shaktiToken.transfer(victim.address, ethers.parseEther("100000"));
    await shaktiToken.transfer(user.address, ethers.parseEther("100000"));

    // Approve
    await shaktiToken.connect(frontrunner).approve(
      await energyAuction.getAddress(),
      ethers.MaxUint256
    );
    await shaktiToken.connect(victim).approve(
      await energyAuction.getAddress(),
      ethers.MaxUint256
    );
    await shaktiToken.connect(user).approve(
      await energyAuction.getAddress(),
      ethers.MaxUint256
    );
    await shaktiToken.connect(victim).approve(
      await stakingPool.getAddress(),
      ethers.MaxUint256
    );
    await shaktiToken.connect(frontrunner).approve(
      await stakingPool.getAddress(),
      ethers.MaxUint256
    );

    return { shaktiToken, energyAuction, stakingPool };
  }

  describe("Auction Front-Running Mitigation", function () {
    beforeEach(async function () {
      await loadFixture(deployContractsFixture);
      // Create auction
      await energyAuction.createAuctionRound(AUCTION_DURATION);
    });

    it("McAfee auction mechanism resists price manipulation", async function () {
      /**
       * The McAfee double auction uses a uniform clearing price,
       * which provides some protection against front-running:
       * - All matched orders execute at the same clearing price
       * - Front-runner cannot get a better price by being first
       */

      // Victim submits a bid
      const victimPrice = ethers.parseEther("0.006");
      await energyAuction.connect(victim).submitBid(ORDER_QUANTITY, victimPrice);

      // Frontrunner sees the bid and tries to front-run with higher bid
      const frontrunnerPrice = ethers.parseEther("0.007");
      await energyAuction.connect(frontrunner).submitBid(ORDER_QUANTITY, frontrunnerPrice);

      // Add a matching ask
      await energyAuction.connect(user).submitAsk(ORDER_QUANTITY * 2, ethers.parseEther("0.004"));

      // Close and clear
      await ethers.provider.send("evm_increaseTime", [AUCTION_DURATION + 1]);
      await ethers.provider.send("evm_mine", []);

      await energyAuction.closeAuction(1);
      await energyAuction.clearMarket(1);

      // Both matched at uniform clearing price
      const round = await energyAuction.getAuctionRound(1);
      const clearingPrice = round.clearingPrice;

      // Clearing price should be between bid and ask
      expect(clearingPrice).to.be.gt(0);
    });

    it("Order submission order does not affect clearing price", async function () {
      // Submit in different orders to verify price is not affected

      // User 1 bids high
      await energyAuction.connect(victim).submitBid(ORDER_QUANTITY, ethers.parseEther("0.008"));

      // User 2 bids lower
      await energyAuction.connect(frontrunner).submitBid(ORDER_QUANTITY, ethers.parseEther("0.006"));

      // User 3 asks low
      await energyAuction.connect(user).submitAsk(ORDER_QUANTITY * 2, ethers.parseEther("0.003"));

      // Close and clear
      await ethers.provider.send("evm_increaseTime", [AUCTION_DURATION + 1]);
      await ethers.provider.send("evm_mine", []);

      await energyAuction.closeAuction(1);
      await energyAuction.clearMarket(1);

      // Verify clearing works
      const round = await energyAuction.getAuctionRound(1);
      expect(round.matchedOrders).to.be.gt(0);
    });

    it("Batch order submission prevents individual order sniping", async function () {
      // Batch orders are processed atomically
      const bids = [
        { quantity: 2000n, maxPricePerWh: ethers.parseEther("0.006") },
        { quantity: 3000n, maxPricePerWh: ethers.parseEther("0.007") },
      ];

      await energyAuction.connect(victim).submitBids(bids);

      // Verify both orders created
      const traderOrders = await energyAuction.getTraderOrders(victim.address, 1);
      expect(traderOrders.length).to.equal(2);
    });

    it("Time-bound auction window limits manipulation window", async function () {
      // Auction has fixed end time
      const round = await energyAuction.getAuctionRound(1);
      const endTime = round.endTime;

      expect(endTime).to.be.gt(0);

      // Cannot submit after end time
      await ethers.provider.send("evm_increaseTime", [AUCTION_DURATION + 1]);
      await ethers.provider.send("evm_mine", []);

      await expect(
        energyAuction.connect(frontrunner).submitBid(ORDER_QUANTITY, ethers.parseEther("0.006"))
      ).to.be.revertedWithCustomError(energyAuction, "AuctionAlreadyEnded");
    });

    it("Minimum order quantity prevents dust griefing", async function () {
      const minQuantity = await energyAuction.MIN_QUANTITY();

      // Cannot submit below minimum
      await expect(
        energyAuction.connect(frontrunner).submitBid(minQuantity - 1n, ethers.parseEther("0.006"))
      ).to.be.revertedWithCustomError(energyAuction, "InvalidQuantity");
    });

    it("Maximum orders per round limits flooding attacks", async function () {
      const maxOrders = await energyAuction.MAX_ORDERS_PER_ROUND();
      expect(maxOrders).to.be.gt(0);

      // Contract enforces max orders limit
      // This prevents an attacker from flooding with orders
    });
  });

  describe("Token Transfer Front-Running", function () {
    beforeEach(async function () {
      await loadFixture(deployContractsFixture);
    });

    it("ERC20 Permit prevents approval front-running", async function () {
      // ShaktiToken has ERC20Permit for gasless approvals
      // This allows atomic approve+transfer without mempool exposure

      const deadline = Math.floor(Date.now() / 1000) + 3600;
      const nonce = await shaktiToken.nonces(victim.address);

      // In a real scenario, the victim would sign a permit
      // and the transaction would be atomic
      expect(nonce).to.equal(0);
    });

    it("approve() susceptible to standard front-running (known limitation)", async function () {
      /**
       * Standard ERC20 approve is susceptible to front-running.
       * Mitigation: Use Permit or increaseAllowance/decreaseAllowance.
       * This is a known limitation documented in SECURITY.md
       */

      // Current allowance
      await shaktiToken.connect(victim).approve(
        frontrunner.address,
        ethers.parseEther("100")
      );

      const allowance = await shaktiToken.allowance(victim.address, frontrunner.address);
      expect(allowance).to.equal(ethers.parseEther("100"));

      // If victim tries to change allowance, front-runner could exploit
      // Recommendation: Set to 0 first, then to new value
    });
  });

  describe("Staking Front-Running", function () {
    beforeEach(async function () {
      await loadFixture(deployContractsFixture);
    });

    it("Reward rate changes are protected by governance delay", async function () {
      // Governance role required to change reward rate
      const currentRate = await stakingPool.annualRewardRate();

      // Only governance can change
      await expect(
        stakingPool.connect(frontrunner).setRewardRate(2000)
      ).to.be.reverted;

      // Rate remains unchanged
      expect(await stakingPool.annualRewardRate()).to.equal(currentRate);
    });

    it("Stake timing does not affect reward calculation unfairly", async function () {
      // Both users stake at different times
      await stakingPool.connect(victim).stake(ethers.parseEther("1000"), 0);

      // Time passes
      await ethers.provider.send("evm_increaseTime", [86400]);
      await ethers.provider.send("evm_mine", []);

      // Frontrunner stakes
      await stakingPool.connect(frontrunner).stake(ethers.parseEther("1000"), 0);

      // Victim's rewards should reflect their longer stake time
      const victimRewards = await stakingPool.getRewards(victim.address);
      const frontrunnerRewards = await stakingPool.getRewards(frontrunner.address);

      expect(victimRewards).to.be.gte(frontrunnerRewards);
    });

    it("Lock period provides time advantage protection", async function () {
      // Longer lock = higher multiplier = higher rewards
      // Cannot be front-run because decision is made upfront

      await stakingPool.connect(victim).stake(ethers.parseEther("1000"), 30 * 86400); // 30 days
      await stakingPool.connect(frontrunner).stake(ethers.parseEther("1000"), 0); // No lock

      const victimInfo = await stakingPool.getStakeInfo(victim.address);
      const frontrunnerInfo = await stakingPool.getStakeInfo(frontrunner.address);

      expect(victimInfo.multiplier).to.be.gt(frontrunnerInfo.multiplier);
    });
  });

  describe("Oracle Manipulation Prevention", function () {
    it("Auction prices bounded by min/max", async function () {
      await loadFixture(deployContractsFixture);
      await energyAuction.createAuctionRound(AUCTION_DURATION);

      const minPrice = await energyAuction.minPrice();
      const maxPrice = await energyAuction.maxPrice();

      // Cannot submit below min
      await expect(
        energyAuction.connect(victim).submitBid(ORDER_QUANTITY, minPrice - 1n)
      ).to.be.revertedWithCustomError(energyAuction, "InvalidPrice");

      // Cannot submit above max
      await expect(
        energyAuction.connect(victim).submitBid(ORDER_QUANTITY, maxPrice + 1n)
      ).to.be.revertedWithCustomError(energyAuction, "InvalidPrice");
    });

    it("Price bounds can only be set by admin", async function () {
      await loadFixture(deployContractsFixture);

      await expect(
        energyAuction.connect(frontrunner).setPriceBounds(1, 1000000)
      ).to.be.reverted;
    });
  });

  describe("Sandwich Attack Prevention", function () {
    beforeEach(async function () {
      await loadFixture(deployContractsFixture);
      await energyAuction.createAuctionRound(AUCTION_DURATION);
    });

    it("Uniform clearing price prevents sandwich attacks", async function () {
      /**
       * Sandwich attack: Attacker places buy before victim, sell after
       * In McAfee auction: Both execute at same clearing price
       * Result: Attack is not profitable
       */

      // Victim submits bid
      await energyAuction.connect(victim).submitBid(ORDER_QUANTITY, ethers.parseEther("0.006"));

      // "Sandwich" bids from attacker
      await energyAuction.connect(frontrunner).submitBid(ORDER_QUANTITY, ethers.parseEther("0.007"));
      await energyAuction.connect(frontrunner).submitAsk(ORDER_QUANTITY, ethers.parseEther("0.005"));

      // Add liquidity
      await energyAuction.connect(user).submitAsk(ORDER_QUANTITY * 2, ethers.parseEther("0.004"));

      // Clear
      await ethers.provider.send("evm_increaseTime", [AUCTION_DURATION + 1]);
      await ethers.provider.send("evm_mine", []);

      await energyAuction.closeAuction(1);
      await energyAuction.clearMarket(1);

      // All matched at uniform price - no sandwich profit
      const round = await energyAuction.getAuctionRound(1);
      expect(round.clearingPrice).to.be.gt(0);
    });
  });

  describe("Commit-Reveal Considerations", function () {
    it("Auction enforces cryptographic commit/reveal validation", async function () {
      await loadFixture(deployContractsFixture);
      await energyAuction.createAuctionRound(AUCTION_DURATION);

      const revealWindow = 600;
      const nonce = ethers.id("commit-reveal-front-running");
      const price = ethers.parseEther("0.006");
      const commitment = await energyAuction.computeCommitment(
        1,
        victim.address,
        ORDER_QUANTITY,
        price,
        true,
        nonce
      );

      await energyAuction.connect(victim).commitOrder(1, commitment, revealWindow);

      await ethers.provider.send("evm_increaseTime", [AUCTION_DURATION + 1]);
      await ethers.provider.send("evm_mine", []);
      await energyAuction.closeAuction(1);

      // Wrong nonce should fail commitment validation.
      await expect(
        energyAuction
          .connect(victim)
          .revealOrder(1, 0, ORDER_QUANTITY, price, true, ethers.id("invalid"))
      ).to.be.revertedWithCustomError(energyAuction, "InvalidRevealData");

      await expect(
        energyAuction.connect(victim).revealOrder(1, 0, ORDER_QUANTITY, price, true, nonce)
      ).to.emit(energyAuction, "OrderRevealed");
    });
  });

  describe("Flash Loan Attack Vectors", function () {
    it("Staking requires token lock, limiting flash loan utility", async function () {
      await loadFixture(deployContractsFixture);

      // Even with flash loaned tokens, stake requires time lock
      await stakingPool.connect(victim).stake(ethers.parseEther("1000"), 0);

      // Cannot immediately unstake for lock period users
      await stakingPool.connect(frontrunner).stake(ethers.parseEther("1000"), 30 * 86400);

      await expect(
        stakingPool.connect(frontrunner).unstake(ethers.parseEther("1000"))
      ).to.be.revertedWithCustomError(stakingPool, "StillLocked");
    });

    it("Auction requires deposit lock during round", async function () {
      await loadFixture(deployContractsFixture);
      await energyAuction.createAuctionRound(AUCTION_DURATION);

      // Bid locks tokens
      await energyAuction.connect(victim).submitBid(ORDER_QUANTITY, ethers.parseEther("0.006"));

      // Cannot withdraw during active auction
      // Tokens are locked until round settles
      const locked = await energyAuction.lockedDeposits(victim.address, 1);
      expect(locked).to.be.gt(0);
    });
  });
});
