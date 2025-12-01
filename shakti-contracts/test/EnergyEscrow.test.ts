import { expect } from "chai";
import { ethers } from "hardhat";
import { loadFixture, time } from "@nomicfoundation/hardhat-network-helpers";
import { ShaktiToken, EnergyEscrow } from "../typechain-types";

describe("EnergyEscrow", function () {
  // Constants
  const PRICE_PRECISION = ethers.parseEther("1");
  const FEE_PRECISION = 10000n;
  const PLATFORM_FEE = 200n; // 2%
  const FEE_BURN = 3000n; // 30%
  const DISPUTE_WINDOW = 24 * 60 * 60; // 24 hours

  // Roles
  const ARBITER_ROLE = ethers.keccak256(ethers.toUtf8Bytes("ARBITER_ROLE"));
  const AUCTION_ROLE = ethers.keccak256(ethers.toUtf8Bytes("AUCTION_ROLE"));
  const TREASURY_ROLE = ethers.keccak256(ethers.toUtf8Bytes("TREASURY_ROLE"));

  // Enum values
  enum SettlementStatus { PENDING, COMPLETED, DISPUTED, RESOLVED, REFUNDED }
  enum DisputeOutcome { NONE, BUYER_WINS, SELLER_WINS, SPLIT }

  async function deployFixture() {
    const [admin, treasury, arbiter, auctionContract, buyer1, buyer2, seller1, seller2] =
      await ethers.getSigners();

    // Deploy ShaktiToken
    const ShaktiTokenFactory = await ethers.getContractFactory("ShaktiToken");
    const token = await ShaktiTokenFactory.deploy(admin.address, admin.address);
    await token.waitForDeployment();

    // Grant BURNER_ROLE to escrow (will be done after deployment)
    const BURNER_ROLE = ethers.keccak256(ethers.toUtf8Bytes("BURNER_ROLE"));

    // Deploy EnergyEscrow
    const EnergyEscrowFactory = await ethers.getContractFactory("EnergyEscrow");
    const escrow = await EnergyEscrowFactory.deploy(
      await token.getAddress(),
      treasury.address,
      admin.address,
      PLATFORM_FEE,
      FEE_BURN
    );
    await escrow.waitForDeployment();

    // Grant BURNER_ROLE to escrow for token burning
    await token.connect(admin).grantRole(BURNER_ROLE, await escrow.getAddress());

    // Grant roles
    await escrow.connect(admin).grantRole(ARBITER_ROLE, arbiter.address);
    await escrow.connect(admin).grantRole(AUCTION_ROLE, auctionContract.address);

    // Distribute tokens
    const tokenAmount = ethers.parseEther("100000");
    await token.connect(admin).transfer(buyer1.address, tokenAmount);
    await token.connect(admin).transfer(buyer2.address, tokenAmount);
    await token.connect(admin).transfer(seller1.address, tokenAmount);
    await token.connect(admin).transfer(seller2.address, tokenAmount);

    // Approve escrow
    await token.connect(buyer1).approve(await escrow.getAddress(), ethers.MaxUint256);
    await token.connect(buyer2).approve(await escrow.getAddress(), ethers.MaxUint256);
    await token.connect(auctionContract).approve(await escrow.getAddress(), ethers.MaxUint256);

    // Transfer tokens to auction contract for deposits
    await token.connect(admin).transfer(auctionContract.address, tokenAmount);

    return {
      token,
      escrow,
      admin,
      treasury,
      arbiter,
      auctionContract,
      buyer1,
      buyer2,
      seller1,
      seller2
    };
  }

  async function deployWithSettlementFixture() {
    const fixture = await loadFixture(deployFixture);
    const { escrow, auctionContract, buyer1, seller1 } = fixture;

    // Create a settlement
    const roundId = 1;
    const quantity = 10000n; // 10 kWh in Wh
    const price = ethers.parseEther("0.010"); // Price per Wh
    const totalAmount = (quantity * price) / PRICE_PRECISION;

    // Deposit funds as auction contract
    await escrow.connect(auctionContract).depositFor(roundId, buyer1.address, totalAmount);

    // Create settlement
    await escrow.connect(auctionContract).createSettlement(
      roundId,
      buyer1.address,
      seller1.address,
      quantity,
      price
    );

    return { ...fixture, roundId, quantity, price, totalAmount };
  }

  // ============ Deployment Tests ============
  describe("Deployment", function () {
    it("should deploy with correct parameters", async function () {
      const { escrow, token, treasury } = await loadFixture(deployFixture);

      expect(await escrow.shaktiToken()).to.equal(await token.getAddress());
      expect(await escrow.treasury()).to.equal(treasury.address);
      expect(await escrow.platformFeePercentage()).to.equal(PLATFORM_FEE);
      expect(await escrow.feeBurnPercentage()).to.equal(FEE_BURN);
    });

    it("should revert if token is zero address", async function () {
      const [admin, treasury] = await ethers.getSigners();
      const EnergyEscrowFactory = await ethers.getContractFactory("EnergyEscrow");

      await expect(
        EnergyEscrowFactory.deploy(
          ethers.ZeroAddress,
          treasury.address,
          admin.address,
          PLATFORM_FEE,
          FEE_BURN
        )
      ).to.be.revertedWithCustomError(EnergyEscrowFactory, "ZeroAddress");
    });

    it("should revert if fee exceeds maximum", async function () {
      const { token } = await loadFixture(deployFixture);
      const [admin, treasury] = await ethers.getSigners();
      const EnergyEscrowFactory = await ethers.getContractFactory("EnergyEscrow");

      await expect(
        EnergyEscrowFactory.deploy(
          await token.getAddress(),
          treasury.address,
          admin.address,
          1100n, // 11% > MAX 10%
          FEE_BURN
        )
      ).to.be.revertedWithCustomError(EnergyEscrowFactory, "InvalidFeePercentage");
    });
  });

  // ============ Deposit Tests ============
  describe("Deposits", function () {
    it("should allow direct deposits", async function () {
      const { escrow, token, buyer1 } = await loadFixture(deployFixture);

      const amount = ethers.parseEther("100");
      const roundId = 1;

      await expect(escrow.connect(buyer1).deposit(roundId, amount))
        .to.emit(escrow, "Deposited")
        .withArgs(roundId, buyer1.address, amount);

      expect(await escrow.getLockedFunds(roundId, buyer1.address)).to.equal(amount);
    });

    it("should allow auction contract to deposit for traders", async function () {
      const { escrow, auctionContract, buyer1 } = await loadFixture(deployFixture);

      const amount = ethers.parseEther("100");
      const roundId = 1;

      await expect(escrow.connect(auctionContract).depositFor(roundId, buyer1.address, amount))
        .to.emit(escrow, "Deposited")
        .withArgs(roundId, buyer1.address, amount);

      expect(await escrow.getLockedFunds(roundId, buyer1.address)).to.equal(amount);
    });

    it("should revert deposit of zero amount", async function () {
      const { escrow, buyer1 } = await loadFixture(deployFixture);

      await expect(escrow.connect(buyer1).deposit(1, 0))
        .to.be.revertedWithCustomError(escrow, "ZeroAmount");
    });

    it("should revert depositFor from non-auction", async function () {
      const { escrow, buyer1, buyer2 } = await loadFixture(deployFixture);

      await expect(escrow.connect(buyer1).depositFor(1, buyer2.address, 100))
        .to.be.revertedWithCustomError(escrow, "UnauthorizedAuction");
    });
  });

  // ============ Withdrawal Tests ============
  describe("Withdrawals", function () {
    it("should allow withdrawal of unallocated funds", async function () {
      const { escrow, token, buyer1 } = await loadFixture(deployFixture);

      const amount = ethers.parseEther("100");
      const roundId = 1;

      await escrow.connect(buyer1).deposit(roundId, amount);

      const balanceBefore = await token.balanceOf(buyer1.address);

      await expect(escrow.connect(buyer1).withdraw(roundId, amount))
        .to.emit(escrow, "Withdrawn")
        .withArgs(roundId, buyer1.address, amount);

      const balanceAfter = await token.balanceOf(buyer1.address);
      expect(balanceAfter - balanceBefore).to.equal(amount);
    });

    it("should revert withdrawal exceeding locked funds", async function () {
      const { escrow, buyer1 } = await loadFixture(deployFixture);

      const amount = ethers.parseEther("100");
      const roundId = 1;

      await escrow.connect(buyer1).deposit(roundId, amount);

      await expect(escrow.connect(buyer1).withdraw(roundId, amount + 1n))
        .to.be.revertedWithCustomError(escrow, "InsufficientFunds");
    });
  });

  // ============ Settlement Creation Tests ============
  describe("Settlement Creation", function () {
    it("should create a settlement", async function () {
      const { escrow, auctionContract, buyer1, seller1 } = await loadFixture(deployFixture);

      const roundId = 1;
      const quantity = 10000n;
      const price = ethers.parseEther("0.010");
      const totalAmount = (quantity * price) / PRICE_PRECISION;

      await escrow.connect(auctionContract).depositFor(roundId, buyer1.address, totalAmount);

      await expect(
        escrow.connect(auctionContract).createSettlement(
          roundId,
          buyer1.address,
          seller1.address,
          quantity,
          price
        )
      ).to.emit(escrow, "SettlementCreated");

      const settlement = await escrow.getSettlement(0);
      expect(settlement.buyer).to.equal(buyer1.address);
      expect(settlement.seller).to.equal(seller1.address);
      expect(settlement.quantity).to.equal(quantity);
      expect(settlement.status).to.equal(SettlementStatus.PENDING);
    });

    it("should calculate correct fees", async function () {
      const { escrow, totalAmount } = await loadFixture(deployWithSettlementFixture);

      const settlement = await escrow.getSettlement(0);

      // 2% platform fee
      const expectedFee = (totalAmount * PLATFORM_FEE) / FEE_PRECISION;
      expect(settlement.platformFee).to.equal(expectedFee);

      // 30% of fee burned
      const expectedBurn = (expectedFee * FEE_BURN) / FEE_PRECISION;
      expect(settlement.burnAmount).to.equal(expectedBurn);
    });

    it("should revert if buyer has insufficient funds", async function () {
      const { escrow, auctionContract, buyer1, seller1 } = await loadFixture(deployFixture);

      await expect(
        escrow.connect(auctionContract).createSettlement(
          1,
          buyer1.address,
          seller1.address,
          10000n,
          ethers.parseEther("0.010")
        )
      ).to.be.revertedWithCustomError(escrow, "InsufficientFunds");
    });

    it("should revert if non-auction tries to create settlement", async function () {
      const { escrow, buyer1, seller1 } = await loadFixture(deployFixture);

      await expect(
        escrow.connect(buyer1).createSettlement(
          1,
          buyer1.address,
          seller1.address,
          10000n,
          ethers.parseEther("0.010")
        )
      ).to.be.revertedWithCustomError(escrow, "UnauthorizedAuction");
    });
  });

  // ============ Settlement Completion Tests ============
  describe("Settlement Completion", function () {
    it("should complete settlement after dispute window", async function () {
      const { escrow, token, seller1, treasury } = await loadFixture(deployWithSettlementFixture);

      // Fast forward past dispute window
      await time.increase(DISPUTE_WINDOW + 1);

      const sellerBalanceBefore = await token.balanceOf(seller1.address);
      const treasuryBalanceBefore = await token.balanceOf(treasury.address);

      await expect(escrow.completeSettlement(0))
        .to.emit(escrow, "SettlementCompleted");

      const settlement = await escrow.getSettlement(0);
      expect(settlement.status).to.equal(SettlementStatus.COMPLETED);

      // Verify seller received payment
      const sellerBalanceAfter = await token.balanceOf(seller1.address);
      expect(sellerBalanceAfter).to.be.gt(sellerBalanceBefore);

      // Verify treasury received fee
      const treasuryBalanceAfter = await token.balanceOf(treasury.address);
      expect(treasuryBalanceAfter).to.be.gt(treasuryBalanceBefore);
    });

    it("should burn correct amount of fees", async function () {
      const { escrow, token, totalAmount } = await loadFixture(deployWithSettlementFixture);

      await time.increase(DISPUTE_WINDOW + 1);

      const burnedBefore = await escrow.totalTokensBurned();

      await escrow.completeSettlement(0);

      const burnedAfter = await escrow.totalTokensBurned();
      const expectedFee = (totalAmount * PLATFORM_FEE) / FEE_PRECISION;
      const expectedBurn = (expectedFee * FEE_BURN) / FEE_PRECISION;

      expect(burnedAfter - burnedBefore).to.equal(expectedBurn);
    });

    it("should revert if dispute window not expired", async function () {
      const { escrow } = await loadFixture(deployWithSettlementFixture);

      await expect(escrow.completeSettlement(0))
        .to.be.revertedWithCustomError(escrow, "DisputeWindowNotExpired");
    });

    it("should revert if settlement already processed", async function () {
      const { escrow } = await loadFixture(deployWithSettlementFixture);

      await time.increase(DISPUTE_WINDOW + 1);
      await escrow.completeSettlement(0);

      await expect(escrow.completeSettlement(0))
        .to.be.revertedWithCustomError(escrow, "SettlementAlreadyProcessed");
    });

    it("should batch complete settlements", async function () {
      const { escrow, auctionContract, buyer1, buyer2, seller1, seller2 } =
        await loadFixture(deployFixture);

      const roundId = 1;
      const quantity = 5000n;
      const price = ethers.parseEther("0.010");
      const totalAmount = (quantity * price) / PRICE_PRECISION;

      // Create multiple settlements
      await escrow.connect(auctionContract).depositFor(roundId, buyer1.address, totalAmount);
      await escrow.connect(auctionContract).depositFor(roundId, buyer2.address, totalAmount);

      await escrow.connect(auctionContract).createSettlement(roundId, buyer1.address, seller1.address, quantity, price);
      await escrow.connect(auctionContract).createSettlement(roundId, buyer2.address, seller2.address, quantity, price);

      await time.increase(DISPUTE_WINDOW + 1);

      await escrow.batchCompleteSettlements([0, 1]);

      expect((await escrow.getSettlement(0)).status).to.equal(SettlementStatus.COMPLETED);
      expect((await escrow.getSettlement(1)).status).to.equal(SettlementStatus.COMPLETED);
    });
  });

  // ============ Dispute Tests ============
  describe("Dispute Resolution", function () {
    it("should allow buyer to raise dispute", async function () {
      const { escrow, buyer1 } = await loadFixture(deployWithSettlementFixture);

      await expect(escrow.connect(buyer1).raiseDispute(0, "Energy not received"))
        .to.emit(escrow, "DisputeRaised")
        .withArgs(0, buyer1.address, "Energy not received");

      const settlement = await escrow.getSettlement(0);
      expect(settlement.status).to.equal(SettlementStatus.DISPUTED);
    });

    it("should allow seller to raise dispute", async function () {
      const { escrow, seller1 } = await loadFixture(deployWithSettlementFixture);

      await expect(escrow.connect(seller1).raiseDispute(0, "Energy delivered but not confirmed"))
        .to.emit(escrow, "DisputeRaised");
    });

    it("should revert dispute from non-party", async function () {
      const { escrow, buyer2 } = await loadFixture(deployWithSettlementFixture);

      await expect(escrow.connect(buyer2).raiseDispute(0, "Not my business"))
        .to.be.revertedWithCustomError(escrow, "NotPartyToSettlement");
    });

    it("should revert dispute after window expires", async function () {
      const { escrow, buyer1 } = await loadFixture(deployWithSettlementFixture);

      await time.increase(DISPUTE_WINDOW + 1);

      await expect(escrow.connect(buyer1).raiseDispute(0, "Too late"))
        .to.be.revertedWithCustomError(escrow, "DisputeWindowExpired");
    });

    it("should revert duplicate dispute", async function () {
      const { escrow, buyer1, seller1 } = await loadFixture(deployWithSettlementFixture);

      await escrow.connect(buyer1).raiseDispute(0, "First dispute");

      await expect(escrow.connect(seller1).raiseDispute(0, "Second dispute"))
        .to.be.revertedWithCustomError(escrow, "SettlementAlreadyProcessed");
    });

    it("should resolve dispute in buyer's favor", async function () {
      const { escrow, token, arbiter, buyer1, seller1 } = await loadFixture(deployWithSettlementFixture);

      await escrow.connect(buyer1).raiseDispute(0, "Energy not received");

      const buyerBalanceBefore = await token.balanceOf(buyer1.address);

      await expect(
        escrow.connect(arbiter).resolveDispute(0, DisputeOutcome.BUYER_WINS, "Seller failed to deliver", false)
      ).to.emit(escrow, "DisputeResolved")
        .withArgs(0, DisputeOutcome.BUYER_WINS, "Seller failed to deliver");

      const buyerBalanceAfter = await token.balanceOf(buyer1.address);

      // Buyer should get full refund
      const settlement = await escrow.getSettlement(0);
      expect(buyerBalanceAfter - buyerBalanceBefore).to.equal(settlement.totalAmount);
      expect(settlement.status).to.equal(SettlementStatus.RESOLVED);
    });

    it("should resolve dispute in seller's favor", async function () {
      const { escrow, token, arbiter, buyer1, seller1 } = await loadFixture(deployWithSettlementFixture);

      await escrow.connect(buyer1).raiseDispute(0, "False claim");

      const sellerBalanceBefore = await token.balanceOf(seller1.address);

      await escrow.connect(arbiter).resolveDispute(0, DisputeOutcome.SELLER_WINS, "Energy was delivered", false);

      const sellerBalanceAfter = await token.balanceOf(seller1.address);

      // Seller should get payment minus fee
      expect(sellerBalanceAfter).to.be.gt(sellerBalanceBefore);
    });

    it("should resolve dispute with split", async function () {
      const { escrow, token, arbiter, buyer1, seller1 } = await loadFixture(deployWithSettlementFixture);

      await escrow.connect(buyer1).raiseDispute(0, "Partial delivery");

      const buyerBalanceBefore = await token.balanceOf(buyer1.address);
      const sellerBalanceBefore = await token.balanceOf(seller1.address);

      await escrow.connect(arbiter).resolveDispute(0, DisputeOutcome.SPLIT, "Both parties partially at fault", false);

      const buyerBalanceAfter = await token.balanceOf(buyer1.address);
      const sellerBalanceAfter = await token.balanceOf(seller1.address);

      // Both should receive approximately half
      expect(buyerBalanceAfter).to.be.gt(buyerBalanceBefore);
      expect(sellerBalanceAfter).to.be.gt(sellerBalanceBefore);
    });

    it("should slash bad actor on dispute resolution", async function () {
      const { escrow, arbiter, buyer1, seller1 } = await loadFixture(deployWithSettlementFixture);

      await escrow.connect(buyer1).raiseDispute(0, "Energy not received");

      await expect(
        escrow.connect(arbiter).resolveDispute(0, DisputeOutcome.BUYER_WINS, "Seller failed", true)
      ).to.emit(escrow, "Slashed")
        .withArgs(seller1.address, 1, "Dispute lost - energy not delivered");

      expect(await escrow.slashCount(seller1.address)).to.equal(1);
    });

    it("should revert resolve from non-arbiter", async function () {
      const { escrow, buyer1 } = await loadFixture(deployWithSettlementFixture);

      await escrow.connect(buyer1).raiseDispute(0, "Energy not received");

      await expect(
        escrow.connect(buyer1).resolveDispute(0, DisputeOutcome.BUYER_WINS, "Self resolution", false)
      ).to.be.revertedWithCustomError(escrow, "AccessControlUnauthorizedAccount");
    });
  });

  // ============ Refund Tests ============
  describe("Refunds", function () {
    it("should refund settlement on cancellation", async function () {
      const { escrow, token, auctionContract, buyer1, totalAmount } =
        await loadFixture(deployWithSettlementFixture);

      const buyerBalanceBefore = await token.balanceOf(buyer1.address);

      await expect(escrow.connect(auctionContract).refundSettlement(0))
        .to.emit(escrow, "Refunded")
        .withArgs(0, buyer1.address, totalAmount);

      const buyerBalanceAfter = await token.balanceOf(buyer1.address);
      expect(buyerBalanceAfter - buyerBalanceBefore).to.equal(totalAmount);

      const settlement = await escrow.getSettlement(0);
      expect(settlement.status).to.equal(SettlementStatus.REFUNDED);
    });

    it("should revert refund from non-auction", async function () {
      const { escrow, buyer1 } = await loadFixture(deployWithSettlementFixture);

      await expect(escrow.connect(buyer1).refundSettlement(0))
        .to.be.revertedWithCustomError(escrow, "UnauthorizedAuction");
    });
  });

  // ============ View Functions Tests ============
  describe("View Functions", function () {
    it("should return settlement details", async function () {
      const { escrow, buyer1, seller1, quantity, price } =
        await loadFixture(deployWithSettlementFixture);

      const settlement = await escrow.getSettlement(0);
      expect(settlement.buyer).to.equal(buyer1.address);
      expect(settlement.seller).to.equal(seller1.address);
      expect(settlement.quantity).to.equal(quantity);
      expect(settlement.price).to.equal(price);
    });

    it("should return round settlements", async function () {
      const { escrow, roundId } = await loadFixture(deployWithSettlementFixture);

      const settlements = await escrow.getRoundSettlements(roundId);
      expect(settlements.length).to.equal(1);
      expect(settlements[0]).to.equal(0);
    });

    it("should return trader settlements", async function () {
      const { escrow, buyer1, seller1 } = await loadFixture(deployWithSettlementFixture);

      const buyerSettlements = await escrow.getTraderSettlements(buyer1.address);
      const sellerSettlements = await escrow.getTraderSettlements(seller1.address);

      expect(buyerSettlements.length).to.equal(1);
      expect(sellerSettlements.length).to.equal(1);
    });

    it("should calculate fees correctly", async function () {
      const { escrow } = await loadFixture(deployFixture);

      const amount = ethers.parseEther("100");
      const [platformFee, burnAmount, treasuryAmount, sellerAmount] =
        await escrow.calculateFees(amount);

      // 2% fee
      expect(platformFee).to.equal((amount * PLATFORM_FEE) / FEE_PRECISION);

      // 30% of fee burned
      expect(burnAmount).to.equal((platformFee * FEE_BURN) / FEE_PRECISION);

      // 70% of fee to treasury
      expect(treasuryAmount).to.equal(platformFee - burnAmount);

      // Seller gets amount - fee
      expect(sellerAmount).to.equal(amount - platformFee);
    });

    it("should check if settlement can be completed", async function () {
      const { escrow } = await loadFixture(deployWithSettlementFixture);

      expect(await escrow.canComplete(0)).to.be.false;

      await time.increase(DISPUTE_WINDOW + 1);

      expect(await escrow.canComplete(0)).to.be.true;
    });

    it("should check if dispute can be raised", async function () {
      const { escrow, buyer1 } = await loadFixture(deployWithSettlementFixture);

      expect(await escrow.canRaiseDispute(0)).to.be.true;

      await escrow.connect(buyer1).raiseDispute(0, "Test");

      expect(await escrow.canRaiseDispute(0)).to.be.false;
    });
  });

  // ============ Admin Functions Tests ============
  describe("Admin Functions", function () {
    it("should update platform fee", async function () {
      const { escrow, admin } = await loadFixture(deployFixture);

      await expect(escrow.connect(admin).setPlatformFee(300))
        .to.emit(escrow, "FeeUpdated")
        .withArgs(PLATFORM_FEE, 300);

      expect(await escrow.platformFeePercentage()).to.equal(300);
    });

    it("should update burn percentage", async function () {
      const { escrow, admin } = await loadFixture(deployFixture);

      await expect(escrow.connect(admin).setFeeBurnPercentage(5000))
        .to.emit(escrow, "BurnPercentageUpdated")
        .withArgs(FEE_BURN, 5000);

      expect(await escrow.feeBurnPercentage()).to.equal(5000);
    });

    it("should update treasury address", async function () {
      const { escrow, admin, buyer1 } = await loadFixture(deployFixture);

      await expect(escrow.connect(admin).setTreasury(buyer1.address))
        .to.emit(escrow, "TreasuryUpdated");

      expect(await escrow.treasury()).to.equal(buyer1.address);
    });

    it("should toggle circuit breaker", async function () {
      const { escrow, admin } = await loadFixture(deployFixture);

      await expect(escrow.connect(admin).setCircuitBreaker(true))
        .to.emit(escrow, "CircuitBreakerToggled")
        .withArgs(true);

      expect(await escrow.circuitBreakerActive()).to.be.true;
    });

    it("should prevent operations when circuit breaker active", async function () {
      const { escrow, admin, buyer1 } = await loadFixture(deployFixture);

      await escrow.connect(admin).setCircuitBreaker(true);

      await expect(escrow.connect(buyer1).deposit(1, 100))
        .to.be.revertedWithCustomError(escrow, "CircuitBreakerActive");
    });

    it("should allow emergency withdrawal when circuit breaker active", async function () {
      const { escrow, token, admin, buyer1 } = await loadFixture(deployFixture);

      const amount = ethers.parseEther("100");
      await escrow.connect(buyer1).deposit(1, amount);

      await escrow.connect(admin).setCircuitBreaker(true);

      const balanceBefore = await token.balanceOf(buyer1.address);

      await expect(escrow.connect(admin).emergencyWithdrawFor(1, buyer1.address))
        .to.emit(escrow, "EmergencyWithdraw")
        .withArgs(buyer1.address, amount);

      const balanceAfter = await token.balanceOf(buyer1.address);
      expect(balanceAfter - balanceBefore).to.equal(amount);
    });

    it("should pause and unpause", async function () {
      const { escrow, admin, buyer1 } = await loadFixture(deployFixture);

      await escrow.connect(admin).pause();
      expect(await escrow.paused()).to.be.true;

      await expect(escrow.connect(buyer1).deposit(1, 100))
        .to.be.revertedWithCustomError(escrow, "EnforcedPause");

      await escrow.connect(admin).unpause();

      await expect(escrow.connect(buyer1).deposit(1, ethers.parseEther("1")))
        .to.emit(escrow, "Deposited");
    });
  });

  // ============ Edge Cases ============
  describe("Edge Cases", function () {
    it("should handle multiple settlements for same buyer", async function () {
      const { escrow, auctionContract, buyer1, seller1, seller2 } =
        await loadFixture(deployFixture);

      const roundId = 1;
      const quantity = 5000n;
      const price = ethers.parseEther("0.010");
      const totalAmount = (quantity * price) / PRICE_PRECISION;

      await escrow.connect(auctionContract).depositFor(roundId, buyer1.address, totalAmount * 2n);

      await escrow.connect(auctionContract).createSettlement(roundId, buyer1.address, seller1.address, quantity, price);
      await escrow.connect(auctionContract).createSettlement(roundId, buyer1.address, seller2.address, quantity, price);

      const settlements = await escrow.getTraderSettlements(buyer1.address);
      expect(settlements.length).to.equal(2);
    });

    it("should handle zero burn percentage", async function () {
      const { escrow, admin, token, auctionContract, buyer1, seller1, treasury } =
        await loadFixture(deployFixture);

      // Set burn to 0
      await escrow.connect(admin).setFeeBurnPercentage(0);

      const roundId = 1;
      const quantity = 10000n;
      const price = ethers.parseEther("0.010");
      const totalAmount = (quantity * price) / PRICE_PRECISION;

      await escrow.connect(auctionContract).depositFor(roundId, buyer1.address, totalAmount);
      await escrow.connect(auctionContract).createSettlement(roundId, buyer1.address, seller1.address, quantity, price);

      await time.increase(DISPUTE_WINDOW + 1);

      const treasuryBefore = await token.balanceOf(treasury.address);
      const burnedBefore = await escrow.totalTokensBurned();

      await escrow.completeSettlement(0);

      const treasuryAfter = await token.balanceOf(treasury.address);
      const burnedAfter = await escrow.totalTokensBurned();

      // All fee should go to treasury
      const expectedFee = (totalAmount * PLATFORM_FEE) / FEE_PRECISION;
      expect(treasuryAfter - treasuryBefore).to.equal(expectedFee);
      expect(burnedAfter - burnedBefore).to.equal(0);
    });

    it("should track total fees and burns", async function () {
      const { escrow, totalAmount } = await loadFixture(deployWithSettlementFixture);

      await time.increase(DISPUTE_WINDOW + 1);
      await escrow.completeSettlement(0);

      const expectedFee = (totalAmount * PLATFORM_FEE) / FEE_PRECISION;
      const expectedBurn = (expectedFee * FEE_BURN) / FEE_PRECISION;

      expect(await escrow.totalFeesCollected()).to.equal(expectedFee);
      expect(await escrow.totalTokensBurned()).to.equal(expectedBurn);
    });
  });
});
